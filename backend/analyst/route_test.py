"""Actual ASGI route with resident product storage and real synthetic Pi/MCP."""
import asyncio
import ctypes
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi import FastAPI
from analyst import product_session
from v2.api import routes
from shared import store

app = FastAPI()
app.include_router(routes.router, prefix="/api")
original = product_session.stream_product_session
root = Path(os.environ["DIME_PI_TEST_ROOT"])


def fixture_stream(**kwargs):
    kwargs["worker"] = Path(__file__).with_name("product_fixture.mjs")
    kwargs["model"] = {"scenario": os.environ.get("SCENARIO", "normal"), "priorRef": os.environ.get("PRIOR_REF")}
    kwargs["env"] = {**kwargs["env"], "DIME_PI_TEST_ROOT": str(root)}
    return original(**kwargs)


class RouteTest(unittest.IsolatedAsyncioTestCase):
    async def request(self, **body):
        with patch.object(product_session, "stream_product_session", fixture_stream):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
                return await client.post("/api/v2/chat/stream", json={"q":"fixture question", "model":"reflection:beam-1", "client":"fixture", "thread":"thread", **body})

    def events(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        events = [(frame.splitlines()[0][7:], json.loads(frame.splitlines()[1][6:])) for frame in response.text.strip().split("\n\n")]
        self.assertEqual(sum(n == "graph_end" for n,d in events), 1)
        return events

    def closed(self):
        records = [json.loads(line) for line in (root / "worker-events.jsonl").read_text().splitlines()]
        pids = [int((root / "worker.pid").read_text())] + [r["pid"] for r in records if r["type"] == "closed" and r.get("pid")]
        for pid in pids:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                try:
                    status = ctypes.c_ulong()
                    ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(status))
                    self.assertNotEqual(status.value, 259)
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)

    async def route_normal(self):
        response = await self.request()
        events = self.events(response)
        self.assertFalse(any(n == "failure" for n,d in events), events)
        final = next(d for n,d in events if n == "final_answer")
        self.assertNotIn("verified_claims", final["carry"])
        self.assertEqual(sum(n == "token" for n,d in events), 1)
        worker_events = [json.loads(line) for line in (root / "worker-events.jsonl").read_text().splitlines()]
        self.assertTrue(any(event["type"] == "token" for event in worker_events))
        self.assertEqual(response.headers["x-dime-run-id"], final["carry"]["run_id"])
        artifact = routes.run_sources(final["carry"]["run_id"], "thread", "fixture")
        self.assertEqual(len(artifact["sources"]), 2)
        good = json.loads(artifact["sources"][1]["response"]["content"][0]["text"])
        self.assertEqual(good["rows"], [{"PTS":71}])
        self.assertEqual(store.list_runs("thread", owner="fixture")[0]["answer"], final["text"])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
            self.assertEqual((await client.get(f"/api/v2/runs/{artifact['run_id']}/sources", params={"thread":"thread","client":"other"})).status_code,404)
        (root / "normal-sse.json").write_text(json.dumps([frame+"\n\n" for frame in response.text.strip().split("\n\n")]))
        (root / "route-artifact.json").write_text(json.dumps(artifact))
        self.closed()

    async def route_followup(self):
        prior = json.loads((root / "route-artifact.json").read_text())
        artifact_path = root / "sources" / (prior["run_id"] + ".json")
        raw = json.loads(prior["sources"][1]["response"]["content"][0]["text"])
        raw["rows"][0]["secret"] = "RAW_SECRET_ROW"
        prior["sources"][1]["response"]["content"][0]["text"] = json.dumps(raw)
        prior["sources"][0]["response"] = {"isError": True, "content": [
            {"type": "text", "text": "RAW_SECRET_ROW: tool exception"}]}
        artifact_path.write_text(json.dumps(prior))
        os.environ["SCENARIO"] = "followup"
        os.environ["PRIOR_REF"] = prior["sources"][1]["ref"]
        (root / "requests.jsonl").write_text("")
        parent_run = routes._CONVERSATIONS.references("fixture", "thread")[-1].run_id
        final = next(d for n,d in self.events(await self.request(q="Use prior sources")) if n == "final_answer")
        self.assertTrue(set(s["ref"] for s in prior["sources"]) <= set(final["carry"]["source_refs"]))
        requests = (root / "requests.jsonl").read_text().splitlines()
        self.assertIn(prior["sources"][1]["ref"], requests[-1])
        # The provider sees the catalogue and filtered output, never raw records.
        self.assertTrue(all("RAW_SECRET_ROW" not in request for request in requests))
        self.assertIn('\"retrieved\":true', requests[-1].replace('\\"', '"'))
        self.assertIn("total_points", requests[-1])
        self.assertIn('\"denied\":true', requests[-1].replace('\\"', '"'))
        durable = json.loads((root / "sources" / (final["carry"]["run_id"] + ".json")).read_text())
        self.assertEqual(durable["sources"], [])
        retrieved = routes.run_sources(final["carry"]["run_id"], "thread", "fixture")
        self.assertIn(prior["sources"][1], retrieved["sources"])
        branches = routes._CONVERSATIONS.list_branches("fixture", "thread")
        self.assertEqual(branches[-1].parent_run_id, parent_run)
        artifact_path = root / "sources" / (prior["run_id"] + ".json")
        artifact_path.write_text(json.dumps({**prior, "run_id": "run-" + "0" * 32}))
        try:
            from fastapi import HTTPException
            with self.assertRaises(HTTPException): routes.run_sources(prior["run_id"], "thread", "fixture")
        finally:
            artifact_path.write_text(json.dumps(prior))
        self.closed()

    async def route_configuration(self):
        events = self.events(await self.request(model="openrouter:unapproved:free"))
        self.assertTrue(any(n == "failure" and d["kind"] == "configuration" for n,d in events))
        self.assertFalse(any(n == "final_answer" for n,d in events))

    async def route_model(self):
        os.environ["SCENARIO"] = "model_immediate"
        events = self.events(await self.request())
        self.assertTrue(any(n == "failure" and d["kind"] == "model" for n,d in events),events)
        self.assertFalse(any(n == "final_answer" for n,d in events))
        self.assertEqual(routes._CONVERSATIONS.read("fixture","thread"), [])
        self.assertEqual(store.list_runs("thread",owner="fixture"), [])
        self.closed()

    async def route_disconnect(self):
        os.environ["SCENARIO"] = "cancel"
        sent = False
        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type":"http.request","body":json.dumps({"q":"cancel", "client":"fixture", "thread":"thread", "model":"reflection:beam-1"}).encode()}
            for _ in range(1000):
                if (root / "entered").exists():
                    return {"type":"http.disconnect"}
                await asyncio.sleep(.01)
            raise AssertionError("worker never entered")
        chunks=[]
        async def send(message): chunks.append(message)
        scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.0"},"http_version":"1.1","method":"POST","scheme":"http","path":"/api/v2/chat/stream","raw_path":b"/api/v2/chat/stream","query_string":b"","headers":[(b"content-type",b"application/json")],"client":("fixture",123),"server":("fixture",80),"root_path":""}
        with patch.object(product_session,"stream_product_session",fixture_stream):
            await app(scope,receive,send)
        self.assertEqual(routes._CONVERSATIONS.read("fixture","thread"), [])
        self.assertFalse(any((root / "private").iterdir()))
        self.closed()

if __name__ == "__main__": unittest.main()
