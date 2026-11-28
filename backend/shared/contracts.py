import re
import unicodedata

import polars as pl


def normalize_name(value: object) -> str:
    text = ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).lower()
    words = re.sub(r'[^a-z0-9\s]', '', text).split()
    while words and words[-1] in {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}:
        words.pop()
    return ''.join(words)


_TEAM_ABBR_CANONICAL = {'WSH': 'WAS', 'BRK': 'BKN', 'CHO': 'CHA', 'PHO': 'PHX'}


def canonical_team_abbr(value: object) -> str:
    code = str(value or '').strip().upper()
    return _TEAM_ABBR_CANONICAL.get(code, code)


def player_name_key_sql(column: str) -> str:
    ws = r"\s\p{Z}"
    cleaned = (f"regexp_replace(strip_accents(lower({column})), "
               f"'[^a-z0-9{ws}]', '', 'g')")
    trimmed = (f"regexp_replace({cleaned}, "
               f"'^[{ws}]+|[{ws}]+$', '', 'g')")
    suffixless = (f"regexp_replace({trimmed}, "
                  f"'(?:^|[{ws}]+)(?:iii|ii|iv|jr|sr|v)"
                  f"(?:[{ws}]+(?:iii|ii|iv|jr|sr|v))*$', '', 'g')")
    return f"regexp_replace({suffixless}, '[{ws}]+', '', 'g')"


def resolve_salary_column(columns: set[str], season: str | None) -> str:
    if season:
        column = 'SALARY_' + season.replace('-', '_')
        return column if column in columns else ''
    if 'SALARY' in columns:
        return 'SALARY'
    salary_columns = {c for c in columns if re.fullmatch(r'SALARY_\d{4}_\d{2}', c)}
    if len(salary_columns) == 1:
        return next(iter(salary_columns))
    return ''


def row_kind_column(columns) -> str | None:
    for column in columns:
        if str(column).lower() == 'row_kind':
            return str(column)
    return None


def row_kind_declared(columns) -> bool:
    return row_kind_column(columns) is not None


def normalized_row_kind(value: object) -> str:
    return str(value or 'roster').strip().lower().replace('-', '_')


def is_dead_money_row(row: dict) -> bool:
    for key, value in row.items():
        if str(key).lower() == 'row_kind':
            return normalized_row_kind(value) == 'dead_money'
    return False


def _quoted_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def dead_money_row_predicate(column: str) -> str:
    ws = r"\s\p{Z}"
    trimmed = (f"regexp_replace(COALESCE({_quoted_identifier(column)}, 'roster'), "
               f"'^[{ws}]+|[{ws}]+$', '', 'g')")
    normalized = f"LOWER(REPLACE({trimmed}, '-', '_'))"
    return f"{normalized} = 'dead_money'"


def roster_row_predicate(column: str) -> str:
    return f"NOT ({dead_money_row_predicate(column)})"


def contract_details(row: dict | None) -> dict:
    row = row or {}
    current = str(row.get('_season') or '')
    columns = sorted(c for c in row if re.fullmatch(r'SALARY_\d{4}_\d{2}', c))
    salaries = {c[7:].replace('_', '-'): row[c] for c in columns
                if row[c] is not None and c[7:].replace('_', '-') >= current}
    available = 'SALARY' in row and len(columns) > 1 and bool(salaries)
    options = {season: row.get('OPTION_' + season.replace('-', '_'))
               for season in (c[7:].replace('_', '-') for c in columns)
               if season >= current and row.get('OPTION_' + season.replace('-', '_'))}
    return {
        'player_id': row.get('PLAYER_ID'),
        'bref_slug': row.get('BREF_SLUG'),
        'remaining_guaranteed': row.get('GUARANTEED'),
        'contract_schedule_available': available,
        'years_remaining': sum(v > 0 for v in salaries.values()) if available else None,
        'salary_by_season': salaries if available else None,
        'future_salaries': {k: v for k, v in salaries.items() if k > current} if available else None,
        'option_years': options if available else None,
        'years_remaining_basis': 'listed salary seasons including options; not guaranteed term' if available else None,
    }


