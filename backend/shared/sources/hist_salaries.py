import csv
import io
import unicodedata

import polars as pl

from .base import FetchMeta, FetchResult, safe

SOURCE = "hoopshype:datadavis-mirror"
SEASON = "1984-2018"

SALARIES_URLS = (
    "https://raw.githubusercontent.com/carlosfrev123/CS3-NBA_3_pointers/main/DATA/salaries_1985to2018.csv",
    "https://raw.githubusercontent.com/elliottwhite35/elliottwhite35.github.io/main/resources/salaries_1985to2018.csv",
)
PLAYERS_URLS = (
    "https://raw.githubusercontent.com/carlosfrev123/CS3-NBA_3_pointers/main/DATA/players.csv",
    "https://raw.githubusercontent.com/elliottwhite35/elliottwhite35.github.io/main/resources/players.csv",
)

HEADERS = {"User-Agent": "Mozilla/5.0"}

TEAM_ABBR = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Bobcats": "CHO",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Kansas City Kings": "KCK",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Jersey Nets": "NJN",
    "New Orleans Hornets": "NOH",
    "New Orleans Pelicans": "NOP",
    "New Orleans/Oklahoma City Hornets": "NOK",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Seattle SuperSonics": "SEA",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Vancouver Grizzlies": "VAN",
    "Washington Bullets": "WSB",
    "Washington Wizards": "WAS",
}


def _fold(name: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(name or ""))
        if not unicodedata.combining(c)
    ).strip()


def team_abbr(name: str, season_start: int) -> str | None:
    name = (name or "").strip()
    if name == "Charlotte Hornets":
        return "CHO" if season_start <= 2001 else "CHA"
    return TEAM_ABBR.get(name)


def _fetch(urls: tuple[str, ...]) -> str:
    import httpx
    last: Exception | None = None
    for url in urls:
        try:
            res = httpx.get(url, headers=HEADERS, timeout=60,
                            follow_redirects=True)
            if res.status_code == 200 and len(res.content) > 1_000:
                return res.text
            last = RuntimeError(f"{url} -> {res.status_code}")
        except Exception as exc:
            last = exc
    raise last or RuntimeError("no mirror available")


def parse_rows(salaries_text: str, players_text: str) -> list[dict]:
    names = {
        r["player_id"]: _fold(r["name"])
        for r in csv.DictReader(io.StringIO(players_text))
        if r.get("player_id")
    }
    rows = []
    for rec in csv.DictReader(io.StringIO(salaries_text)):
        if rec.get("league") != "NBA":
            continue
        try:
            salary = int(rec["salary"])
            year = int(rec["season_start"])
        except (TypeError, ValueError):
            continue
        team = (rec.get("team") or "").strip()
        rows.append({
            "PLAYER_ID": rec["player_id"],
            "PLAYER_NAME": names.get(rec["player_id"]),
            "SEASON_YEAR": year,
            "SEASON": rec["season"],
            "TEAM_NAME": team or None,
            "TEAM_ABBREVIATION": team_abbr(team, year) if team else None,
            "SALARY": salary,
        })
    return rows


def _run() -> pl.DataFrame:
    salaries_text = _fetch(SALARIES_URLS)
    players_text = _fetch(PLAYERS_URLS)
    return pl.DataFrame(parse_rows(salaries_text, players_text),
                        infer_schema_length=None)


def history() -> FetchResult:
    return safe(SOURCE, SEASON, _run)
