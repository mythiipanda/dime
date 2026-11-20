from typing import Annotated

import duckdb
from fastapi import APIRouter, HTTPException
from pydantic import Field

from shared import store
from v2.boards.service import Season
from .deep_dive import build_packet
from .models import Model, Narrative, Packet
from .narrative import validate_narrative
from .trade import build_trade


router = APIRouter(prefix="/packets", tags=["packets"])


class DeepDiveBody(Model):
    player: Annotated[str, Field(min_length=1, max_length=200)] | Annotated[int, Field(strict=True, gt=0)]
    season: Season = "2025-26"


class NarrativeBody(Model):
    packet: Packet
    narrative: Narrative


Player = Annotated[str, Field(min_length=1, max_length=200)] | Annotated[int, Field(strict=True, gt=0)]


class TradeBody(Model):
    team_a: str = Field(min_length=1,max_length=100)
    team_b: str = Field(min_length=1,max_length=100)
    a_sends: list[Player] = Field(max_length=15)
    b_sends: list[Player] = Field(max_length=15)
    season: Season = "2025-26"
    notes: str | None = Field(default=None,max_length=10000)


@router.post("/trade_evaluation", response_model=Packet)
def trade_evaluation(body: TradeBody):
    try:
        con = store.connect(read_only=True)
        try:
            return build_trade(con,body.team_a,body.team_b,body.a_sends,body.b_sends,body.season,body.notes)
        finally:
            con.close()
    except (duckdb.IOException, duckdb.ConnectionException) as exc:
        raise HTTPException(503,detail="Packets warehouse unavailable") from exc


@router.post("/player_deep_dive", response_model=Packet)
def player_deep_dive(body: DeepDiveBody):
    try:
        con = store.connect(read_only=True)
        try:
            return build_packet(con, body.player, body.season)
        finally:
            con.close()
    except (duckdb.IOException, duckdb.ConnectionException) as exc:
        raise HTTPException(503, detail="Packets warehouse unavailable") from exc


@router.post("/narrative")
def narrative(body: NarrativeBody):
    accepted, rejected = validate_narrative(body.packet, body.narrative)
    return {"packet_with_narrative": body.packet.model_copy(update={"narrative": accepted}), "rejected": rejected}
