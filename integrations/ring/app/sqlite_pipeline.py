"""Local durable event/job store for Ring summary demos and offline testing.

This is deliberately integration-local. It is not a replacement for the
AccessAble backend database or an ownership-aware production data model.
"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROCESSING_VERSION = "ring-summary-v1"
JOB_STATES = {
    "pending", "waiting_for_recording", "retrieving", "summarizing",
    "completed", "unavailable", "failed", "skipped",
}


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Timestamps must have a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class ClaimedJob:
    job_id: int
    event_id: int
    event_key: str
    worker_id: str
    attempt_count: int
    event: dict[str, Any]
    processing_version: str


class SQLitePipelineStore:
    """SQLite WAL store with atomic enqueue/claim and lease-based recovery."""

    def __init__(self, database_path: str | Path, *, busy_timeout_ms: int = 5000):
        if str(database_path) == ":memory:":
            raise ValueError("Use a temporary SQLite file so worker restart recovery is meaningful")
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.busy_timeout_ms = busy_timeout_ms
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ring_local_events (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_event_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(source, external_event_id)
                );
                CREATE INDEX IF NOT EXISTS ix_ring_local_events_time
                    ON ring_local_events(occurred_at DESC, id DESC);
                CREATE TABLE IF NOT EXISTS ring_summary_jobs (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL REFERENCES ring_local_events(id) ON DELETE CASCADE,
                    processing_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT NOT NULL,
                    lock_owner TEXT,
                    locked_until TEXT,
                    error_category TEXT,
                    importance_json TEXT,
                    recording_json TEXT,
                    summary_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(event_id, processing_version)
                );
                CREATE INDEX IF NOT EXISTS ix_ring_summary_jobs_claim
                    ON ring_summary_jobs(status, available_at, locked_until, id);
            """)

    @staticmethod
    def event_key(event: Mapping[str, Any]) -> str:
        source, external_id = event.get("source"), event.get("external_event_id")
        if not isinstance(source, str) or not source or not isinstance(external_id, str) or not external_id:
            raise ValueError("A stable source and external_event_id are required")
        return f"{source}:{external_id}"

    def enqueue(self, event: Mapping[str, Any], *, now: datetime | None = None) -> tuple[str, bool]:
        key = self.event_key(event)
        occurred_at = event.get("occurred_at")
        if isinstance(occurred_at, str):
            try:
                occurred = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Event occurred_at must be an ISO timestamp") from exc
        elif isinstance(occurred_at, datetime):
            occurred = occurred_at
        else:
            raise ValueError("Event occurred_at must be an ISO timestamp")
        occurred_text = _utc_iso(occurred)
        now_text = _utc_iso(now or datetime.now(timezone.utc))
        event_json = json.dumps(dict(event), default=_json_default, separators=(",", ":"))
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM ring_local_events WHERE source = ? AND external_event_id = ?",
                (event["source"], event["external_event_id"]),
            ).fetchone()
            created = row is None
            if row is None:
                cursor = db.execute(
                    "INSERT INTO ring_local_events(source, external_event_id, occurred_at, event_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (event["source"], event["external_event_id"], occurred_text, event_json, now_text),
                )
                event_id = int(cursor.lastrowid)
            else:
                event_id = int(row["id"])
            db.execute(
                "INSERT OR IGNORE INTO ring_summary_jobs(event_id, processing_version, status, available_at, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?, ?)",
                (event_id, PROCESSING_VERSION, now_text, now_text, now_text),
            )
            db.execute("COMMIT")
            return key, created
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def claim_next(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
        max_attempts: int = 3,
    ) -> ClaimedJob | None:
        if not worker_id or lease_seconds < 1 or not 1 <= max_attempts <= 10:
            raise ValueError("Invalid worker claim configuration")
        instant = now or datetime.now(timezone.utc)
        now_text = _utc_iso(instant)
        lease_text = _utc_iso(instant + timedelta(seconds=lease_seconds))
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """UPDATE ring_summary_jobs SET status='failed', error_category='lease_expired_retries_exhausted',
                   lock_owner=NULL, locked_until=NULL, updated_at=?
                   WHERE status IN ('retrieving','summarizing') AND locked_until <= ? AND attempt_count >= ?""",
                (now_text, now_text, max_attempts),
            )
            row = db.execute(
                """SELECT j.id AS job_id, j.event_id, j.processing_version, j.attempt_count,
                          e.source, e.external_event_id, e.event_json
                   FROM ring_summary_jobs j JOIN ring_local_events e ON e.id=j.event_id
                   WHERE j.attempt_count < ? AND (
                     (j.status IN ('pending','waiting_for_recording') AND j.available_at <= ?)
                     OR (j.status IN ('retrieving','summarizing') AND j.locked_until <= ?)
                   )
                   ORDER BY j.available_at ASC, e.occurred_at ASC, j.id ASC LIMIT 1""",
                (max_attempts, now_text, now_text),
            ).fetchone()
            if row is None:
                db.execute("COMMIT")
                return None
            attempt_count = int(row["attempt_count"]) + 1
            db.execute(
                """UPDATE ring_summary_jobs SET status='retrieving', attempt_count=?, lock_owner=?, locked_until=?,
                   error_category=NULL, updated_at=? WHERE id=?""",
                (attempt_count, worker_id, lease_text, now_text, int(row["job_id"])),
            )
            db.execute("COMMIT")
            return ClaimedJob(
                job_id=int(row["job_id"]),
                event_id=int(row["event_id"]),
                event_key=f"{row['source']}:{row['external_event_id']}",
                worker_id=worker_id,
                attempt_count=attempt_count,
                event=json.loads(row["event_json"]),
                processing_version=str(row["processing_version"]),
            )
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def update_state(
        self,
        job: ClaimedJob,
        status: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
        available_at: datetime | None = None,
        error_category: str | None = None,
    ) -> None:
        if status not in JOB_STATES:
            raise ValueError("Unsupported processing state")
        now_text = _utc_iso(now or datetime.now(timezone.utc))
        retains_lease = status in {"retrieving", "summarizing"}
        owner = job.worker_id if retains_lease else None
        locked_until = _utc_iso((now or datetime.now(timezone.utc)) + timedelta(seconds=lease_seconds)) if retains_lease else None
        available_text = _utc_iso(available_at or now or datetime.now(timezone.utc))
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """UPDATE ring_summary_jobs SET status=?, available_at=?, lock_owner=?, locked_until=?,
                   error_category=?, updated_at=? WHERE id=? AND lock_owner=?""",
                (status, available_text, owner, locked_until, error_category, now_text, job.job_id, job.worker_id),
            )
            if cursor.rowcount != 1:
                db.execute("ROLLBACK")
                raise RuntimeError("Processing lease was lost")
            db.execute("COMMIT")

    def complete(
        self,
        job: ClaimedJob,
        *,
        importance: Mapping[str, Any],
        summary: Mapping[str, Any],
        recording: Mapping[str, Any] | None,
        now: datetime | None = None,
    ) -> None:
        self.finish(
            job,
            status="completed",
            importance=importance,
            summary=summary,
            recording=recording,
            now=now,
        )

    def finish(
        self,
        job: ClaimedJob,
        *,
        status: str,
        importance: Mapping[str, Any],
        summary: Mapping[str, Any] | None,
        recording: Mapping[str, Any] | None,
        error_category: str | None = None,
        now: datetime | None = None,
    ) -> None:
        if status not in {"completed", "unavailable", "failed", "skipped"}:
            raise ValueError("A final processing state is required")
        now_text = _utc_iso(now or datetime.now(timezone.utc))
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """UPDATE ring_summary_jobs SET status=?, importance_json=?, recording_json=?,
                   summary_json=?, lock_owner=NULL, locked_until=NULL, error_category=?, updated_at=?
                   WHERE id=? AND lock_owner=?""",
                (
                    status,
                    json.dumps(dict(importance), separators=(",", ":")),
                    json.dumps(dict(recording), separators=(",", ":")) if recording is not None else None,
                    json.dumps(dict(summary), separators=(",", ":")) if summary is not None else None,
                    error_category,
                    now_text, job.job_id, job.worker_id,
                ),
            )
            if cursor.rowcount != 1:
                db.execute("ROLLBACK")
                raise RuntimeError("Processing lease was lost before result commit")
            db.execute("COMMIT")

    def finish_unavailable(
        self,
        job: ClaimedJob,
        *,
        importance: Mapping[str, Any],
        summary: Mapping[str, Any],
        recording: Mapping[str, Any] | None,
        error_category: str,
        now: datetime | None = None,
    ) -> None:
        now_text = _utc_iso(now or datetime.now(timezone.utc))
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """UPDATE ring_summary_jobs SET status='unavailable', importance_json=?, recording_json=?,
                   summary_json=?, lock_owner=NULL, locked_until=NULL, error_category=?, updated_at=?
                   WHERE id=? AND lock_owner=?""",
                (
                    json.dumps(dict(importance), separators=(",", ":")),
                    json.dumps(dict(recording), separators=(",", ":")) if recording is not None else None,
                    json.dumps(dict(summary), separators=(",", ":")),
                    error_category, now_text, job.job_id, job.worker_id,
                ),
            )
            if cursor.rowcount != 1:
                db.execute("ROLLBACK")
                raise RuntimeError("Processing lease was lost before unavailable result commit")
            db.execute("COMMIT")

    def fail_or_retry(
        self,
        job: ClaimedJob,
        *,
        error_category: str,
        max_attempts: int,
        retry_delay_seconds: int,
        now: datetime | None = None,
        waiting_for_recording: bool = False,
    ) -> str:
        instant = now or datetime.now(timezone.utc)
        state = "waiting_for_recording" if waiting_for_recording else "pending"
        final_state = "failed"
        if job.attempt_count >= max_attempts:
            state = final_state
        available = instant + timedelta(seconds=retry_delay_seconds)
        now_text = _utc_iso(instant)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """UPDATE ring_summary_jobs SET status=?, available_at=?, lock_owner=NULL, locked_until=NULL,
                   error_category=?, updated_at=? WHERE id=? AND lock_owner=?""",
                (state, _utc_iso(available), error_category, now_text, job.job_id, job.worker_id),
            )
            if cursor.rowcount != 1:
                db.execute("ROLLBACK")
                raise RuntimeError("Processing lease was lost")
            db.execute("COMMIT")
        return state

    def get_job(self, event_key: str) -> dict[str, Any] | None:
        try:
            source, external_id = event_key.split(":", 1)
        except ValueError as exc:
            raise ValueError("Malformed event key") from exc
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT e.id AS event_id, e.source, e.external_event_id, e.occurred_at, e.event_json,
                          j.processing_version, j.status, j.attempt_count, j.available_at, j.error_category,
                          j.importance_json, j.recording_json, j.summary_json, j.created_at, j.updated_at
                   FROM ring_local_events e JOIN ring_summary_jobs j ON j.event_id=e.id
                   WHERE e.source=? AND e.external_event_id=? AND j.processing_version=?""",
                (source, external_id, PROCESSING_VERSION),
            ).fetchone()
        if row is None:
            return None
        return {
            "event_id": int(row["event_id"]),
            "event_key": event_key,
            "event": json.loads(row["event_json"]),
            "processing_version": row["processing_version"],
            "status": row["status"],
            "attempt_count": row["attempt_count"],
            "available_at": row["available_at"],
            "error_category": row["error_category"],
            "importance": json.loads(row["importance_json"]) if row["importance_json"] else None,
            "recording": json.loads(row["recording_json"]) if row["recording_json"] else None,
            "summary": json.loads(row["summary_json"]) if row["summary_json"] else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def recent_events(self, event: Mapping[str, Any], *, window_seconds: int = 600) -> list[dict[str, Any]]:
        occurred = event.get("occurred_at")
        if isinstance(occurred, str):
            timestamp = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
        elif isinstance(occurred, datetime):
            timestamp = occurred
        else:
            return []
        if timestamp.tzinfo is None:
            return []
        timestamp = timestamp.astimezone(timezone.utc)
        start, end = _utc_iso(timestamp - timedelta(seconds=window_seconds)), _utc_iso(timestamp + timedelta(seconds=window_seconds))
        with closing(self._connect()) as db:
            all_rows = db.execute(
                """SELECT event_json FROM ring_local_events WHERE source=? AND occurred_at >= ? AND occurred_at <= ?""",
                (event.get("source"), start, end),
            ).fetchall()
        recent = [json.loads(row["event_json"]) for row in all_rows]
        return [item for item in recent if item.get("device_id") == event.get("device_id")]

    def list_timeline(
        self,
        day: date,
        *,
        timezone_name: str = "UTC",
        sort: str = "time",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        if sort not in {"time", "importance"}:
            raise ValueError("sort must be 'time' or 'importance'")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination")
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown timezone") from exc
        start_local = datetime.combine(day, time.min, zone)
        end_local = datetime.combine(day + timedelta(days=1), time.min, zone)
        start_utc, end_utc = _utc_iso(start_local), _utc_iso(end_local)
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT e.source, e.external_event_id, e.occurred_at, e.event_json,
                          j.status, j.importance_json, j.recording_json, j.summary_json
                   FROM ring_local_events e LEFT JOIN ring_summary_jobs j ON j.event_id=e.id
                   WHERE e.occurred_at >= ? AND e.occurred_at < ?
                   ORDER BY e.occurred_at DESC, e.id DESC""",
                (start_utc, end_utc),
            ).fetchall()
        items = []
        for row in rows:
            rank = json.loads(row["importance_json"]) if row["importance_json"] else None
            items.append({
                "event": json.loads(row["event_json"]),
                "status": row["status"] or "pending",
                "importance": rank,
                "recording": json.loads(row["recording_json"]) if row["recording_json"] else None,
                "summary": json.loads(row["summary_json"]) if row["summary_json"] else None,
            })
        if sort == "importance":
            def tie_break(item: dict[str, Any]) -> float:
                occurred = item["event"].get("occurred_at", "")
                try:
                    parsed = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
                    return parsed.timestamp()
                except (AttributeError, TypeError, ValueError, OverflowError):
                    return float("-inf")

            items.sort(key=lambda item: (
                -(item["importance"] or {}).get("importance_score", -1),
                -tie_break(item),
                item["event"].get("external_event_id", ""),
            ))
        total = len(items)
        return {
            "day": day.isoformat(),
            "timezone": timezone_name,
            "sort": sort,
            "items": items[offset:offset + limit],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def close(self) -> None:
        """Connections are short-lived; this method is for context-manager symmetry."""
        return None
