import assert from "node:assert/strict";
import test from "node:test";
import {
  bindingDiagnostics,
  diffDiagnostics,
  diffMarker,
  fastFailVerdict,
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

const RUN_A = `event: binding_diagnostic
data: {"run_id":"run-12b45b4ccf1b4059a53cfb14f4262a33","claim_index":0,"requirement_kind":"evidence","requirement_id":"celtics_ratings_2024_25","output_id":"NET_RATING","node_id":"node_ratings","evidence_id":"team_ratings:846a59cd8b5b96a7","selector":"rows[0].NET_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"9.4"},"declared_unit":{"kind":"declared","value":"points_per_100_possessions"},"reanchor_changed":false,"rejection":"binding evidence ownership is invalid"}

event: binding_diagnostic
data: {"run_id":"run-12b45b4ccf1b4059a53cfb14f4262a33","claim_index":1,"requirement_kind":"evidence","requirement_id":"celtics_ratings_2024_25","output_id":"OFF_RATING","node_id":"node_ratings","evidence_id":"team_ratings:846a59cd8b5b96a7","selector":"rows[0].OFF_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"118.2"},"declared_unit":{"kind":"declared","value":"points_per_100_possessions"},"reanchor_changed":false,"rejection":"binding evidence ownership is invalid"}
`;

const RUN_B = `event: binding_diagnostic
data: {"run_id":"run-5feb4808b6d34181a637e6790829c802","claim_index":0,"requirement_kind":"task","output_id":"OFF_RATING","node_id":"team_ratings:846a59cd8b5b96a7","evidence_id":"team_ratings:846a59cd8b5b96a7","selector":"rows[0].OFF_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"118.2"},"declared_unit":{"kind":"declared","value":"points per 100 possessions"},"reanchor_changed":false,"rejection":"binding unit does not match output authority"}

event: binding_diagnostic
data: {"run_id":"run-5feb4808b6d34181a637e6790829c802","claim_index":2,"requirement_kind":"task","output_id":"NET_RATING","node_id":"team_ratings:846a59cd8b5b96a7","evidence_id":"team_ratings:846a59cd8b5b96a7","selector":"rows[0].NET_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"9.4"},"declared_unit":{"kind":"declared","value":"points per 100 possessions"},"reanchor_changed":false,"rejection":"binding unit does not match output authority"}

event: binding_diagnostic
data: {"run_id":"run-5feb4808b6d34181a637e6790829c802","claim_index":1,"requirement_kind":"task","output_id":"DEF_RATING","node_id":"team_ratings:846a59cd8b5b96a7","evidence_id":"team_ratings:846a59cd8b5b96a7","selector":"rows[0].DEF_RATING","row_selector":"rows[0]","subject_selector":"rows[0].TEAM_ID","subject_entity_type":"team","subject_entity_id":"BOS","declared_value":{"kind":"float","value":"108.8"},"declared_unit":{"kind":"declared","value":"points per 100 possessions"},"reanchor_changed":false,"rejection":"binding unit does not match output authority"}
`;

test("run diff aligns by output and marks changed gates", () => {
  const left = bindingDiagnostics(parseSseText(RUN_A));
  const right = bindingDiagnostics(parseSseText(RUN_B));
  const rows = diffDiagnostics(left, right);
  assert.deepEqual(
    rows.map((r) => r.output_id),
    ["NET_RATING", "OFF_RATING", "DEF_RATING"],
  );
  const net = rows[0];
  assert.equal(diffMarker(net), "changed");
  assert.equal(net.left?.rejection, "binding evidence ownership is invalid");
  assert.equal(net.right?.rejection, "binding unit does not match output authority");
  assert.equal(diffMarker(rows[1]), "changed");
  assert.equal(diffMarker(rows[2]), "only in run B");
  assert.equal(rows[2].left, null);
});

test("identical runs diff clean", () => {
  const left = bindingDiagnostics(parseSseText(RUN_A));
  const rows = diffDiagnostics(left, left);
  assert.ok(rows.length > 0);
  for (const row of rows) {
    assert.equal(diffMarker(row), "same");
    assert.equal(row.changed, false);
  }
});

const FAST_FAIL_FIXTURE = `event: work_log
data: {"run_id":"run-b2cee69e8fb148f187ef19c1fe34038f","status":"partial"}

event: final_answer
data: {"text":"I could not verify a publishable answer from the available data. ","carry":{"run_id":"run-b2cee69e8fb148f187ef19c1fe34038f","verification":"partial","verified_claims":0,"structural_flags":[],"gaps":[{"kind":"execution_failure","blocks":[]}],"stage_latencies_ms":{"understand":306}}}

event: graph_end
data: {}
`;

test("fast-fail verdict fires on sub-second understand with execution failure", () => {
  const verdict = fastFailVerdict(parseSseText(FAST_FAIL_FIXTURE));
  assert.equal(verdict.fastFail, true);
  assert.equal(verdict.understandMs, 306);
  assert.deepEqual(verdict.gapKinds, ["execution_failure"]);
});

test("slow or clean runs are not fast-fails", () => {
  assert.equal(fastFailVerdict(parseSseText(FIXTURE)).fastFail, false);
  assert.equal(fastFailVerdict([]).fastFail, false);
  assert.equal(
    fastFailVerdict(parseSseText('event: final_answer\ndata: {"text":"ok"}\n\n')).fastFail,
    false,
  );
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
