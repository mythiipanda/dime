TEAM_NICKNAMES = {
    "hawks": "ATL",
    "celtics": "BOS",
    "nets": "BKN",
    "hornets": "CHA",
    "bulls": "CHI",
    "cavaliers": "CLE",
    "cavs": "CLE",
    "mavericks": "DAL",
    "mavs": "DAL",
    "nuggets": "DEN",
    "pistons": "DET",
    "warriors": "GSW",
    "rockets": "HOU",
    "pacers": "IND",
    "clippers": "LAC",
    "lakers": "LAL",
    "grizzlies": "MEM",
    "grizz": "MEM",
    "heat": "MIA",
    "bucks": "MIL",
    "timberwolves": "MIN",
    "wolves": "MIN",
    "pelicans": "NOP",
    "pels": "NOP",
    "knicks": "NYK",
    "thunder": "OKC",
    "magic": "ORL",
    "76ers": "PHI",
    "sixers": "PHI",
    "suns": "PHX",
    "trail blazers": "POR",
    "blazers": "POR",
    "kings": "SAC",
    "spurs": "SAS",
    "raptors": "TOR",
    "raps": "TOR",
    "jazz": "UTA",
    "wizards": "WAS",
}

OFFENSIVE_FOULS = {"Offensive", "Offensive Charge"}

DECISIVE_ACTIONS = {"Made Shot", "Missed Shot", "Free Throw", "Turnover"}


def period_base(period):
    try:
        if int(period) > 4:
            return 300.0
    except (TypeError, ValueError):
        pass
    return 720.0


def elapsed_sec(period, sec_remaining):
    try:
        left = float(sec_remaining)
    except (TypeError, ValueError):
        return 0.0
    return period_base(period) - left


def clock_text(clock):
    try:
        s = str(clock)
        if not s.startswith("PT") or not s.endswith("S"):
            return ""
        m = s.index("M")
        minutes = int(s[2:m])
        seconds = int(float(s[m + 1:-1]))
        return f"{minutes}:{seconds:02d}"
    except (ValueError, AttributeError):
        return ""


def _sec_remaining(row):
    raw = row.get("seconds_remaining")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    from shared.tools.wpamodel import parse_clock

    parsed = parse_clock(row.get("clock"))
    if parsed is None:
        return 0.0
    return float(parsed)


def _score_value(raw):
    try:
        text = str(raw).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _team_of(row):
    try:
        return int(row.get("team_id"))
    except (TypeError, ValueError):
        return 0


def _order_of(row):
    try:
        return int(row.get("order_index") or 0)
    except (TypeError, ValueError):
        return 0


def _ft_numbers(sub_type):
    nums = []
    for part in str(sub_type or "").split():
        if part.isdigit():
            nums.append(int(part))
    return nums


def _ft_made(row):
    return not str(row.get("description") or "").startswith("MISS")


def _ft_token(row):
    nums = _ft_numbers(row.get("sub_type"))
    made = _ft_made(row)
    if len(nums) == 2:
        return f"FT{nums[0]}OF{nums[1]}-{'MAKE' if made else 'MISS'}"
    return f"FT-{'MAKE' if made else 'MISS'}"


def _is_final_ft(row):
    nums = _ft_numbers(row.get("sub_type"))
    return len(nums) == 2 and nums[0] == nums[1]


def _shot_value(row):
    try:
        return int(row.get("shot_value") or 0)
    except (TypeError, ValueError):
        return 0


def _shot_token(row):
    value = _shot_value(row)
    if (row.get("action_type") or "") == "Made Shot":
        return f"MAKE{value}"
    return f"MISS{value}"


def _rebound_team(row, id_to_abbr, abbr_to_id):
    tricode = str(row.get("team_tricode") or "").strip()
    tid = _team_of(row)
    if tricode:
        return tid, tricode
    if tid:
        return tid, id_to_abbr.get(tid) or ""
    desc = str(row.get("description") or "")
    name = desc.split(" Rebound")[0].strip().lower()
    abbr = TEAM_NICKNAMES.get(name)
    if abbr is None:
        for known in id_to_abbr.values():
            if known and known.lower() == name:
                abbr = known
                break
    if abbr is None or abbr not in abbr_to_id:
        raise ValueError(f"unmapped team rebound: {desc!r}")
    return abbr_to_id[abbr], abbr


