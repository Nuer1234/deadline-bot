"""A Discord bot that reminds a study group about homework deadlines.

Run with:  python bot.py   (DISCORD_TOKEN must be set in .env first)

The replies below are written in Thai on purpose: this bot was built for a Thai
study group, and the date parser understands Thai date words.
"""

from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord.ext import commands, tasks

import config
from dateparse import DateParseError, now_bkk, parse_deadline
from formatting import THAI_MONTH_ABBR, format_due, relative_due, task_line
from reminders import pick_tasks_to_remind, should_run_digest, split_by_urgency
from storage import Store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("deadline-bot")

COLOR = 0x5865F2
COLOR_OK = 0x57F287
COLOR_WARN = 0xED4245
MAX_LINES_PER_FIELD = 15  # Discord caps an embed field at 1024 characters

store = Store(config.DATA_FILE)

intents = discord.Intents.default()
intents.message_content = True  # MESSAGE CONTENT INTENT must also be on in the Developer Portal
bot = commands.Bot(command_prefix=config.PREFIX, intents=intents, help_command=None)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@bot.command(name="add", aliases=["a"])
@commands.guild_only()
async def add_task(ctx: commands.Context, *, arg: str = ""):
    """!add <task> <date> [time] [#category]"""
    if not arg.strip():
        await ctx.reply(
            f"ใช้แบบนี้ครับ: `{config.PREFIX}add เขียนรายงาน Calculus 5/9`\n"
            f"ดูรูปแบบวันที่ทั้งหมดได้ที่ `{config.PREFIX}help`"
        )
        return

    try:
        parsed = parse_deadline(arg)
    except DateParseError:
        await ctx.reply(
            "อ่านวันที่ไม่ออกครับ วันที่ต้องอยู่ท้ายสุด เช่น\n"
            f"`{config.PREFIX}add ส่งแล็บฟิสิกส์ พรุ่งนี้`\n"
            f"`{config.PREFIX}add เขียนรายงาน 5/9 23:59 #calculus`"
        )
        return

    if not parsed.title:
        await ctx.reply("ใส่ชื่องานด้วยครับ ไม่งั้นจะไม่รู้ว่าเตือนเรื่องอะไร")
        return

    now = now_bkk()
    task = store.add_task(
        guild_id=ctx.guild.id,
        title=parsed.title,
        due=parsed.due,
        owner_id=ctx.author.id,
        owner_name=ctx.author.display_name,
        category=parsed.category,
        now=now,
    )

    embed = discord.Embed(
        title=f"เพิ่มแล้ว · #{task.id}",
        description=task.title,
        color=COLOR_OK,
    )
    embed.add_field(
        name="กำหนดส่ง",
        value=f"{format_due(task.due_dt, now)} ({relative_due(task.due_dt, now)})",
    )
    if task.category:
        embed.add_field(name="หมวด", value=f"#{task.category}")
    if task.due_dt < now:
        embed.set_footer(text=f"วันที่ที่ใส่มาเลยไปแล้ว ถ้าพิมพ์ผิดลบด้วย {config.PREFIX}del")
    await ctx.reply(embed=embed)


@bot.command(name="list", aliases=["ls", "l"])
@commands.guild_only()
async def list_tasks(ctx: commands.Context, *, arg: str = ""):
    """!list [all|#category|@someone] — with no argument, your own list."""
    arg = arg.strip()
    now = now_bkk()

    tokens = arg.split()
    show_everyone = any(t.lower() in ("all", "ทั้งหมด", "everyone") for t in tokens)
    owner = ctx.author
    if ctx.message.mentions:
        owner = ctx.message.mentions[0]
        show_everyone = False

    # The category may arrive as "#calculus" or plain "calculus".
    # (If a channel of that name exists, Discord turns the # into a channel mention.)
    category = None
    for token in tokens:
        word = token[1:] if token.startswith("#") else token
        if not word or token.startswith("<") or word.lower() in ("all", "ทั้งหมด", "everyone"):
            continue
        category = word.lower()
        break

    tasks_found = store.list_tasks(
        ctx.guild.id,
        owner_id=None if show_everyone else owner.id,
        category=category,
    )

    who = "ทั้งเซิร์ฟเวอร์" if show_everyone else f"ของ {owner.display_name}"
    title = f"งานที่ยังไม่เสร็จ {who}"
    if category:
        title += f" · #{category}"

    if not tasks_found:
        await ctx.reply(embed=discord.Embed(
            title=title,
            description=f"ว่างเลย ไม่มีงานค้าง 🎉\nเพิ่มงานด้วย `{config.PREFIX}add ...`",
            color=COLOR,
        ))
        return

    overdue, today_due, upcoming = split_by_urgency(tasks_found, now)
    embed = discord.Embed(title=title, color=COLOR_WARN if overdue else COLOR)
    for name, group in (
        ("เลยกำหนดแล้ว", overdue),
        ("ครบกำหนดวันนี้", today_due),
        ("กำลังจะถึง", upcoming),
    ):
        if group:
            embed.add_field(
                name=f"{name} ({len(group)})",
                value=_render_group(group, now, show_owner=show_everyone),
                inline=False,
            )
    embed.set_footer(text=f"ทำเสร็จแล้วพิมพ์ {config.PREFIX}done <id>")
    await ctx.reply(embed=embed)


