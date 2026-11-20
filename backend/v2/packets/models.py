from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def format_value(value, unit=None):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if not isinstance(value, (int, float)):
        return str(value)
    if unit in ("count", "years"):
        return f"{value:,.0f}"
    if unit == "usd":
        sign = "-" if value < 0 else ""
        return f"{sign}${abs(value)/1_000_000:,.1f}M" if abs(value) >= 1_000_000 else f"{sign}${abs(value):,.0f}"
    if unit == "pct":
        return f"{value:.1f}%"
    if unit == "percentage_points":
        return f"{value:+.1f} pp"
    if unit in ("rating", "points_per_100_possessions"):
        return f"{value:+.1f}"
    return f"{value:.1f}"


UNITS = {"age": "years", "gp": "count", "g": "count", "n": "count", "fga": "count",
         "percentile": "pct", "share": "pct", "league_share": "pct", "fg_pct": "pct",
         "league_fg_pct": "pct", "ts_pct": "pct", "usg_pct": "pct", "pie": "pct",
         "net_rating": "rating", "rapm": "points_per_100_possessions",
         "share_delta": "percentage_points", "efficiency_delta": "percentage_points"}


def display_rows(rows, units):
    return [{key: {"provider_stat":"Provider units", "pct":"Percent", "rating":"Points per 100 possessions"}.get(value, value) if key == "unit" and isinstance(value, str) else format_value(value, "percentage_points" if key == "On-Off" and row.get("unit") == "pct" else units.get(key) or row.get("unit") or UNITS.get(key.lower()))
             for key, value in row.items()} for row in rows]


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

    @model_validator(mode="after")
    def formatted(self):
        self.display = format_value(self.value, self.unit)
        return self


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
    title: str | None = None
    collapsed: bool = False
    display_rows: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def formatted(self):
        self.columns = [c for c in self.columns if not c.key.lower().endswith("_id") and c.key.lower() != "id"]
        self.rows = [{k: v for k, v in row.items() if not k.lower().endswith("_id") and k.lower() != "id"} for row in self.rows]
        self.display_rows = display_rows(self.rows, {c.key: c.unit for c in self.columns})
        return self


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
    display_data: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def formatted(self):
        self.display_data = display_rows(self.data, {})
        return self


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
