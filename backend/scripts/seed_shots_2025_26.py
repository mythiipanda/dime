import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats

SEASON = "2025-26"
SLEEP = 0.8

def main() -> None:
    force = "--all" in sys.argv
    with store.connect() as con:
        pids = [r[0] for r in con.execute(
            "SELECT DISTINCT PLAYER_ID FROM silver_player_gamelogs "
            "ORDER BY PLAYER_ID").fetchall()]
        have = {r[0] for r in con.execute(
            "SELECT DISTINCT _entity FROM silver_shots").fetchall()}
    with store.connect() as con:
        con.execute("DELETE FROM silver_shots WHERE _entity = ''")
    todo = [p for p in pids if force or f"player:{p}" not in have]
    print(f"players={len(pids)} todo={len(todo)}", flush=True)
    failed: list[int] = []
    for i, pid in enumerate(todo, 1):
        try:
            res = nba_stats.shot_chart(pid, SEASON)
            if res.ok and res.frame.height > 0:
                store.save_frame("silver_shots", res, f"player:{pid}")
            else:
                failed.append(pid)
        except Exception as exc:
            print(f"ERR {pid}: {exc}", flush=True)
            failed.append(pid)
        if i % 25 == 0:
            print(f"{i}/{len(todo)} done, {len(failed)} failed", flush=True)
        time.sleep(SLEEP)
    for pid in list(failed):
        time.sleep(2)
        try:
            res = nba_stats.shot_chart(pid, SEASON)
            if res.ok and res.frame.height > 0:
                store.save_frame("silver_shots", res, f"player:{pid}")
                failed.remove(pid)
        except Exception:
            pass
    with store.connect() as con:
        n = con.execute("SELECT COUNT(*) FROM silver_shots").fetchone()[0]
        p = con.execute(
            "SELECT COUNT(DISTINCT _entity) FROM silver_shots").fetchone()[0]
    print(f"DONE rows={n} entities={p} failed={len(failed)}", flush=True)

if __name__ == "__main__":
    main()