def _render_group(group, now: datetime, show_owner: bool) -> str:
    lines = [task_line(t, now, show_owner=show_owner) for t in group[:MAX_LINES_PER_FIELD]]
    if len(group) > MAX_LINES_PER_FIELD:
        lines.append(f"…และอีก {len(group) - MAX_LINES_PER_FIELD} รายการ")
    return "\n".join(lines)


@bot.command(name="done", aliases=["d"])
@commands.guild_only()
async def done(ctx: commands.Context, task_id: int):
    """!done <id> — mark finished; it stays in the data for the stats."""
    task = store.get_task(ctx.guild.id, task_id)
    if task is None:
        await ctx.reply(f"ไม่มีงาน #{task_id} ครับ ลองดูเลขจาก `{config.PREFIX}list`")
        return
    if task.done:
        await ctx.reply(f"#{task_id} **{task.title}** เสร็จไปแล้วนะ")
        return

    now = now_bkk()
    task = store.mark_done(ctx.guild.id, task_id, now=now)
    late = " (ส่งช้ากว่ากำหนดนะ)" if now > task.due_dt else ""
    await ctx.reply(f"✅ ปิดงาน #{task.id} **{task.title}** เรียบร้อย{late}")


@bot.command(name="undone", aliases=["undo"])
@commands.guild_only()
async def undone(ctx: commands.Context, task_id: int):
    """!undone <id> — undo a !done pressed by mistake."""
    task = store.mark_undone(ctx.guild.id, task_id)
    if task is None:
        await ctx.reply(f"ไม่มีงาน #{task_id} ครับ")
        return
    await ctx.reply(f"↩️ เอา #{task.id} **{task.title}** กลับเข้าลิสต์แล้ว")


@bot.command(name="delete", aliases=["del", "rm", "remove"])
@commands.guild_only()
async def delete(ctx: commands.Context, task_id: int):
    """!del <id> — delete for good, for when a task was added wrongly."""
    task = store.get_task(ctx.guild.id, task_id)
    if task is None:
        await ctx.reply(f"ไม่มีงาน #{task_id} ครับ")
        return
    if task.owner_id != ctx.author.id and not ctx.author.guild_permissions.manage_messages:
        await ctx.reply("ลบได้เฉพาะงานของตัวเองนะครับ")
        return
    store.delete_task(ctx.guild.id, task_id)
    await ctx.reply(f"🗑️ ลบ #{task.id} **{task.title}** แล้ว")


@bot.command(name="stats", aliases=["stat"])
@commands.guild_only()
async def stats(ctx: commands.Context, *, arg: str = ""):
    """!stats [all|@someone]"""
    show_everyone = arg.strip().lower() in ("all", "ทั้งหมด", "everyone")
    owner = ctx.author
    if ctx.message.mentions:
        owner = ctx.message.mentions[0]
        show_everyone = False

    data = store.stats(ctx.guild.id, owner_id=None if show_everyone else owner.id)
    who = "ทั้งเซิร์ฟเวอร์" if show_everyone else owner.display_name

    if data["total"] == 0:
        await ctx.reply(f"ยังไม่มีข้อมูลของ {who} เลยครับ")
        return

    filled = round(data["percent"] / 10)
    bar = "█" * filled + "░" * (10 - filled)
    embed = discord.Embed(title=f"สถิติของ {who}", color=COLOR)
    embed.description = f"`{bar}` **{data['percent']}%**"
    embed.add_field(name="ทำเสร็จ", value=f"{data['done']} / {data['total']}")
    embed.add_field(name="ค้างอยู่", value=str(data["pending"]))
    embed.add_field(name="ส่งทันกำหนด", value=f"{data['on_time']} / {data['done']}")
    await ctx.reply(embed=embed)


@bot.command(name="setchannel")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def set_channel(ctx: commands.Context, channel: discord.TextChannel = None):
    """!setchannel [#channel] — choose where the morning digest is posted."""
    channel = channel or ctx.channel
    store.set_reminder_channel(ctx.guild.id, channel.id)
    await ctx.reply(
        f"จะส่งเตือนที่ {channel.mention} ทุกวันประมาณ {config.REMINDER_HOUR:02d}:00 น. ครับ"
    )


