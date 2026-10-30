"""Real Python host -> Node Pi -> Python MCP -> SSE, with owned fixture storage."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import ctypes
import unittest

# verify_product.py sets isolated environment before this interpreter imports product code.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyst.product_session import stream_product_session
from v2.conversations import ConversationStore


class ProductStore:
    # Run the existing storage implementation between workers, so the proof does not
    # keep two Python dependency graphs resident under the ordinary 1 GiB cap.
    def __getattr__(self, name):
        def call(*args, **kwargs):
            code = ("import sys,json;sys.path.insert(0,sys.argv[1]);"
                    "from shared import store;"
                    "a,k=json.loads(sys.argv[3]);getattr(store,sys.argv[2])(*a,**k)")
            if name == "save_run":
                code += (";assert store.list_runs(a[0],owner=k['owner'])[0]['answer']==a[2];"
                         "assert any(c['role']=='ai' for c in store.chat_history(a[0]))")
            subprocess.run([sys.executable, "-B", "-c", code,
                            str(Path(__file__).resolve().parents[1]), name,
                            json.dumps([args, kwargs])], check=True,
                           cwd=os.environ["DIME_PI_TEST_ROOT"], env=dict(os.environ))
        return call


store = ProductStore()


class ProductSessionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = Path(os.environ["DIME_PI_TEST_ROOT"])
        self.conversations = ConversationStore(self.root / "conversations.sqlite")

    def stream(self, scenario="normal", **overrides):
        return stream_product_session(q="fixture question", model={"scenario": scenario},
            node=shutil.which("node"), python=sys.executable, env=dict(os.environ),
            warehouse=(self.root / "absent.duckdb" if scenario == "bridge" else os.environ["DIME_WAREHOUSE"]),
            private_root=self.root / "private",
            sources_dir=self.root / "sources", conversations=self.conversations,
            store=store, client="fixture", thread="thread",
            worker=Path(__file__).with_name("product_fixture.mjs"), **overrides)

    async def collect(self, scenario="normal"):
        chunks = [chunk async for chunk in self.stream(scenario)]
        (self.root / f"{scenario}-sse.json").write_text(json.dumps(chunks))
        events = [(chunk.splitlines()[0][7:], json.loads(chunk.splitlines()[1][6:])) for chunk in chunks]
        self.assertEqual(sum(name == "graph_end" for name, _ in events), 1)
        self.assert_closed()
        return events

    def assert_closed(self):
        events = [json.loads(line) for line in (self.root / "worker-events.jsonl").read_text().splitlines()]
        pids = [int((self.root / "worker.pid").read_text())]
        pids += [event["pid"] for event in events if event["type"] == "closed" and event.get("pid")]
        for pid in pids:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                try:
                    status = ctypes.c_ulong()
                    ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(status))
                    self.assertNotEqual(status.value, 259, f"process {pid} still active")
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)

    async def test_session(self):
        events = await self.collect()
        self.assertNotIn("failure", [name for name, _ in events], events)
        results = [data for name, data in events if name == "tool_result"]
        self.assertEqual([r["status"] for r in results], ["fail", "ok"])
        final = next(data for name, data in events if name == "final_answer")
        self.assertEqual(final["carry"]["verification"], "unassessed")
        self.assertNotIn("verified_claims", final["carry"])
        artifact = json.loads((self.root / "sources" / (final["carry"]["run_id"] + ".json")).read_text())
        self.assertEqual(len(artifact["sources"]), 2)
        good = json.loads(artifact["sources"][1]["response"]["content"][0]["text"])
        self.assertEqual(good["rows"], [{"PTS": 71}])
        self.assertFalse(any((self.root / "private").iterdir()))

    async def test_followup(self):
        for i in range(5):
            self.conversations.append_exchange("fixture", "thread", f"prior {i}", f"answer {i}")
        expected = [t.model_dump() for t in self.conversations.read("fixture", "thread")]
        await self.collect()
        context = json.loads((self.root / "requests.jsonl").read_text().splitlines()[0])
        prior = context["messages"][:8]
        self.assertEqual([m["role"] for m in prior], [t["role"] for t in expected])
        self.assertEqual([m["content"] if isinstance(m["content"], str) else m["content"][0]["text"] for m in prior],
                         [t["content"] for t in expected])
        self.assertFalse(any((self.root / "private").iterdir()))

    async def check_failure(self, scenario, kind):
        events = await self.collect(scenario)
        self.assertEqual(next(d["kind"] for n, d in events if n == "failure"), kind)
        self.assertFalse(any(n == "final_answer" for n, _ in events))
        self.assertEqual(self.conversations.read("fixture", "thread"), [])
        if scenario == "startup":
            await self.collect()

    async def test_startup(self):
        await self.check_failure("startup", "configuration")

    async def test_model(self):
        await self.check_failure("model", "model")
        artifacts = list((self.root / "sources").glob("*.json"))
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(len(json.loads(artifacts[0].read_text())["sources"]), 2)

    async def test_bridge(self):
        await self.check_failure("bridge", "startup")

    async def test_recovery(self):
        self.assertEqual(self.conversations.read("fixture", "thread"), [])
        await self.collect()

    async def test_cancel(self):
        async def drain():
            return [chunk async for chunk in self.stream("cancel")]
        task = asyncio.create_task(drain())
        for _ in range(600):
            if (self.root / "entered").exists():
                break
            await asyncio.sleep(.02)
        self.assertTrue((self.root / "entered").exists())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(any((self.root / "private").iterdir()))
        self.assertEqual(self.conversations.read("fixture", "thread"), [])
        self.assert_closed()


if __name__ == "__main__":
    unittest.main()
