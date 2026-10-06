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
SEASON_LABEL = re.compile(r"\d{4}-\d{2}")
SHARE_TOLERANCE = 0.001

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
    contested: bool = False

    @property
    def ordinal_stat(self) -> str:
        return self.rank_stat or self.team_stat or ""

    @property
    def name_column(self) -> str:
        return "COACH" if self.name_stat == "coach" else "PLAYER"

    @property
    def required_stats(self) -> tuple[str, ...]:
        declared = [self.name_stat, self.ordinal_stat, *_RESULT_STATS]
        declared += [stat for stat in self.vote_stats if stat]
        return tuple(sorted(set(declared)))

@dataclass(frozen=True)
class WinnerPage:
    award: str
    url: str
    table_id: str

WINNER_PAGES: tuple[WinnerPage, ...] = (
    WinnerPage("MVP", "https://www.basketball-reference.com/awards/mvp.html",
               "mvp_NBA"),
    WinnerPage("ROY", "https://www.basketball-reference.com/awards/roy.html",
               "roy_NBA"),
    WinnerPage("DPOY", "https://www.basketball-reference.com/awards/dpoy.html",
               "dpoy_NBA"),
    WinnerPage("6MOY", "https://www.basketball-reference.com/awards/smoy.html",
               "smoy_NBA"),
    WinnerPage("MIP", "https://www.basketball-reference.com/awards/mip.html",
               "mip_NBA"),
    WinnerPage("COY", "https://www.basketball-reference.com/awards/coy.html",
               "coyNBA"),
)
WINNER_URLS = frozenset(page.url for page in WINNER_PAGES)

@dataclass(frozen=True)
class Ballot:
    season: str
    award: str
    rank: int | None
    rank_label: str | None
    player: str | None
    coach: str | None
    age: int | None
    team: str | None
    points_won: int | None
    points_max: int | None
    award_share: float | None
    votes: tuple[int | None, ...]

    def row(self, source_url: str) -> dict:
        row = {
            "SEASON": self.season,
            "AWARD": self.award,
            "RANK": self.rank,
            "RANK_LABEL": self.rank_label,
            "PLAYER": self.player,
            "COACH": self.coach,
            "AGE": self.age,
            "TEAM": self.team,
            "POINTS_WON": self.points_won,
            "POINTS_MAX": self.points_max,
            "AWARD_SHARE": self.award_share,
            "SOURCE_URL": source_url,
        }
        row.update(zip(VOTE_OUT_COLUMNS, self.votes))
        return row

