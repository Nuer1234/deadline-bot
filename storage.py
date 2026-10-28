"""The task store, currently a single JSON file.

Everything that touches the data goes through the Store class on purpose, so that
swapping in SQLite later means editing this file and nothing else — bot.py stays as is.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from dateparse import TZ

SCHEMA_VERSION = 1


@dataclass
class Task:
    id: int
    title: str
    due: str                      # ISO 8601 with offset, e.g. 2026-09-05T23:59:00+07:00
    owner_id: int
    owner_name: str
    category: str | None = None
    done: bool = False
    created_at: str = ""
    done_at: str | None = None
    # Dates (YYYY-MM-DD) this task was already announced on, so a restart does not repeat it
    reminded_on: list[str] = field(default_factory=list)

    @property
    def due_dt(self) -> datetime:
        return datetime.fromisoformat(self.due).astimezone(TZ)


def _empty_guild() -> dict:
    return {
        "next_id": 1,
        "reminder_channel_id": None,
        "last_digest_date": None,
        "tasks": [],
    }


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict = {"version": SCHEMA_VERSION, "guilds": {}}
        self.load()

    # ---------- file ----------

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Keep a corrupt file for later inspection; better than refusing to start
            backup = self.path.with_suffix(self.path.suffix + ".broken")
            try:
                self.path.replace(backup)
            except OSError:
                pass
            return
        if isinstance(data, dict) and "guilds" in data:
            self._data = data

    def save(self) -> None:
        """Atomic write: fill a temporary file first, then replace the real one.

        Overwriting in place and having the process die halfway loses the whole file.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ---------- guild ----------

    def _guild(self, guild_id: int) -> dict:
        guilds = self._data.setdefault("guilds", {})
        return guilds.setdefault(str(guild_id), _empty_guild())

    def get_reminder_channel(self, guild_id: int) -> int | None:
        return self._guild(guild_id)["reminder_channel_id"]

    def set_reminder_channel(self, guild_id: int, channel_id: int | None) -> None:
        self._guild(guild_id)["reminder_channel_id"] = channel_id
        self.save()

    def get_last_digest_date(self, guild_id: int) -> str | None:
        return self._guild(guild_id)["last_digest_date"]

    def set_last_digest_date(self, guild_id: int, day: str) -> None:
        self._guild(guild_id)["last_digest_date"] = day
        self.save()

    def guild_ids(self) -> list[int]:
        return [int(gid) for gid in self._data.get("guilds", {})]

    # ---------- tasks ----------

    def add_task(
        self,
        guild_id: int,
        title: str,
        due: datetime,
        owner_id: int,
        owner_name: str,
        category: str | None = None,
        now: datetime | None = None,
    ) -> Task:
        guild = self._guild(guild_id)
        task = Task(
            id=guild["next_id"],
            title=title,
            due=due.astimezone(TZ).isoformat(),
            owner_id=owner_id,
            owner_name=owner_name,
            category=category,
            created_at=(now or datetime.now(TZ)).isoformat(),
        )
        guild["next_id"] += 1
        guild["tasks"].append(asdict(task))
        self.save()
        return task

    def all_tasks(self, guild_id: int) -> list[Task]:
        return [Task(**raw) for raw in self._guild(guild_id)["tasks"]]

    def list_tasks(
        self,
        guild_id: int,
        owner_id: int | None = None,
        category: str | None = None,
        include_done: bool = False,
    ) -> list[Task]:
        """Unfinished tasks, soonest deadline first."""
        tasks = self.all_tasks(guild_id)
        if not include_done:
            tasks = [t for t in tasks if not t.done]
        if owner_id is not None:
            tasks = [t for t in tasks if t.owner_id == owner_id]
        if category is not None:
            tasks = [t for t in tasks if (t.category or "") == category.lower()]
        return sorted(tasks, key=lambda t: t.due_dt)

    def get_task(self, guild_id: int, task_id: int) -> Task | None:
        for raw in self._guild(guild_id)["tasks"]:
            if raw["id"] == task_id:
                return Task(**raw)
        return None

    def _update(self, guild_id: int, task_id: int, **fields) -> Task | None:
        for raw in self._guild(guild_id)["tasks"]:
            if raw["id"] == task_id:
                raw.update(fields)
                self.save()
                return Task(**raw)
        return None

    def mark_done(self, guild_id: int, task_id: int, now: datetime | None = None) -> Task | None:
        return self._update(
            guild_id, task_id, done=True, done_at=(now or datetime.now(TZ)).isoformat()
        )

    def mark_undone(self, guild_id: int, task_id: int) -> Task | None:
        return self._update(guild_id, task_id, done=False, done_at=None)

    def mark_reminded(self, guild_id: int, task_id: int, day: str) -> None:
        task = self.get_task(guild_id, task_id)
        if task is None or day in task.reminded_on:
            return
        self._update(guild_id, task_id, reminded_on=[*task.reminded_on, day])

    def delete_task(self, guild_id: int, task_id: int) -> Task | None:
        guild = self._guild(guild_id)
        for i, raw in enumerate(guild["tasks"]):
            if raw["id"] == task_id:
                guild["tasks"].pop(i)
                self.save()
                return Task(**raw)
        return None

    def stats(self, guild_id: int, owner_id: int | None = None) -> dict:
        tasks = self.all_tasks(guild_id)
        if owner_id is not None:
            tasks = [t for t in tasks if t.owner_id == owner_id]
        done = [t for t in tasks if t.done]
        pending = [t for t in tasks if not t.done]
        # On time means !done was pressed before the deadline
        on_time = sum(1 for t in done if t.done_at and datetime.fromisoformat(t.done_at) <= t.due_dt)
        return {
            "total": len(tasks),
            "done": len(done),
            "pending": len(pending),
            "on_time": on_time,
            "percent": round(len(done) * 100 / len(tasks)) if tasks else 0,
        }