def _static_token(row):
    action = row.get("action_type") or ""
    if action == "period":
        if (row.get("sub_type") or "") == "start":
            return "PERIOD-START"
        return "PERIOD-END"
    if action == "Jump Ball":
        return "TIP"
    if action in ("Made Shot", "Missed Shot"):
        return _shot_token(row)
    if action == "Free Throw":
        return _ft_token(row)
    if action == "Turnover":
        return "TOV"
    if action == "Foul":
        return "FOUL"
    if action == "Timeout":
        return "TIMEOUT"
    if action == "Substitution":
        return "SUB"
    if action == "Instant Replay":
        return "REPLAY"
    if action == "Violation":
        return "VIOLATION"
    if action == "Ejection":
        return "EJECTION"
    return "NOTE"


def _resolve_offense(rows, team_ids, id_to_abbr, abbr_to_id):
    for row in rows:
        if (row.get("action_type") or "") not in DECISIVE_ACTIONS:
            continue
        tid = _team_of(row)
        if tid and tid in id_to_abbr:
            return tid, id_to_abbr.get(tid) or ""
    for row in rows:
        action = row.get("action_type") or ""
        if action in ("Jump Ball", "period"):
            continue
        tid = _team_of(row)
        tricode = str(row.get("team_tricode") or "").strip()
        if not tid and not tricode:
            continue
        if action == "Foul" and str(row.get("sub_type") or "") not in OFFENSIVE_FOULS:
            others = [i for i in team_ids if i != tid]
            if len(others) == 1:
                return others[0], id_to_abbr.get(others[0]) or ""
            continue
        if tid and tid in id_to_abbr:
            return tid, id_to_abbr.get(tid) or ""
        if tricode and tricode in abbr_to_id:
            resolved = abbr_to_id[tricode]
            return resolved, tricode
    raise ValueError("offense unresolvable")


class _Open:
    def __init__(self, team_ids, id_to_abbr, abbr_to_id, score_in):
        self.team_ids = team_ids
        self.id_to_abbr = id_to_abbr
        self.abbr_to_id = abbr_to_id
        self.score_in = score_in
        self.rows = []
        self.events = []
        self.decisive = None
        self.scored = False
        self.shooter = 0
        self.score_sec = 0.0
        self.foul_seen = False
        self.team_points = {}

    def attach(self, row):
        self.rows.append(row)
        action = row.get("action_type") or ""
        if action == "Rebound":
            tid, _ = _rebound_team(row, self.id_to_abbr,
                                   self.abbr_to_id)
            off = self.decisive[0] if self.decisive else 0
            team_event = not str(row.get("team_tricode") or "").strip()
            if tid == off and off:
                self.events.append("TEAM-OREB" if team_event else "OREB")
                return False
            self.events.append("TEAM-DREB" if team_event else "DREB")
            return True
        if action in ("Made Shot", "Missed Shot", "Free Throw"):
            if self.decisive is None:
                tid = _team_of(row)
                tricode = str(row.get("team_tricode") or "").strip()
                if tid and tid in self.id_to_abbr:
                    self.decisive = (tid, self.id_to_abbr.get(tid) or "")
                elif tricode:
                    self.decisive = (tid, tricode)
            if action in ("Made Shot", "Missed Shot"):
                self.events.append(_shot_token(row))
            else:
                self.events.append(_ft_token(row))
            if action == "Made Shot":
                tid = _team_of(row)
                value = _shot_value(row)
                self.team_points[tid] = self.team_points.get(tid, 0) + value
                self.scored = True
                self.shooter = tid
                self.score_sec = _sec_remaining(row)
            elif action == "Free Throw":
                if _ft_made(row):
                    tid = _team_of(row)
                    self.team_points[tid] = self.team_points.get(tid, 0) + 1
                    if _is_final_ft(row):
                        self.scored = True
                        self.shooter = tid
                        self.score_sec = _sec_remaining(row)
            return False
        if action == "Turnover":
            if self.decisive is None:
                tid = _team_of(row)
                tricode = str(row.get("team_tricode") or "").strip()
                if tid and tid in self.id_to_abbr:
                    self.decisive = (tid, self.id_to_abbr.get(tid) or "")
                elif tricode:
                    self.decisive = (tid, tricode)
            self.events.append("TOV")
            return True
        self.events.append(_static_token(row))
        if action == "Foul":
            self.foul_seen = True
        return action == "period" and (row.get("sub_type") or "") == "end"

    def close(self, number, score_out):
        first = self.rows[0]
        last = self.rows[-1]
        try:
            period = int(first.get("period") or 0)
        except (TypeError, ValueError):
            period = 0
        if self.decisive is not None:
            off_id, off_abbr = self.decisive
        else:
            off_id, off_abbr = _resolve_offense(self.rows, self.team_ids,
                                                self.id_to_abbr,
                                                self.abbr_to_id)
        def_id = next((i for i in self.team_ids if i != off_id), 0)
        return {
            "possession_number": number,
            "period": period,
            "clock_in": clock_text(first.get("clock")),
            "clock_out": clock_text(last.get("clock")),
            "clock_in_sec": _sec_remaining(first),
            "clock_out_sec": _sec_remaining(last),
            "off_team_id": off_id,
            "def_team_id": def_id,
            "off_abbr": off_abbr,
            "def_abbr": self.id_to_abbr.get(def_id) or "",
            "events": list(self.events),
            "points": int(self.team_points.get(off_id, 0)),
            "score_home_in": int(self.score_in[0]),
            "score_away_in": int(self.score_in[1]),
            "score_home_out": int(score_out[0]),
            "score_away_out": int(score_out[1]),
        }