AWARD_SECTIONS: tuple[AwardSection, ...] = (
    AwardSection("mvp", "MVP", "player", "rank", None,
                 ("votes_first", None, None), 1955, True),
    AwardSection("roy", "ROY", "player", "rank", None,
                 ("votes_first", None, None), 1962, True),
    AwardSection("dpoy", "DPOY", "player", "rank", None,
                 ("votes_first", None, None), 1982, True),
    AwardSection("smoy", "6MOY", "player", "rank", None,
                 ("votes_first", None, None), 1982, True),
    AwardSection("mip", "MIP", "player", "rank", None,
                 ("votes_first", None, None), 1985, True),
    AwardSection("coy", "COY", "coach", "rank", None,
                 ("votes_first", None, None), 1962, True),
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

def winner_index(text: str, award: str) -> dict[str, tuple[str, ...]]:
    page = _winner_page(award)
    tables = _award_tables(_document(text, f"the {award} winners index"))
    table = tables.get(page.table_id)
    if table is None:
        raise AwardsPageError(
            f"award {award}: winners table '{page.table_id}' missing from "
            f"{page.url}, so no season's {award} winner can be verified")
    winners: dict[str, list[str]] = {}
    for tr in table.xpath(".//tr"):
        cells = _row_cells(tr, f"award {award}", page.url)
        season = _cell_text(cells.get("season"))
        identity = _identity(_cell_text(cells.get("player"))
                             or _cell_text(cells.get("coach")))
        if not SEASON_LABEL.fullmatch(season or "") or not identity:
            continue
        named = winners.setdefault(season, [])
        if identity not in named:
            named.append(identity)
    if not winners:
        raise AwardsPageError(
            f"award {award}: {page.url} published no season winner, so no "
            f"{award} winner can be verified")
    return {season: tuple(named) for season, named in winners.items()}

def _identity(text: str | None) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()
    return re.sub(r"\s*[(*].*$", "", cleaned).strip()

def load_winner_index(
        pages: dict[str, str]) -> dict[str, dict[str, tuple[str, ...]]]:
    return {page.award: winner_index(pages[page.award], page.award)
            for page in WINNER_PAGES}

def fetch_winner_index(
        transport=None) -> dict[str, dict[str, tuple[str, ...]]]:
    get = transport or paced_transport()
    return load_winner_index({page.award: get(page.url)
                              for page in WINNER_PAGES})

def verify_ballots(frame: pl.DataFrame,
                   winners: dict[str, dict[str, tuple[str, ...]]]) -> None:
    for section in AWARD_SECTIONS:
        rows = frame.filter(pl.col("AWARD") == section.award)
        if rows.height == 0:
            continue
        seasons = rows["SEASON"].unique().to_list()
        if len(seasons) != 1:
            raise AwardsPageError(
                f"award {section.award}: one ballot spans seasons {seasons}")
        label = seasons[0]
        url = rows["SOURCE_URL"][0]
        _verify_row_completeness(section, rows, label, url)
        _verify_one_ballot_size(section, rows, label, url)
        _verify_share_of_points(section, rows, label, url)
        if section.contested:
            _verify_points_fall_with_rank(section, rows, label, url)
            _verify_first_place_budget(section, rows, label, url)
            _verify_published_winner(section, rows, label, url, winners)

def _winner_page(award: str) -> WinnerPage:
    for page in WINNER_PAGES:
        if page.award == award:
            return page
    raise AwardsPageError(
        f"award {award} has no winners page in {AWARDS_INDEX_URL}, so its "
        f"winner cannot be verified against the source")

def _verify_row_completeness(section: AwardSection, rows: pl.DataFrame,
                             label: str, url: str) -> None:
    columns = [section.name_column]
    if section.contested:
        columns += ["POINTS_WON", "POINTS_MAX", "AWARD_SHARE", "VOTES_FIRST"]
    for row in rows.iter_rows(named=True):
        for column in columns:
            if row[column] is None:
                raise AwardsPageError(
                    f"season {label}: award {section.award} row "
                    f"{_describe(row)} at {url} has no {column.lower()}, so its "
                    f"identity and its ballot cannot both be read")

def _verify_one_ballot_size(section: AwardSection, rows: pl.DataFrame,
                            label: str, url: str) -> None:
    sizes = rows["POINTS_MAX"].drop_nulls().unique().to_list()
    if len(sizes) > 1:
        raise AwardsPageError(
            f"season {label}: award {section.award} at {url} reports "
            f"{len(sizes)} different voter counts {sorted(sizes)}, so its rows "
            f"do not come from one ballot")

def _verify_share_of_points(section: AwardSection, rows: pl.DataFrame,
                            label: str, url: str) -> None:
    for row in rows.iter_rows(named=True):
        if row["POINTS_MAX"] in (None, 0) or row["POINTS_WON"] is None:
            continue
        exact = row["POINTS_WON"] / row["POINTS_MAX"]
        if abs(row["AWARD_SHARE"] - exact) >= SHARE_TOLERANCE:
            raise AwardsPageError(
                f"season {label}: award {section.award} row "
                f"{row[section.name_column]!r} at {url} claims share "
                f"{row['AWARD_SHARE']} for "
                f"{row['POINTS_WON']} of {row['POINTS_MAX']} points, which is "
                f"{round(exact, 4)}")

def _verify_points_fall_with_rank(section: AwardSection, rows: pl.DataFrame,
                                  label: str, url: str) -> None:
    ranked = rows.filter(pl.col("RANK").is_not_null()).sort("RANK")
    points = ranked["POINTS_WON"].to_list()
    for index in range(len(points) - 1):
        if points[index + 1] > points[index]:
            raise AwardsPageError(
                f"season {label}: award {section.award} at {url} gives rank "
                f"{ranked['RANK'][index + 1]} more points "
                f"({points[index + 1]}) than rank {ranked['RANK'][index]} "
                f"({points[index]})")

def _verify_first_place_budget(section: AwardSection, rows: pl.DataFrame,
                               label: str, url: str) -> None:
    firsts = rows["VOTES_FIRST"].drop_nulls().sum()
    voters = rows["POINTS_MAX"].drop_nulls().max()
    if firsts is not None and voters and firsts > voters:
        raise AwardsPageError(
            f"season {label}: award {section.award} at {url} hands out "
            f"{firsts} first-place votes to {voters} voters, so its rows "
            f"cannot all come from that ballot")

def _verify_published_winner(
        section: AwardSection, rows: pl.DataFrame, label: str, url: str,
        winners: dict[str, dict[str, tuple[str, ...]]]) -> None:
    published = (winners.get(section.award) or {}).get(label)
    if not published:
        raise AwardsPageError(
            f"season {label}: award {section.award} has no winner published at "
            f"{_winner_page(section.award).url}, so the ballot read from {url} "
            f"would go out unverified")
    ranked = rows.filter(pl.col("RANK") == 1)
    if ranked.height == 0:
        raise AwardsPageError(
            f"season {label}: award {section.award} at {url} has no rank 1 row, "
            f"so it names no winner at all")
    named = {_identity(row[section.name_column])
             for row in ranked.iter_rows(named=True)}
    unexpected = sorted(named - set(published))
    if unexpected:
        raise AwardsPageError(
            f"season {label}: award {section.award} rank 1 at {url} names "
            f"{', '.join(repr(name) for name in unexpected)} but "
            f"{_winner_page(section.award).url} names "
            f"{', '.join(repr(name) for name in published)} for that season")

def _describe(row: dict) -> str:
    rank = row["RANK"]
    return f"rank {rank}" if rank is not None else "unranked"

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
        ballot = _ballot(tr, section, label, url)
        if ballot is not None:
            rows.append(ballot.row(url))
    return rows

def _ballot(tr, section: AwardSection, label: str, url: str) -> Ballot | None:
    if not tr.xpath("./td"):
        return None
    cells = _row_cells(tr, f"season {label}: award {section.award}", url)
    name = _cell_text(cells.get(section.name_stat))
    if not name:
        return None
    rank_label = _cell_text(cells.get(section.ordinal_stat)) or None
    return Ballot(
        season=label,
        award=section.award,
        rank=_rank(rank_label, section, name, label, url),
        rank_label=rank_label,
        player=name if section.name_stat == "player" else None,
        coach=name if section.name_stat == "coach" else None,
        age=_cell_int(cells.get("age")),
        team=_cell_text(cells.get("team_id")) or None,
        points_won=_cell_int(cells.get("points_won")),
        points_max=_cell_int(cells.get("points_max")),
        award_share=_cell_float(cells.get("award_share")),
        votes=tuple(_cell_int(cells.get(stat)) if stat else None
                    for stat in section.vote_stats),
    )

def _row_cells(tr, context: str, url: str) -> dict:
    cells: dict = {}
    for cell in tr.xpath("./th|./td"):
        stat = cell.get("data-stat")
        if not stat:
            continue
        if stat in cells:
            raise AwardsPageError(
                f"{context} row at {url} carries two cells for {stat!r}, so no "
                f"cell can be trusted as that row's {stat}")
        cells[stat] = cell
    return cells

def _rank(rank_label: str | None, section: AwardSection, name: str,
          label: str, url: str) -> int | None:
    ordinal = re.match(r"\d+", rank_label or "")
    if ordinal:
        return int(ordinal.group(0))
    if section.rank_stat:
        raise AwardsPageError(
            f"season {label}: award {section.award} row {name!r} has rank "
            f"{rank_label!r} at {url}")
    return None

def _cell_text(cell) -> str:
    return cell.text_content().strip() if cell is not None else ""

def _cell_number(cell, cast):
    raw = _cell_text(cell).replace(",", "")
    if not raw:
        return None
    try:
        return cast(raw)
    except ValueError:
        return None

def _cell_int(cell):
    return _cell_number(cell, lambda raw: int(float(raw)))

def _cell_float(cell):
    return _cell_number(cell, float)
