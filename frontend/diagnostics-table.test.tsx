import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { DiagnosticsTable } from "./components/DiagnosticsTable";
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

  it("renders nothing without rows", () => {
    assert.equal(
      renderToStaticMarkup(React.createElement(DiagnosticsTable, { rows: [] })),
      "",
    );
  });
});
