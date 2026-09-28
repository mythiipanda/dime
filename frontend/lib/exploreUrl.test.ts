// Tests for the Phase 3 shareable panel URLs (lib/exploreUrl).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  decodeParams,
  encodeParams,
  panelShareUrl,
  pickParams,
} from "./exploreUrl";

test("decodeParams parses a query string with or without the leading ?", () => {
  assert.deepEqual(decodeParams("?a=1&b=x+y"), { a: "1", b: "x y" });
  assert.deepEqual(decodeParams("a=1"), { a: "1" });
  assert.deepEqual(decodeParams(""), {});
});

test("encodeParams skips empty values and round-trips through decode", () => {
  const params = { leaders_stat: "AST", leaders_q: "", team: "BOS" };
  assert.equal(encodeParams(params), "leaders_stat=AST&team=BOS");
  assert.deepEqual(decodeParams(encodeParams(params)), {
    leaders_stat: "AST",
    team: "BOS",
  });
});

test("pickParams keeps only the panel's own keys", () => {
  const all = {
    leaders_stat: "REB",
    shots_player: "2544",
    unrelated: "1",
  };
  assert.deepEqual(pickParams(all, ["leaders_stat"]), { leaders_stat: "REB" });
  assert.deepEqual(pickParams(all, ["nope"]), {});
});

test("panelShareUrl keeps the panel params, drops the rest, adds panel + anchor", () => {
  const url = panelShareUrl(
    "https://dime.test",
    "/explore",
    "?leaders_stat=AST&shots_player=2544",
    "leaders",
  );
  assert.ok(url.startsWith("https://dime.test/explore?"), url);
  assert.ok(url.endsWith("#explore-leaders"), url);
  const qs = url.split("?")[1].split("#")[0];
  assert.deepEqual(decodeParams(qs), { leaders_stat: "AST", panel: "leaders" });
});

test("panelShareUrl works for a panel with no params", () => {
  assert.equal(
    panelShareUrl("https://dime.test", "/", "", "playoffs"),
    "https://dime.test/?panel=playoffs#explore-playoffs",
  );
});
