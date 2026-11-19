from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

OUTPUT_CAP = 256 * 1024
_LOCK = RLock()
_ID = re.compile(r"^[0-9a-f]{32}$")


class Cell(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[0-9a-f]{32}$")
    kind: Literal["markdown", "sql", "python"]
    source: str = Field(default="", max_length=100_000)
    outputs: Any = None
    executed_at: datetime | None = None


class Origin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["chat", "board"]
    ref: str = Field(min_length=1, max_length=256)


class NotebookInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled notebook", min_length=1, max_length=160)
    cells: list[Cell] = Field(default_factory=list, max_length=100)
    origin: Origin | None = None


class NotebookUpdate(NotebookInput):
    version: int = Field(ge=1)


class ConflictError(Exception):
    pass


def _bounded(value: Any) -> Any:
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(raw.encode()) <= OUTPUT_CAP:
        return value
    count = None
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        count = value.get("row_count", len(value["rows"]))
        preview = {**value, "rows": value["rows"][:20], "row_count": count, "truncated": True}
        if len(json.dumps(preview, ensure_ascii=False).encode()) <= OUTPUT_CAP:
            return preview
    if isinstance(value, dict) and isinstance(value.get("tables"), list):
        preview = {**value, "tables": [_bounded(table) for table in value["tables"][:4]],
                   "figures": [], "truncated": True}
        for table in preview["tables"]:
            if isinstance(table, dict) and isinstance(table.get("rows"), list):
                table["row_count"] = table.get("row_count", len(table["rows"]))
                table["rows"] = table["rows"][:20]
                table["truncated"] = True
        if len(json.dumps(preview, ensure_ascii=False).encode()) <= OUTPUT_CAP:
            return preview
    return {"preview": raw[:4096], "row_count": count, "truncated": True}


class NotebookStore:
    def __init__(self, directory: Path):
        self.directory = directory

    def _path(self, notebook_id: str) -> Path:
        if not _ID.fullmatch(notebook_id):
            raise FileNotFoundError("Notebook not found")
        path = self.directory / f"{notebook_id}.json"
        if path.is_symlink():
            raise FileNotFoundError("Notebook not found")
        return path

    @contextmanager
    def _locked(self):
        with _LOCK:
            if any(p.is_symlink() for p in (self.directory, *self.directory.parents)):
                raise ValueError("Notebook directory cannot be a symlink")
            self.directory.mkdir(parents=True, exist_ok=True)
            lock_path = self.directory / ".lock"
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "a") as handle:
                try:
                    import fcntl
                except ImportError:
                    fcntl = None
                if fcntl:
                    fcntl.flock(handle, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl:
                        fcntl.flock(handle, fcntl.LOCK_UN)

    def _read(self, notebook_id: str) -> dict:
        return json.loads(self._path(notebook_id).read_text())

    def _write(self, notebook: dict) -> dict:
        for cell in notebook["cells"]:
            cell["outputs"] = _bounded(cell.get("outputs"))
        ids = [cell["id"] for cell in notebook["cells"]]
        if len(ids) != len(set(ids)):
            raise ValueError("Cell ids must be unique")
        fd, name = tempfile.mkstemp(prefix=".notebook-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(notebook, handle, ensure_ascii=False, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self._path(notebook["id"]))
        finally:
            Path(name).unlink(missing_ok=True)
        return notebook

    def list(self) -> list[dict]:
        with self._locked():
            docs = [self._read(p.stem) for p in self.directory.glob("*.json") if _ID.fullmatch(p.stem) and not p.is_symlink()]
            return sorted(docs, key=lambda d: d["updated_at"], reverse=True)

    def get(self, notebook_id: str) -> dict:
        with self._locked():
            return self._read(notebook_id)

    def create(self, body: NotebookInput) -> dict:
        now = datetime.now(UTC).isoformat()
        with self._locked():
            return self._write({**body.model_dump(mode="json"), "id": uuid4().hex,
                                "version": 1, "created_at": now, "updated_at": now})

    def update(self, notebook_id: str, body: NotebookUpdate) -> dict:
        with self._locked():
            current = self._read(notebook_id)
            if current["version"] != body.version:
                raise ConflictError("Notebook changed; reload before saving")
            return self._write({**current, **body.model_dump(mode="json"),
                                "version": body.version + 1, "updated_at": datetime.now(UTC).isoformat()})

    def delete(self, notebook_id: str) -> None:
        with self._locked():
            self._path(notebook_id).unlink()


def ipynb(notebook: dict) -> dict:
    cells = []
    for cell in notebook["cells"]:
        markdown = cell["kind"] == "markdown"
        source = ("%%sql\n" if cell["kind"] == "sql" else "") + cell["source"]
        output = cell.get("outputs")
        snapshot_source = None
        if markdown and isinstance(output, dict) and output.get("kind") == "snapshot":
            data = output.get("data", {})
            names = [column["name"] for column in data.get("columns", [])]
            def scalar(value):
                rendered = "—" if value is None else json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
                return rendered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\\", "&#92;").replace("|", "&#124;").replace("`", "&#96;").replace("\r", "").replace("\n", "<br>")
            snapshot_source = f"Cached snapshot · from answer · {notebook['created_at']}\n\n"
            if names:
                lines = [" | ".join(scalar(name) for name in names), " | ".join("---" for _ in names)]
                lines.extend(" | ".join(scalar(row.get(name)) for name in names) for row in data.get("rows", []))
                snapshot_source += "\n".join(f"| {line} |" for line in lines)
            else:
                snapshot_source += "No columns recorded."
            if data.get("truncated"):
                snapshot_source += "\n\nBounded preview of the original answer table."
        item = {"id": cell["id"], "cell_type": "markdown" if markdown else "code", "metadata": {}, "source": source.splitlines(keepends=True)}
        if not markdown:
            item.update(execution_count=None, outputs=[])
        cells.append(item)
        if snapshot_source is not None:
            cells.append({"id": f'{cell["id"]}-snapshot', "cell_type": "markdown", "metadata": {}, "source": snapshot_source.splitlines(keepends=True)})
    return {"nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}, "cells": cells}
