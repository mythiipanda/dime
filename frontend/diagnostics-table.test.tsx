import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { DiagnosticsTable, RevisionCard } from "./components/DiagnosticsTable";
import { DiffTable, FastFailBanner } from "./app/diagnostics/page";
import { bindingDiagnostics, parseSseText } from "./lib/diagnostics";

const FIXTURE = `event: binding_diagnostic
data: {"run_id":"run-ccbce16e085d4d4f81db412cdb45df51","claim_index":0,"requirement_kind":"task","output_id":"PLAYER_NAME","node_id":"qualified_leaders:05b5922eaefae72d","evidence_id":"qualified_leaders:05b5922eaefae72d","selector":"rows[0].PLAYER_NAME","row_selector":"rows[0]","subject_selector":"rows[0].PLAYER_ID","subject_entity_type":"player","subject_entity_id":"1629027","declared_value":{"kind":"string","value":"Trae Young"},"declared_unit":{"kind":"unitless","value":null},"reanchor_changed":false,"rejection":"binding evidence ownership is invalid"}

event: binding_diagnostic
data: {"run_id":"run-ccbce16e085d4d4f81db412cdb45df51","claim_index":0,"requirement_kind":"task","output_id":"AST","node_id":"qualified_leaders:05b5922eaefae72d","evidence_id":"qualified_leaders:05b5922eaefae72d","selector":"rows[0].AST","row_selector":"rows[0]","subject_selector":"rows[0].PLAYER_ID","subject_entity_type":"player","subject_entity_id":"1629027","declared_value":{"kind":"integer","value":"880"},"declared_unit":{"kind":"declared","value":"count"},"reanchor_changed":false,"rejection":"binding evidence ownership is invalid"}
`;

describe("diagnostics table", () => {
  it("renders probe events in order with all diagnostic fields", () => {
    const rows = bindingDiagnostics(parseSseText(FIXTURE));
    const html = renderToStaticMarkup(React.createElement(DiagnosticsTable, { rows }));
    const nameAt = html.indexOf("PLAYER_NAME");
    const astAt = html.indexOf(">AST<");
    assert.ok(nameAt !== -1 && astAt !== -1 && nameAt < astAt);
    for (const token of [
      "rows[0].PLAYER_NAME",
      "rows[0]",
      "rows[0].PLAYER_ID",
      "1629027",
      "Trae Young",
      "880",
      "binding evidence ownership is invalid",
    ]) {
      assert.ok(html.includes(token), "missing " + token);
    }
  });

  it("renders domain and capability when the fixture carries them", () => {
    const frame = `event: binding_diagnostic
data: {"run_id":"run-x","claim_index":1,"requirement_kind":"evidence","requirement_id":"ratings","output_id":"NET_RATING","node_id":"ratings","evidence_id":"ev-1","selector":"rows[5].NET_RATING","row_selector":"rows[5]","subject_selector":"rows[5].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":99.9},"declared_unit":{"kind":"declared","value":"points_per_100_possessions"},"domain":"team_ratings","evidence_capability":"team_ratings","reanchor_changed":true,"rejection":"binding evidence ownership is invalid"}
`;
    const rows = bindingDiagnostics(parseSseText(frame));
    assert.equal(rows.length, 1);
    const html = renderToStaticMarkup(React.createElement(DiagnosticsTable, { rows }));
    assert.ok(html.includes("team_ratings"));
    assert.ok(html.includes("changed"));
  });

  it("older fixtures without the fields render clean", () => {
    const rows = bindingDiagnostics(parseSseText(FIXTURE));
    const html = renderToStaticMarkup(React.createElement(DiagnosticsTable, { rows }));
    assert.ok(!html.includes("undefined"));
    assert.ok(!html.includes("null"));
  });

  it("renders run diff with both rejection strings and markers", () => {
    const runA = `event: binding_diagnostic
data: {"run_id":"run-a","claim_index":0,"requirement_kind":"evidence","requirement_id":"celtics_ratings_2024_25","output_id":"NET_RATING","node_id":"node_ratings","evidence_id":"ev-1","selector":"rows[0].NET_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"9.4"},"declared_unit":{"kind":"declared","value":"points_per_100_possessions"},"reanchor_changed":false,"rejection":"binding evidence ownership is invalid"}
`;
    const runB = `event: binding_diagnostic
data: {"run_id":"run-b","claim_index":2,"requirement_kind":"task","output_id":"NET_RATING","node_id":"team_ratings:x","evidence_id":"team_ratings:x","selector":"rows[0].NET_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"9.4"},"declared_unit":{"kind":"declared","value":"points per 100 possessions"},"reanchor_changed":false,"rejection":"binding unit does not match output authority"}

event: binding_diagnostic
data: {"run_id":"run-b","claim_index":1,"requirement_kind":"task","output_id":"DEF_RATING","node_id":"team_ratings:x","evidence_id":"team_ratings:x","selector":"rows[0].DEF_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"108.8"},"declared_unit":{"kind":"declared","value":"points per 100 possessions"},"reanchor_changed":false,"rejection":"binding unit does not match output authority"}
`;
    const html = renderToStaticMarkup(
      React.createElement(DiffTable, { leftText: runA, rightText: runB }),
    );
    const netAt = html.indexOf("NET_RATING");
    const defAt = html.indexOf("DEF_RATING");
    assert.ok(netAt !== -1 && defAt !== -1 && netAt < defAt);
    for (const token of [
      "binding evidence ownership is invalid",
      "binding unit does not match output authority",
      "changed",
      "only in run B",
    ]) {
      assert.ok(html.includes(token), "missing " + token);
    }
  });

  it("banners the fast-fail verdict with exact gap string", () => {
    const sse = `event: work_log
data: {"run_id":"run-x","status":"partial"}

event: final_answer
data: {"text":"I could not verify a publishable answer from the available data. ","carry":{"run_id":"run-x","verification":"partial","verified_claims":0,"structural_flags":[],"gaps":[{"kind":"execution_failure","blocks":[]}],"stage_latencies_ms":{"understand":306}}}

event: graph_end
data: {}
`;
    const html = renderToStaticMarkup(
      React.createElement(FastFailBanner, { events: parseSseText(sse) }),
    );
    assert.ok(html.includes("Fast fail"));
    assert.ok(html.includes("306"));
    assert.ok(html.includes("execution_failure"));
  });

  it("banner stays silent without a fast-fail", () => {
    const html = renderToStaticMarkup(
      React.createElement(FastFailBanner, { events: parseSseText(FIXTURE) }),
    );
    assert.equal(html, "");
  });

  it("renders revision hash plus runtime flag", () => {
    const html = renderToStaticMarkup(
      React.createElement(RevisionCard, {
        info: { revision: "168e2f31abc123", runtime: "v2" },
      }),
    );
    assert.ok(html.includes("168e2f31"));
    assert.ok(!html.includes("168e2f31abc123"));
    assert.ok(html.includes("v2"));
  });

  it("renders plain words when revision is missing", () => {
    const html = renderToStaticMarkup(React.createElement(RevisionCard, { info: null }));
    assert.ok(html.includes("revision unavailable"));
  });

  it("renders nothing without rows", () => {
    assert.equal(
      renderToStaticMarkup(React.createElement(DiagnosticsTable, { rows: [] })),
      "",
    );
  });
});
