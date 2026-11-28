import polars as pl

from .base import FetchMeta, FetchResult

SOURCE = "nba-cba:public-cap-figures"
SEASON = "league"

ROWS = [
    (1985, 3.600, None),
    (1986, 4.233, None),
    (1987, 4.945, None),
    (1988, 6.164, None),
    (1989, 7.232, None),
    (1990, 9.802, None),
    (1991, 11.871, None),
    (1992, 12.500, None),
    (1993, 14.000, None),
    (1994, 15.175, None),
    (1995, 15.964, None),
    (1996, 23.000, None),
    (1997, 24.363, None),
    (1998, 26.900, None),
    (1999, 30.000, None),
    (2000, 34.000, None),
    (2001, 35.500, None),
    (2002, 42.500, None),
    (2003, 40.271, 52.880),
    (2004, 43.840, 54.630),
    (2005, 43.870, 55.630),
    (2006, 49.500, 61.700),
    (2007, 53.135, 65.420),
    (2008, 55.630, 67.865),
    (2009, 58.680, 71.150),
    (2010, 57.700, 69.920),
    (2011, 58.044, 70.307),
    (2012, 58.044, 70.307),
    (2013, 58.044, 70.307),
    (2014, 58.679, 71.748),
    (2015, 63.065, 76.829),
    (2016, 70.000, 84.740),
    (2017, 94.143, 113.287),
    (2018, 99.093, 119.266),
    (2019, 101.869, 123.733),
    (2020, 109.140, 132.627),
    (2021, 109.140, 132.627),
    (2022, 112.414, 136.606),
    (2023, 123.655, 150.267),
    (2024, 136.021, 165.294),
    (2025, 140.588, 170.814),
    (2026, 154.647, 187.895),
    (2027, 164.961, 200.428),
]

APRON = {
    2024: (172.346, 182.794),
    2025: (178.132, 188.931),
    2026: (195.945, 207.824),
    2027: (209.015, 221.686),
}

ERA = {
    (1985, 1999): "1984-cba",
    (1999, 2006): "1999-cba",
    (2006, 2012): "2005-cba",
    (2012, 2024): "2011-cba",
    (2024, 2031): "2023-cba",
}

MAX_TIERS = (0.25, 0.30, 0.35)
FLOOR_PCT = 0.90


def _era(end_year: int) -> str:
    for (lo, hi), name in ERA.items():
        if lo <= end_year < hi:
            return name
    return "unknown"


def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def history() -> FetchResult:
    rows = []
    for end_year, cap_m, tax_m in ROWS:
        aprons = APRON.get(end_year)
        floor = FLOOR_PCT if end_year >= 2006 else None
        tiers = MAX_TIERS if end_year >= 2000 else (None, None, None)
        rows.append({
            "season": end_year,
            "season_label": label(end_year),
            "salary_cap": cap_m * 1_000_000,
            "luxury_tax": tax_m * 1_000_000 if tax_m is not None else None,
            "apron_1": aprons[0] * 1_000_000 if aprons else None,
            "apron_2": aprons[1] * 1_000_000 if aprons else None,
            "salary_floor_pct": floor,
            "max_salary_tier_low_pct": tiers[0],
            "max_salary_tier_mid_pct": tiers[1],
            "max_salary_tier_high_pct": tiers[2],
            "cba_era": _era(end_year),
        })
    frame = pl.DataFrame(rows)
    return FetchResult(frame=frame, meta=FetchMeta(source=SOURCE, season=SEASON))
