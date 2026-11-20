
import asyncio
import json
import os
from pathlib import Path

import duckdb

from python_tools import catalogue


async def main():
    root = Path(os.environ["DIME_PI_TEST_ROOT"])
    warehouse = Path(os.environ["DIME_WAREHOUSE"])
    if warehouse.exists():
        raise FileExistsError(warehouse)
    con = duckdb.connect(str(warehouse))
    try:
        columns = ", ".join(f"metadata_{i} DOUBLE" for i in range(2000))
        con.execute("CREATE TABLE silver_hist_player_seasons "
                    "(season INTEGER, _season VARCHAR, PTS DOUBLE, _source VARCHAR)")
        con.execute("INSERT INTO silver_hist_player_seasons VALUES "
                    "(2091, '2090-91', 11.8, 'owned-synthetic'), "
                    "(2091, '2090-91', 999, 'RAW_SECRET_ROW')")
        con.execute("CREATE TABLE silver_leaders_pts "
                    f"(_season VARCHAR, PTS INTEGER, _source VARCHAR, {columns}, RAW_SECRET_ROW VARCHAR)")
        con.execute("INSERT INTO silver_leaders_pts (_season, PTS, _source) VALUES ('2090-91', 71, 'owned-synthetic')")
        con.execute("CREATE TABLE silver_lineups "
                    "(_season VARCHAR, _entity VARCHAR, TEAM_ID BIGINT, "
                    " GROUP_NAME VARCHAR, MIN DOUBLE, PLUS_MINUS DOUBLE)")
        con.execute("INSERT INTO silver_lineups VALUES "
                    "('2024-25', 'team:1610612747', 1610612747, "
                    " 'Avery-Bradley-Caruso-Dolson-Erhun', 120.0, 6.5)")
        con.execute("INSERT INTO silver_lineups VALUES "
                    "('2023-24', 'team:1610612738', 1610612738, "
                    " 'Brown-Tatum-Horford-White-Pritchard', 120.0, 8.0)")
    finally:
        con.close()
    tools = catalogue()
    queries = [
        "SELECT season, _season, PTS AS total_points, _source FROM silver_hist_player_seasons ORDER BY PTS",
        "SELECT _season, PTS, _source FROM silver_leaders_pts",
        "SELECT PTS FROM silver_leaders_pts WHERE PTS < 0",
        "SELECT missing_column FROM silver_leaders_pts",
        "SELECT PTS FROM silver_unavailable",
        "DELETE FROM silver_leaders_pts",
    ]
    args = [{"sql": sql} for sql in queries]
    direct = [await tools["sql_exec"].ainvoke(arg) for arg in args]
    schema = await tools["warehouse_schema"].ainvoke({})
    (root / "python-baseline.json").write_text(
        json.dumps({"args": args, "direct": direct, "schema": schema}), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
