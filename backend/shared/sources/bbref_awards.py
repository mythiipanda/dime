import re
import time
from dataclasses import dataclass

import polars as pl
import requests
from lxml import etree, html as lxml_html

from .base import FetchMeta, FetchResult

SOURCE = "basketball-reference"
AWARDS_INDEX_URL = "https://www.basketball-reference.com/awards/"
SEASON_URL = "https://www.basketball-reference.com/awards/awards_%d.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 "
                  "Safari/537.36",
    "Accept": "text/html,*/*",
    "Referer": "https://www.basketball-reference.com/awards/",
}
REQUESTS_PER_MINUTE_LIMIT = 20
MIN_INTERVAL_S = 3.2
TIMEOUT_S = 30
ATTEMPTS = 4
BACKOFF_S = 30.0

_RESULT_STATS = ("team_id", "points_won", "points_max", "award_share")
VOTE_OUT_COLUMNS = ("VOTES_FIRST", "VOTES_SECOND", "VOTES_THIRD")


class AwardsPageError(RuntimeError):
    pass


class Throttled(RuntimeError):
    pass


@dataclass(frozen=True)
class AwardSection:
    table_id: str
    award: str
    name_stat: str
    rank_stat: str | None
    team_stat: str | None
    vote_stats: tuple[str | None, ...]
    first_year: int

    @property
    def ordinal_stat(self) -> str:
        return self.rank_stat or self.team_stat or ""

    @property
    def required_stats(self) -> tuple[str, ...]:
        declared = [self.name_stat, self.ordinal_stat, *_RESULT_STATS]
        declared += [stat for stat in self.vote_stats if stat]
        return tuple(sorted(set(declared)))


AWARD_SECTIONS: tuple[AwardSection, ...] = (
    AwardSection("mvp", "MVP", "player", "rank", None,
                 ("votes_first", None, None), 1955),
    AwardSection("roy", "ROY", "player", "rank", None,
                 ("votes_first", None, None), 1962),
    AwardSection("dpoy", "DPOY", "player", "rank", None,
                 ("votes_first", None, None), 1982),
    AwardSection("smoy", "6MOY", "player", "rank", None,
                 ("votes_first", None, None), 1982),
    AwardSection("mip", "MIP", "player", "rank", None,
                 ("votes_first", None, None), 1985),
    AwardSection("coy", "COY", "coach", "rank", None,
                 ("votes_first", None, None), 1962),
    AwardSection("leading_all_nba", "ALL_NBA", "player", None, "all_nba_team",
                 ("first_team_votes", "second_team_votes",
                  "third_team_votes"), 1955),
    AwardSection("leading_all_defense", "ALL_DEFENSE", "player", None,
                 "all_defense_team", (None, None, None), 1955),
    AwardSection("leading_all_rookie", "ALL_ROOKIE", "player", None,
                 "all_rookie_team",
                 ("first_team_votes", "second_team_votes", None), 1962),
)

SCHEMA = {
    "SEASON": pl.String,
    "AWARD": pl.String,
    "RANK": pl.Int64,
    "RANK_LABEL": pl.String,
    "PLAYER": pl.String,
    "COACH": pl.String,
    "AGE": pl.Int64,
    "TEAM": pl.String,
    "POINTS_WON": pl.Int64,
    "POINTS_MAX": pl.Int64,
    "AWARD_SHARE": pl.Float64,
    "VOTES_FIRST": pl.Int64,
    "VOTES_SECOND": pl.Int64,
    "VOTES_THIRD": pl.Int64,
    "SOURCE_URL": pl.String,
}
COLUMNS = list(SCHEMA)


def season_label(year: int) -> str:
    start = int(year) - 1
    return "%d-%02d" % (start, (start + 1) % 100)


def season_year(season: str) -> int:
    match = re.fullmatch(r"(\d{4})-(\d{2})", str(season).strip())
    if not match:
        raise ValueError(f"season '{season}' is not in YYYY-YY form")
    start = int(match.group(1))
    if int(match.group(2)) != (start + 1) % 100:
        raise ValueError(f"season '{season}' does not roll over the century")
    return start + 1


def season_url(year: int) -> str:
    return SEASON_URL % int(year)


def published_years(text: str) -> list[int]:
    years = sorted({int(found) for found
                    in re.findall(r"/awards/awards_(\d{4})\.html", text)})
    if not years:
        raise AwardsPageError(
            f"{AWARDS_INDEX_URL} listed no per-season awards pages")
    return years


def parse_season_page(text: str, year: int) -> pl.DataFrame:
    label = season_label(year)
    url = season_url(year)
    doc = _document(text, label)
    _assert_page_season(doc, label)
    tables = _award_tables(doc)
    rows: list[dict] = []
    for section in AWARD_SECTIONS:
        table = tables.get(section.table_id)
        if table is None:
            if int(year) >= section.first_year:
                raise AwardsPageError(
                    f"season {label}: award {section.award} ballot "
                    f"'{section.table_id}' missing from {url}")
            continue
        parsed = _section_rows(section, table, label, url)
        if not parsed:
            raise AwardsPageError(
                f"season {label}: award {section.award} ballot "
                f"'{section.table_id}' held no rows at {url}")
        rows.extend(parsed)
    return pl.DataFrame(rows, schema=SCHEMA).sort(
        ["SEASON", "AWARD", "RANK", "PLAYER"])