def parse_game_possessions(pbp_rows):
    rows = sorted(list(pbp_rows or []), key=_order_of)
    team_ids = []
    id_to_abbr = {}
    for row in rows:
        tid = _team_of(row)
        if not tid or tid in team_ids:
            continue
        team_ids.append(tid)
        tricode = str(row.get("team_tricode") or "").strip()
        if tricode:
            id_to_abbr.setdefault(tid, tricode)
    if len(team_ids) != 2:
        raise ValueError(f"expected 2 teams, found {len(team_ids)}")
    abbr_to_id = {a: i for i, a in id_to_abbr.items() if a}
    out = []
    current = None
    home = 0
    away = 0
    game_id = ""
    if rows:
        first_home = _score_value(rows[0].get("score_home"))
        if first_home is not None:
            home = first_home
        first_away = _score_value(rows[0].get("score_away"))
        if first_away is not None:
            away = first_away

    def shut(number):
        record = current.close(number, (home, away))
        out.append(record)

    for row in rows:
        gid = row.get("game_id")
        if gid:
            game_id = str(gid)
        action = row.get("action_type") or ""
        sub = row.get("sub_type") or ""
        if current is None:
            current = _Open(team_ids, id_to_abbr, abbr_to_id, (home, away))
        elif action == "period" and sub == "start":
            shut(len(out) + 1)
            current = _Open(team_ids, id_to_abbr, abbr_to_id, (home, away))
        elif action == "period" and sub == "end":
            home_score = _score_value(row.get("score_home"))
            if home_score is not None:
                home = home_score
            away_score = _score_value(row.get("score_away"))
            if away_score is not None:
                away = away_score
            current.attach(row)
            shut(len(out) + 1)
            current = None
            continue
        elif action == "Jump Ball" and (current.decisive is not None
                                       or current.scored):
            shut(len(out) + 1)
            current = _Open(team_ids, id_to_abbr, abbr_to_id, (home, away))
        elif current.scored:
            continues = (
                (action == "Free Throw"
                 and _team_of(row) == current.shooter)
                or (action == "Foul"
                    and _sec_remaining(row) == current.score_sec)
                or (action in ("Timeout", "Substitution", "Instant Replay")
                    and current.foul_seen
                    and _sec_remaining(row) == current.score_sec)
            )
            if not continues:
                shut(len(out) + 1)
                current = _Open(team_ids, id_to_abbr, abbr_to_id,
                                (home, away))
        home_score = _score_value(row.get("score_home"))
        if home_score is not None:
            home = home_score
        away_score = _score_value(row.get("score_away"))
        if away_score is not None:
            away = away_score
        ended = current.attach(row)
        if ended:
            shut(len(out) + 1)
            current = None
    if current is not None and current.rows:
        shut(len(out) + 1)
    for record in out:
        record["game_id"] = game_id
    return out