def salary_records(con, season: str | None = None, salary_season: str | None = None,
                   include_fallback: bool = False) -> list[dict]:
    tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
    order = ['silver_salaries', 'silver_cap_players', 'silver_contracts']
    want = season or salary_season
    if want and 'silver_contracts' in tables:
        contract_cols = [r[1] for r in con.execute('PRAGMA table_info(silver_contracts)').fetchall()]
        exact = ('_season' in contract_cols and con.execute(
            'SELECT 1 FROM silver_contracts WHERE _season = ? LIMIT 1', [want]).fetchone())
        latest_sheet = None
        if 'silver_salaries' in tables:
            salary_cols = [r[1] for r in con.execute('PRAGMA table_info(silver_salaries)').fetchall()]
            if '_season' in salary_cols:
                latest_sheet = con.execute('SELECT MAX(_season) FROM silver_salaries').fetchone()[0]
        if exact and (latest_sheet is None or str(want) < str(latest_sheet)):
            order = ['silver_contracts', 'silver_salaries', 'silver_cap_players']
    records = []
    for table in order:
        if table not in tables:
            continue
        columns = [r[1] for r in con.execute(f'PRAGMA table_info({table})').fetchall()]
        salary = (resolve_salary_column(set(columns), salary_season or season)
                  if table == 'silver_salaries' else ('salary' if table == 'silver_cap_players' else 'SALARY'))
        if not salary:
            continue
        filters = []
        params = []
        season_filter = season or (salary_season if table == 'silver_contracts' else None)
        if season_filter and '_season' in columns:
            filters.append('_season = ?')
            params = [season_filter]
        kind_column = row_kind_column(columns) if table == 'silver_salaries' else None
        if kind_column:
            filters.append(roster_row_predicate(kind_column))
        where = ' WHERE ' + ' AND '.join(filters) if filters else ''
        rows = [dict(zip(columns, values)) for values in con.execute(f'SELECT * FROM {table}{where}', params).fetchall()]
        if rows and not season and '_season' in columns:
            latest = max(str(r.get('_season') or '') for r in rows)
            rows = [r for r in rows if str(r.get('_season') or '') == latest]
        if rows:
            for row in rows:
                row['PLAYER_NAME'] = row.get('PLAYER_NAME', row.get('player'))
                row['TEAM'] = canonical_team_abbr(row.get('TEAM', row.get('team')))
                row['salary'] = row.get(salary)
            if not records:
                records = rows
            else:
                for row in rows:
                    primary = match_record(records, row['PLAYER_NAME'], row.get('PLAYER_ID'), row['TEAM'], salary=row.get('salary'))
                    if primary is None:
                        records.append(row)
                    else:
                        if primary['salary'] is None:
                            primary['salary'] = row['salary']
                        if primary.get('PLAYER_ID') is None and row.get('PLAYER_ID') is not None:
                            primary['PLAYER_ID'] = row['PLAYER_ID']
            if not include_fallback:
                return records
    return records


def name_tokens(value: object) -> set[str]:
    text = ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).lower()
    return {t for t in re.findall(r'[a-z]+', text) if len(t) >= 4}


def match_record(records: list[dict], name: str, player_id=None, team: str = '', salary=None) -> dict | None:
    team_code = canonical_team_abbr(team)
    if player_id is not None:
        hits = [r for r in records if r.get('PLAYER_ID') == player_id]
        if len(hits) == 1:
            return hits[0]
        if hits:
            team_hits = [r for r in hits if canonical_team_abbr(r.get('TEAM')) == team_code]
            if len(team_hits) == 1:
                return team_hits[0]
    hits = [r for r in records if normalize_name(r.get('PLAYER_NAME', r.get('PLAYER'))) == normalize_name(name)
            and (player_id is None or r.get('PLAYER_ID') is None or r['PLAYER_ID'] == player_id)]
    if len(hits) == 1:
        return hits[0]
    hits = [r for r in hits if canonical_team_abbr(r.get('TEAM')) == team_code]
    if len(hits) == 1:
        return hits[0]
    if salary and team_code:
        want = name_tokens(name)
        hits = [r for r in records
                if r.get('salary') and float(r['salary']) == float(salary)
                and canonical_team_abbr(r.get('TEAM')) == team_code
                and name_tokens(r.get('PLAYER_NAME', r.get('PLAYER'))) & want]
        if len(hits) == 1:
            return hits[0]
    return None


def warehouse_player_ids(con) -> list[dict]:
    records = []
    tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
    for table in ('silver_leaders_pts', 'silver_advanced', 'silver_player_season'):
        if table not in tables:
            continue
        columns = {r[1] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}
        name = next((c for c in ('PLAYER_NAME', 'PLAYER') if c in columns), None)
        team = next((c for c in ('TEAM_ABBREVIATION', 'TEAM') if c in columns), None)
        if not name or 'PLAYER_ID' not in columns:
            continue
        team_sql = team or 'NULL'
        season_sql = '_season' if '_season' in columns else "''"
        for pid, player, abbr, season in con.execute(
                f'SELECT DISTINCT PLAYER_ID, {name}, {team_sql}, {season_sql} FROM {table} WHERE PLAYER_ID IS NOT NULL').fetchall():
            records.append({'PLAYER_ID': pid, 'PLAYER_NAME': player,
                            'TEAM': canonical_team_abbr(abbr), '_season': season or ''})
    return records


def resolve_player_ids(frame, con):
    index = {}
    for row in warehouse_player_ids(con):
        index.setdefault(normalize_name(row['PLAYER_NAME']), []).append(row)
    ids = []
    for row in frame.to_dicts():
        candidates = index.get(normalize_name(row['PLAYER_NAME']), [])
        unique = {r['PLAYER_ID'] for r in candidates}
        if len(unique) > 1:
            latest = {pid: max(r['_season'] for r in candidates if r['PLAYER_ID'] == pid) for pid in unique}
            team_code = canonical_team_abbr(row['TEAM'])
            unique = {r['PLAYER_ID'] for r in candidates if r['_season'] == latest[r['PLAYER_ID']]
                      and canonical_team_abbr(r['TEAM']) == team_code}
        ids.append(next(iter(unique)) if len(unique) == 1 else None)
    return frame.with_columns(pl.Series('PLAYER_ID', ids, dtype=pl.Int64))
