import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools.league import get_clutch, get_situational_splits

SEASON = "2022-23"


def _clutch_rows(season, seconds, margin, season_type):
    con = store.connect(read_only=True)
    try:
        return con.execute(
            "SELECT game_id, action_number, clock, period, team_tricode,"
            " person_id, player_name, location, score_home, score_away,"
            " action_type, sub_type, description, shot_value, shot_result,"
            " is_field_goal FROM silver_hist_pbp"
            " WHERE _season = ? AND period >= 4 ORDER BY game_id, action_number",
            [season],
        ).fetchall()
    finally:
        con.close()


def _parse_clock(clock):
    s = str(clock)
    if not s.startswith("PT") or not s.endswith("S"):
        return None
    bar = s.index("M")
    return int(s[2:bar]) * 60.0 + float(s[bar + 1:-1])


def _fold(rows, seconds, margin, prefixes):
    home_of = {}
    votes = {}
    for r in rows:
        if (r[7] or "") == "h" and r[4]:
            votes.setdefault(r[0], {}).setdefault(str(r[4]), 0)
            votes[r[0]][str(r[4])] += 1
    for gid, tally in votes.items():
        home_of[gid] = max(tally.items(), key=lambda kv: kv[1])[0]
    final = {}
    lead = {}
    for r in rows:
        gid = r[0]
        if gid not in home_of:
            continue
        if str(gid)[0:3] not in prefixes:
            continue
        sh, sa = r[8], r[9]
        try:
            if sh not in (None, ""):
                lead_home = int(str(sh))
            else:
                lead_home = None
        except (TypeError, ValueError):
            lead_home = None
        try:
            if sa not in (None, ""):
                lead_away = int(str(sa))
            else:
                lead_away = None
        except (TypeError, ValueError):
            lead_away = None
        cur = lead.get(gid)
        if lead_home is not None and lead_away is not None:
            cur = (lead_home, lead_away)
            lead[gid] = cur
        if cur is None:
            continue
        left = _parse_clock(r[2])
        if left is None:
            continue
        sec = left if int(r[3]) > 4 else left
        gap = abs(cur[0] - cur[1])
        if sec <= seconds and gap <= margin:
            final.setdefault(gid, []).append(r)
    return final, home_of


def test_hist_player_clutch_matches_independent_fold():
    out = get_clutch.invoke(
        {"scope": "player", "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})
    assert out["ok"] is True
    assert out["meta"]["source"] == "warehouse:silver_hist_pbp"
    assert out["meta"]["clutch_definition"] == {
        "seconds": 300, "margin": 5, "season_type": "regular"}
    top = out["rows"][0]
    rows = _clutch_rows(SEASON, 300, 5, {"002"})
    events, _ = _fold(rows, 300, 5, {"002"})
    pts = fgm = fga = 0
    for gid, evts in events.items():
        for r in evts:
            if int(r[5] or 0) != int(top["PLAYER_ID"]):
                continue
            if r[10] == "Made Shot":
                pts += int(r[13] or 0)
                fgm += 1
                fga += 1
            elif r[10] == "Missed Shot":
                fga += 1
            elif r[10] == "Free Throw" and not str(r[12] or "").startswith("MISS"):
                pts += 1
    assert top["PTS"] == pts
    assert top["FG_PCT"] == round(fgm / fga, 3)


def test_tighter_definition_shrinks_output():
    wide = get_clutch.invoke(
        {"scope": "player", "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})
    tight = get_clutch.invoke(
        {"scope": "player", "season": SEASON,
         "clutch_seconds": 60, "clutch_margin": 3,
         "season_type": "regular"})
    assert wide["ok"] is True and tight["ok"] is True
    assert tight["meta"]["clutch_definition"] == {
        "seconds": 60, "margin": 3, "season_type": "regular"}
    wide_pts = sum(r["PTS"] for r in wide["rows"])
    tight_pts = sum(r["PTS"] for r in tight["rows"])
    assert tight_pts < wide_pts
    assert len(tight["rows"]) <= len(wide["rows"])


def test_season_type_playoffs_isolates_postseason():
    reg = get_clutch.invoke(
        {"scope": "player", "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})
    po = get_clutch.invoke(
        {"scope": "player", "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "playoffs"})
    assert reg["ok"] is True and po["ok"] is True
    assert reg["meta"]["games"] > po["meta"]["games"]
    assert po["meta"]["clutch_definition"]["season_type"] == "playoffs"


def test_pre_pbp_season_returns_honest_gap():
    out = get_clutch.invoke(
        {"scope": "player", "season": "2015-16",
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})
    assert out["ok"] is False
    assert "2020-21" in out["error"] and "2024-25" in out["error"]


def test_current_season_reads_silver_clutch():
    out = get_clutch.invoke({"scope": "player", "season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"].get("source") != "warehouse:silver_hist_pbp"
    assert len(out["rows"]) > 0


def test_team_scope_hist_derivation_sorts_by_pts():
    out = get_clutch.invoke(
        {"scope": "team", "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})
    assert out["ok"] is True
    assert out["meta"]["source"] == "warehouse:silver_hist_pbp"
    assert len(out["rows"]) > 20
    pts = [r["PTS"] for r in out["rows"]]
    assert pts == sorted(pts, reverse=True)
    assert all(r["TEAM_ABBREVIATION"] for r in out["rows"])


def test_situational_splits_reconcile_to_overall():
    top = get_clutch.invoke(
        {"scope": "player", "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})["rows"][0]
    out = get_situational_splits.invoke(
        {"scope": "player", "entity": top["PLAYER_NAME"], "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})
    assert out["ok"] is True
    overall = next(r for r in out["rows"]["splits"] if r["split"] == "overall")
    assert overall["PTS"] == top["PTS"]
    for group in ("ahead", "tied", "behind"):
        group_rows = [r for r in out["rows"]["splits"]
                       if r["split"].startswith(group)]
        assert group_rows
    states = [r for r in out["rows"]["splits"]
              if r["split"] in ("ahead", "tied", "behind")]
    assert sum(r["PTS"] for r in states) == overall["PTS"]
    assert sum(r["FGA"] for r in states) == overall["FGA"]
    venues = [r for r in out["rows"]["splits"] if r["split"] in ("home", "away")]
    assert sum(r["PTS"] for r in venues) == overall["PTS"]


def test_situational_team_splits_cover_entry_states():
    out = get_situational_splits.invoke(
        {"scope": "team", "entity": "BOS", "season": SEASON,
         "clutch_seconds": 300, "clutch_margin": 5,
         "season_type": "regular"})
    assert out["ok"] is True
    assert out["rows"]["team"] == "BOS"
    overall = next(r for r in out["rows"]["splits"] if r["split"] == "overall")
    states = [r for r in out["rows"]["splits"]
              if r["split"] in ("ahead", "tied", "behind")]
    assert sum(r["PTS"] for r in states) == overall["PTS"]
    assert overall["GP"] > 10
