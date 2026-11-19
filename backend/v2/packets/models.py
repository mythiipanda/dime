from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Citation(Model):
    source_table: str
    table: str
    columns: list[str]
    season: str
    sql: str
    params: list[Any]
    fetched_at: str | None = None
    source: str | None = None
    row_key: dict[str, Any]
    salary_vintage: dict[str, Any] | None = None
    supporting_cites: list[str] = Field(default_factory=list)
    transformation: str | None = None


class Kpi(Model):
    label: str
    value: float | str | None
    unit: str
    display: str
    cite: str | None = None
    null_reason: str | None = None
    context: str | None = None


class Kpis(Model):
    type: Literal["kpis"] = "kpis"
    items: list[Kpi]


class Column(Model):
    key: str
    label: str
    unit: str | None = None


class Table(Model):
    type: Literal["table"] = "table"
    columns: list[Column]
    rows: list[dict[str, Any]]
    cites: dict[str, str]
    note: str | None = None


class Series(Model):
    key: str
    label: str


class Chart(Model):
    type: Literal["chart"] = "chart"
    chart: Literal["bar", "line"]
    x: str
    series: list[Series]
    data: list[dict[str, Any]]
    cite: str | None = None


class Text(Model):
    type: Literal["text"] = "text"
    md: str
    cites: list[str]


class Callout(Model):
    type: Literal["callout"] = "callout"
    tone: Literal["info", "warn"] = "info"
    md: str


Block = Annotated[Kpis | Table | Chart | Text | Callout, Field(discriminator="type")]


class Section(Model):
    id: str
    title: str
    summary: str | None = None
    blocks: list[Block]


class Claim(Model):
    md: str = Field(max_length=10000)
    cites: list[str] = Field(default_factory=list, max_length=100)


class Narrative(Model):
    status: Literal["none", "draft", "ready"] = "none"
    generated_by: str | None = None
    generated_at: datetime | None = None
    summary: list[Claim] = Field(default_factory=list, max_length=100)
    recommendation: list[Claim] = Field(default_factory=list, max_length=100)


class Packet(Model):
    id: UUID
    kind: Literal["player_deep_dive", "trade_evaluation"]
    title: str
    subtitle: str
    season: str
    generated_at: datetime
    inputs: dict[str, Any]
    sections: list[Section]
    citations: dict[str, Citation]
    limitations: list[str]
    narrative: Narrative | None = None