@bot.command(name="help", aliases=["h"])
async def help_command(ctx: commands.Context):
    p = config.PREFIX
    embed = discord.Embed(
        title="คำสั่งทั้งหมด",
        description="บอทเตือน deadline การบ้าน — เวลาทั้งหมดเป็นเวลาไทย (UTC+7)",
        color=COLOR,
    )
    embed.add_field(
        name="จัดการงาน",
        value=(
            f"`{p}add <งาน> <วันที่> [เวลา] [#หมวด]` เพิ่มงาน\n"
            f"`{p}list` ดูงานของตัวเอง · `{p}list all` ดูทั้งเซิร์ฟเวอร์\n"
            f"`{p}list #calculus` หรือ `{p}list @เพื่อน` กรองดู\n"
            f"`{p}done <id>` ปิดงาน · `{p}undone <id>` เอากลับ\n"
            f"`{p}del <id>` ลบทิ้ง · `{p}stats` ดูสถิติ"
        ),
        inline=False,
    )
    embed.add_field(
        name="รูปแบบวันที่ที่เขียนได้",
        value=(
            "`วันนี้` `พรุ่งนี้` `มะรืน` `ศุกร์`\n"
            "`5/9` `5/9/2569` `2026-09-05` `5 ก.ย.`\n"
            "ต่อท้ายด้วยเวลาได้ เช่น `5/9 16:30` (ไม่ใส่ = 23:59)"
        ),
        inline=False,
    )
    embed.add_field(
        name="ตั้งค่า (แอดมิน)",
        value=f"`{p}setchannel #ช่อง` เลือกช่องที่จะเตือนทุกเช้า",
        inline=False,
    )
    await ctx.reply(embed=embed)


# --------------------------------------------------------------------------
# Automatic reminders
# --------------------------------------------------------------------------

@tasks.loop(minutes=config.CHECK_INTERVAL_MINUTES)
async def reminder_loop():
    """Wake every N minutes and look for guilds still owed today's digest."""
    now = now_bkk()
    for guild_id in store.guild_ids():
        try:
            await maybe_send_digest(guild_id, now)
        except Exception:
            log.exception("failed to send the digest for guild %s", guild_id)


async def maybe_send_digest(guild_id: int, now: datetime) -> bool:
    if not should_run_digest(store.get_last_digest_date(guild_id), now, config.REMINDER_HOUR):
        return False

    channel_id = store.get_reminder_channel(guild_id)
    if channel_id is None:
        return False
    channel = bot.get_channel(channel_id)
    if channel is None:
        log.warning("guild %s points at channel %s, which cannot be found", guild_id, channel_id)
        return False

    due_tasks = pick_tasks_to_remind(
        store.all_tasks(guild_id), now, lead_days=config.REMINDER_LEAD_DAYS
    )

    # Record the check even when nothing is due, so it is not retried all day long
    store.set_last_digest_date(guild_id, now.date().isoformat())
    if not due_tasks:
        return False

    overdue, today_due, upcoming = split_by_urgency(due_tasks, now)
    embed = discord.Embed(
        title="⏰ เตือนความจำประจำวัน",
        description=f"{now.day} {THAI_MONTH_ABBR[now.month]} {now.year + 543}",
        color=COLOR_WARN if overdue else COLOR,
    )
    for name, group in (
        ("เลยกำหนดแล้ว", overdue),
        ("ครบกำหนดวันนี้", today_due),
        ("ครบกำหนดพรุ่งนี้", upcoming),
    ):
        if group:
            embed.add_field(
                name=f"{name} ({len(group)})",
                value=_render_group(group, now, show_owner=True),
                inline=False,
            )

    mentions = " ".join(sorted({f"<@{t.owner_id}>" for t in due_tasks}))
    await channel.send(content=mentions, embed=embed)

    for task in due_tasks:
        store.mark_reminded(guild_id, task.id, now.date().isoformat())
    log.info("sent a digest of %s task(s) to guild %s", len(due_tasks), guild_id)
    return True


@reminder_loop.before_loop
async def before_reminder_loop():
    await bot.wait_until_ready()


# --------------------------------------------------------------------------
# event / error
# --------------------------------------------------------------------------

@bot.event
async def on_ready():
    log.info("logged in as %s (%s guild(s))", bot.user, len(bot.guilds))
    if not reminder_loop.is_running():
        reminder_loop.start()
    await bot.change_presence(
        activity=discord.Game(name=f"{config.PREFIX}help | เตือน deadline")
    )


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"ใส่ argument ไม่ครบครับ ลองดู `{config.PREFIX}help`")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.reply(f"id ต้องเป็นตัวเลขนะครับ เช่น `{config.PREFIX}done 3`")
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("คำสั่งนี้ใช้ได้เฉพาะแอดมินของเซิร์ฟเวอร์ครับ")
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.reply("ใช้ในเซิร์ฟเวอร์เท่านั้นครับ (แต่ละเซิร์ฟเวอร์มีลิสต์แยกกัน)")
        return
    log.exception("command %s crashed", ctx.command, exc_info=error)
    await ctx.reply("มีอะไรผิดพลาดครับ ลองใหม่อีกที")


def main():
    if not config.TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is not set - copy .env.example to .env and put your token in it"
        )
    bot.run(config.TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
