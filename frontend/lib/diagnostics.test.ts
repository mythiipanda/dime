import assert from "node:assert/strict";
import test from "node:test";
import {
  bindingDiagnostics,
  isBindingDiagnostic,
  parseSseText,
} from "./diagnostics";

const FIXTURE = `event: binding_diagnostic
data: {"run_id":"run-ccbce16e085d4d4f81db412cdb45df51","claim_index":0,"requirement_kind":"task","output_id":"PLAYER_NAME","node_id":"qualified_leaders:05b5922eaefae72d","evidence_id":"qualified_leaders:05b5922eaefae72d","selector":"rows[0].PLAYER_NAME","row_selector":"rows[0]","subject_selector":"rows[0].PLAYER_ID","subject_entity_type":"player","subject_entity_id":"1629027","declared_value":{"kind":"string","value":"Trae Young"},"declared_unit":{"kind":"unitless","value":null},"reanchor_changed":false,"rejection":"binding evidence ownership is invalid"}

event: binding_diagnostic
data: {"run_id":"run-ccbce16e085d4d4f81db412cdb45df51","claim_index":0,"requirement_kind":"task","output_id":"AST","node_id":"qualified_leaders:05b5922eaefae72d","evidence_id":"qualified_leaders:05b5922eaefae72d","selector":"rows[0].AST","row_selector":"rows[0]","subject_selector":"rows[0].PLAYER_ID","subject_entity_type":"player","subject_entity_id":"1629027","declared_value":{"kind":"integer","value":"880"},"declared_unit":{"kind":"declared","value":"count"},"reanchor_changed":false,"rejection":"binding evidence ownership is invalid"}

event: final_answer
data: {"text":"Some requested outputs could not be published.","carry":{"run_id":"run-ccbce16e085d4d4f81db412cdb45df51","verification":"partial","verified_claims":1}}
`;

test("probe frames parse in order with all diagnostic fields", () => {
  const events = parseSseText(FIXTURE);
  assert.equal(events.length, 3);
  assert.deepEqual(
    events.map((e) => e.type),
    ["binding_diagnostic", "binding_diagnostic", "final_answer"],
  );
  const diags = bindingDiagnostics(events);
  assert.equal(diags.length, 2);
  assert.equal(diags[0].output_id, "PLAYER_NAME");
  assert.equal(diags[0].selector, "rows[0].PLAYER_NAME");
  assert.equal(diags[0].row_selector, "rows[0]");
  assert.equal(diags[0].subject_selector, "rows[0].PLAYER_ID");
  assert.equal(diags[0].subject_entity_id, "1629027");
  assert.equal(diags[0].reanchor_changed, false);
  assert.equal(diags[0].rejection, "binding evidence ownership is invalid");
  assert.equal(diags[1].output_id, "AST");
});

test("junk frames are skipped without throwing", () => {
  assert.deepEqual(parseSseText(""), []);
  assert.deepEqual(parseSseText("keep-alive\n\n"), []);
  const events = parseSseText("event: node_update\ndata: not json\n\n");
  assert.equal(events.length, 1);
  assert.equal(events[0].data, "not json");
  assert.equal(bindingDiagnostics(events).length, 0);
});

test("diagnostic guard rejects other payloads", () => {
  assert.equal(isBindingDiagnostic(null), false);
  assert.equal(isBindingDiagnostic("x"), false);
  assert.equal(isBindingDiagnostic({ output_id: "AST" }), false);
  assert.equal(
    isBindingDiagnostic({ output_id: "AST", rejection: "no", claim_index: 0 }),
    true,
  );
});
