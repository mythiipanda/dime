import re
import time
import unicodedata

import polars as pl
from lxml import html as lxml_html

from .base import FetchResult, safe

SOURCE = "bref_contracts"
URL = "https://www.basketball-reference.com/contracts/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,*/*",
    "Referer": "https://www.basketball-reference.com/",
}

TEAM_ABBR = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX", "WSH": "WAS"}

def _fold(name: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(name or ""))
        if not unicodedata.combining(c)
    ).strip()

def _get(url: str) -> str:
    import httpx
    last: Exception | None = None
    for attempt in range(4):
        r = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        if r.status_code == 429:
            last = RuntimeError(f"429 for {url}")
            time.sleep(8 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.text
    raise last or RuntimeError(f"failed fetching {url}")

def _parse_contracts(page: str, team: str) -> tuple[str, list[dict]]:
    document = lxml_html.fromstring(page)
    tables = document.xpath('//table[@id="contracts"]')
    if not tables:
        raise ValueError('contracts table missing')
    table = tables[0]
    seasons = {}
    for cell in table.xpath('.//thead//*[@data-stat]'):
        stat = cell.get('data-stat')
        text = cell.text_content().strip()
        if re.fullmatch(r'y[1-6]', stat or '') and re.fullmatch(r'\d{4}-\d{2}', text):
            seasons[stat] = text
    if len(seasons) != 6:
        raise ValueError('six contract season headers required')
    rows = []
    option_classes = {'salary-pl': 'player', 'salary-tm': 'team',
                      'salary-et': 'early-termination', 'salary-eto': 'early-termination'}
    for node in table.xpath('.//tbody/tr'):
        cells = {c.get('data-stat'): c for c in node.xpath('./th|./td')}
        player = cells.get('player')
        if player is None:
            continue
        links = player.xpath('.//a/@href')
        slug = re.search(r'/players/[a-z]/([^/]+)\.html', links[0]) if links else None
        if not slug:
            continue
        row = {'PLAYER_NAME': _fold(player.text_content()),
               'TEAM': TEAM_ABBR.get(team, team), 'BREF_SLUG': slug.group(1)}
        for stat, season in seasons.items():
            cell = cells.get(stat)
            raw = cell.get('csk') if cell is not None else None
            amount = int(raw) if raw and raw.isdigit() else None
            key = season.replace('-', '_')
            row['SALARY_' + key] = amount
            classes = set((cell.get('class') or '').split()) if cell is not None else set()
            row['OPTION_' + key] = next((value for name, value in option_classes.items() if name in classes), None)
            if stat == 'y1':
                row['SALARY'] = amount
        guaranteed = cells.get('remain_gtd')
        raw = guaranteed.get('csk') if guaranteed is not None else None
        row['GUARANTEED'] = int(raw) if raw and raw.isdigit() else None
        if any(row.get('SALARY_' + s.replace('-', '_')) is not None for s in seasons.values()):
            rows.append(row)
    return seasons['y1'], rows

def _run(season: list) -> pl.DataFrame:
    html = _get(URL)
    m = re.search(r'data-stat="y1"[^>]*>([\d-]+)', html)
    observed = (m.group(1).strip() if m else "")
    season.append(observed)
    rows = []
    for a in sorted(set(re.findall(r"/contracts/([A-Z]{2,3})\.html", html))):
        time.sleep(4)
        page = _get(URL + a + ".html")
        team_season, team_rows = _parse_contracts(page, a)
        if team_season != observed:
            raise ValueError('inconsistent contract seasons')
        rows.extend(team_rows)
    frame = pl.DataFrame(rows, infer_schema_length=None)
    return frame.with_columns([
        pl.col(c).cast(pl.Int64 if c.startswith('SALARY') or c == 'GUARANTEED' else pl.String)
        for c in frame.columns
    ])

def get_contracts() -> FetchResult:
    season: list = []
    res = safe(SOURCE, "unknown", lambda: _run(season))
    observed = season[0] if season and season[0] else ""
    if observed:
        res.meta.season = observed
    else:
        res.meta.season = "unknown"
        res.ok = False
        res.error = (res.error or "y1 header not observed")[:300]
    return res
