"""Diagnosis History CRUD API — JSON file persistence."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/history", tags=["History"])

MAX_RECORDS = 200


def _success(data: Any, msg: str = "success") -> dict:
    return {"code": 0, "data": data, "msg": msg}


def _error(code: int, msg: str) -> JSONResponse:
    return JSONResponse(status_code=code, content={"code": code, "data": None, "msg": msg})


class HistoryStore:
    """Thread-safe JSON file store for diagnosis records."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._records: list[dict[str, Any]] = []

    async def load(self) -> None:
        async with self._lock:
            if self.file_path.exists():
                with open(self.file_path, encoding="utf-8") as f:
                    data = json.load(f)
                self._records = data if isinstance(data, list) else []
            else:
                self._records = []

    def _save_unlocked(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, ensure_ascii=False, indent=2)

    def _sort_and_prune_unlocked(self) -> None:
        self._records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        if len(self._records) > MAX_RECORDS:
            self._records = self._records[:MAX_RECORDS]

    async def list_records(self) -> list[dict[str, Any]]:
        async with self._lock:
            return sorted(
                self._records,
                key=lambda r: r.get("timestamp", ""),
                reverse=True,
            )

    async def get_record(self, record_id: str) -> dict[str, Any] | None:
        async with self._lock:
            for record in self._records:
                if record.get("id") == record_id:
                    return record
            return None

    async def create_record(self, record: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            record_id = record.get("id")
            if not record_id:
                raise ValueError("Record must include an id")

            for existing in self._records:
                if existing.get("id") == record_id:
                    return existing

            self._records.append(record)
            self._sort_and_prune_unlocked()
            self._save_unlocked()
            return record

    async def delete_record(self, record_id: str) -> bool:
        async with self._lock:
            before = len(self._records)
            self._records = [r for r in self._records if r.get("id") != record_id]
            if len(self._records) < before:
                self._save_unlocked()
                return True
            return False


def _get_store(request: Request) -> HistoryStore:
    return request.app.state.history_store


@router.get("")
async def list_history(request: Request):
    """List all diagnosis records, sorted by timestamp descending."""
    store = _get_store(request)
    records = await store.list_records()
    return _success(records)


@router.get("/{record_id}")
async def get_history_record(record_id: str, request: Request):
    """Get a single diagnosis record by id."""
    store = _get_store(request)
    record = await store.get_record(record_id)
    if record is None:
        return _error(404, f"Record not found: {record_id}")
    return _success(record)


@router.post("")
async def create_history_record(request: Request):
    """Create a diagnosis record (idempotent by record.id)."""
    store = _get_store(request)
    try:
        record = await request.json()
    except Exception:
        return _error(400, "Invalid JSON body")

    if not isinstance(record, dict) or not record.get("id"):
        return _error(400, "Record must be a JSON object with an id field")

    try:
        created = await store.create_record(record)
    except ValueError as exc:
        return _error(400, str(exc))

    return _success(created)


@router.delete("/{record_id}")
async def delete_history_record(record_id: str, request: Request):
    """Delete a diagnosis record by id."""
    store = _get_store(request)
    deleted = await store.delete_record(record_id)
    if not deleted:
        return _error(404, f"Record not found: {record_id}")
    return _success(None)
