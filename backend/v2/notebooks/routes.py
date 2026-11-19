from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import runner, sql
from .store import ConflictError, NotebookInput, NotebookStore, NotebookUpdate, ipynb

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


def store() -> NotebookStore:
    return NotebookStore(Path(os.environ.get("DIME_NOTEBOOK_DIR") or
                              Path(__file__).resolve().parents[2] / "data" / "notebooks"))


class SQLBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sql: str = Field(min_length=1, max_length=100_000)
    params: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=100)
    page: int = Field(default=0, ge=0)
    page_size: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def bounded_page(self):
        if self.page * self.page_size >= 5000:
            raise ValueError("Pages are limited to the first 5000 rows")
        return self


class PythonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=100_000)
    timeout_s: float = Field(default=30, gt=0, le=60, allow_inf_nan=False)


@router.get("/capabilities")
def capabilities():
    return {"python": {"enabled": runner.enabled(), "trusted_local_only": True,
                       "message": "Trusted local Python only. Enable with DIME_NOTEBOOK_PYTHON=1; this is not a security sandbox."},
            "sql": {"page_size_max": 500, "row_cap": 5000, "timeout_s": 30}}


@router.post("/sql")
def execute_sql(body: SQLBody):
    try:
        return sql.execute(body.sql, body.params, body.page, body.page_size)
    except TimeoutError as exc:
        raise HTTPException(408, str(exc)) from exc
    except (ValueError, duckdb.BinderException, duckdb.ParserException, duckdb.InvalidInputException) as exc:
        raise HTTPException(400, str(exc)[:1000]) from exc
    except (ImportError, OSError, duckdb.Error) as exc:
        raise HTTPException(503, "Notebook warehouse query unavailable") from exc


@router.post("/python")
def execute_python(body: PythonBody):
    if not runner.enabled():
        raise HTTPException(403, "Python execution is disabled. For trusted local notebooks only, set DIME_NOTEBOOK_PYTHON=1 on the backend.")
    return runner.run(body.source, body.timeout_s)


def storage_call(method, *args):
    try:
        return method(*args)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Notebook not found") from exc
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("")
def list_notebooks():
    return {"notebooks": storage_call(store().list)}


@router.post("", status_code=201)
def create_notebook(body: NotebookInput):
    return storage_call(store().create, body)


@router.get("/{notebook_id}/export")
def export_notebook(notebook_id: str, fmt: Literal["ipynb", "json"] = Query(default="ipynb")):
    notebook = storage_call(store().get, notebook_id)
    return JSONResponse(ipynb(notebook) if fmt == "ipynb" else notebook,
                        headers={"Content-Disposition": f'attachment; filename="{notebook["id"]}.{fmt}"'})


@router.get("/{notebook_id}")
def get_notebook(notebook_id: str):
    return storage_call(store().get, notebook_id)


@router.put("/{notebook_id}")
def update_notebook(notebook_id: str, body: NotebookUpdate):
    return storage_call(store().update, notebook_id, body)


@router.delete("/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: str):
    storage_call(store().delete, notebook_id)
    return Response(status_code=204)
