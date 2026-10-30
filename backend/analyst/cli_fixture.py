"""Real CLI consumer with injected synthetic Pi configuration, no provider discovery."""
import ctypes
import asyncio
import io
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_v2_chat import main, run_question
from analyst.configuration import worker_environment

root = Path(os.environ["DIME_PI_TEST_ROOT"])
scenario = sys.argv[1].removeprefix("cli_")

def configure(model):
    assert model == "fixture:selected-model"
    if scenario == "configuration":
        raise ValueError("synthetic configuration failure")
    return dict(model={"scenario": scenario}, node=shutil.which("node"), python=sys.executable,
                worker=Path(__file__).with_name("product_fixture.mjs"),
                env={**worker_environment(), "PYTHONPATH": os.environ["PYTHONPATH"],
                     "DIME_PI_TEST_ROOT": str(root)},
                warehouse=os.environ["DIME_WAREHOUSE"], private_root=root / "private",
                sources_dir=root / "sources", conversations=None, store=None)

out, err = io.StringIO(), io.StringIO()
if scenario == "cancel":
    async def cancel():
        task = asyncio.create_task(run_question("fixture question", configure("fixture:selected-model"), stdout=out, stderr=err))
        while not (root / "requests.jsonl").exists():
            await asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return 1
        raise AssertionError("CLI request was not cancelled")
    code = asyncio.run(cancel())
else:
    code = main(["fixture question", "--model", "fixture:selected-model"],
                configure=configure, stdout=out, stderr=err)
assert "claims=" not in out.getvalue() + err.getvalue()
if scenario == "normal":
    assert code == 0, err.getvalue()
    artifacts = list((root / "sources").glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text())
    assert len(artifact["sources"]) == 2
    assert all("source: " + ref in err.getvalue() for ref in artifact["source_refs"])
    assert out.getvalue().strip()
else:
    assert code == 1
    assert not out.getvalue()
    assert err.getvalue() or scenario == "cancel"
if scenario != "configuration":
    for pid in [int((root / "worker.pid").read_text())] + [r["pid"] for r in
            map(json.loads, (root / "worker-events.jsonl").read_text().splitlines())
            if r["type"] == "closed" and r.get("pid")]:
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            try:
                status = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(status))
                assert status.value != 259
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
(root / "cli-output.json").write_text(json.dumps({"status":code,"stdout":out.getvalue(),"stderr":err.getvalue()}))
print("CLI", scenario, "passed")
