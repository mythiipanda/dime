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

  it("renders nothing without rows", () => {
    assert.equal(
      renderToStaticMarkup(React.createElement(DiagnosticsTable, { rows: [] })),
      "",
    );
  });
});