def fetch_season(year: int, transport=None,
                 min_interval_s: float = MIN_INTERVAL_S,
                 backoff_s: float = BACKOFF_S, attempts: int = ATTEMPTS
                 ) -> FetchResult:
    get = transport or paced_transport(min_interval_s)
    url = season_url(year)
    throttled: Throttled | None = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(backoff_s * attempt)
        try:
            text = get(url)
        except Throttled as exc:
            throttled = exc
            continue
        return FetchResult(frame=parse_season_page(text, year),
                           meta=FetchMeta(SOURCE, season_label(year)))
    raise throttled or Throttled(url)


def fetch_index(transport=None) -> list[int]:
    get = transport or paced_transport()
    return published_years(get(AWARDS_INDEX_URL))


def paced_transport(min_interval_s: float = MIN_INTERVAL_S):
    last_request = [0.0]

    def get(url: str) -> str:
        wait = min_interval_s - (time.monotonic() - last_request[0])
        if wait > 0:
            time.sleep(wait)
        last_request[0] = time.monotonic()
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S)
        if response.status_code == 429:
            raise Throttled(url)
        response.raise_for_status()
        return response.content.decode("utf-8")

    return get


def _document(text: str, label: str):
    if "<table" not in text:
        raise AwardsPageError(
            f"season {label}: no award ballot markup in the fetched page")
    return lxml_html.fromstring(
        text.encode("utf-8"),
        parser=lxml_html.HTMLParser(remove_comments=False, encoding="utf-8"))


def _assert_page_season(doc, label: str) -> None:
    headings = doc.xpath("//h1")
    heading = headings[0].text_content().strip() if headings else ""
    if not heading.startswith(label):
        raise AwardsPageError(
            f"season {label}: page heading '{heading}' is not that season")


def _award_tables(doc) -> dict:
    tables: dict = {}
    for table in doc.xpath("//table[@id]"):
        tables.setdefault(table.get("id"), table)
    for node in doc.iter(etree.Comment):
        body = node.text
        if not body or "<table" not in body:
            continue
        for table in lxml_html.fromstring("<div>" + body + "</div>").xpath(
                "//table[@id]"):
            tables.setdefault(table.get("id"), table)
    return tables


def _section_rows(section: AwardSection, table, label: str, url: str) -> list[dict]:
    present = {cell.get("data-stat") for cell in table.xpath(".//th|.//td")
               if cell.get("data-stat")}
    missing = [stat for stat in section.required_stats if stat not in present]
    if missing:
        raise AwardsPageError(
            f"season {label}: award {section.award} ballot '{section.table_id}' "
            f"at {url} lacks column(s) {','.join(missing)}")
    rows = []
    for tr in table.xpath("./tbody/tr"):
        name = _text(tr, section.name_stat)
        if not tr.xpath("./td") or not name:
            continue
        row = {
            "SEASON": label,
            "AWARD": section.award,
            "RANK": _rank(tr, section, label, url),
            "RANK_LABEL": _rank_label(tr, section),
            "PLAYER": name if section.name_stat == "player" else None,
            "COACH": name if section.name_stat == "coach" else None,
            "AGE": _int(tr, "age"),
            "TEAM": _text(tr, "team_id") or None,
            "POINTS_WON": _int(tr, "points_won"),
            "POINTS_MAX": _int(tr, "points_max"),
            "AWARD_SHARE": _float(tr, "award_share"),
            "SOURCE_URL": url,
        }
        for column, stat in zip(VOTE_OUT_COLUMNS, section.vote_stats):
            row[column] = _int(tr, stat) if stat else None
        rows.append(row)
    return rows


def _rank_label(tr, section: AwardSection) -> str | None:
    return _text(tr, section.ordinal_stat) or None


def _rank(tr, section: AwardSection, label: str, url: str) -> int | None:
    code = _rank_label(tr, section) or ""
    ordinal = re.match(r"\d+", code)
    if ordinal:
        return int(ordinal.group(0))
    if section.rank_stat:
        raise AwardsPageError(
            f"season {label}: award {section.award} row "
            f"{_text(tr, section.name_stat)!r} has rank {code!r} at {url}")
    return None


def _cell(tr, stat: str | None):
    if not stat:
        return None
    found = tr.xpath("./th[@data-stat=$stat]|./td[@data-stat=$stat]", stat=stat)
    return found[0] if found else None


def _text(tr, stat: str | None) -> str:
    cell = _cell(tr, stat)
    return cell.text_content().strip() if cell is not None else ""


def _number(tr, stat: str | None, cast):
    raw = _text(tr, stat).replace(",", "")
    if not raw:
        return None
    try:
        return cast(raw)
    except ValueError:
        return None


def _int(tr, stat: str | None):
    return _number(tr, stat, lambda raw: int(float(raw)))


def _float(tr, stat: str | None):
    return _number(tr, stat, float)
