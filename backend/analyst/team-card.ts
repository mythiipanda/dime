import { Type } from "typebox";
import { Value } from "typebox/value";
import {
    field, selector, sectionSchema,
    resolveSourceRow, resolveMetrics, resolveFields, resolveProvenance
} from "./player-card.js";
import type { SourceRecord } from "./python-tools.js";

export const teamCardSchema = Type.Object({
    kind: Type.Literal("team_card"),
    title: field,
    ref: field,
    row: Type.Integer({ minimum: 0 }),
    nameColumn: field,
    metrics: Type.Array(selector, { minItems: 1, maxItems: 6 }),
    sections: Type.Optional(Type.Array(sectionSchema, { minItems: 1, maxItems: 6 }))
}, { additionalProperties: false });

export function resolveTeamCard(artifact: Record<string, unknown>, getSource: (ref: string) => SourceRecord | undefined): Record<string, unknown> {
    if (!Value.Check(teamCardSchema, artifact))
        throw new Error("Invalid team_card: provide title, ref, row, nameColumn and 1-6 metrics with column/label selectors, plus optional sections of {label, ref, row, metrics, fields}; do not provide values or units.");
    const { record, row, data } = resolveSourceRow(artifact.ref, artifact.row, getSource, "team_card");
    const teamName = row[artifact.nameColumn];
    if (typeof teamName !== "string" || !teamName.trim())
        throw new Error("team_card nameColumn must select a text field.");
    const metrics = resolveMetrics(row, data, artifact.metrics, "team_card");
    const sections = (artifact.sections ?? []).map(section => {
        if (!section.metrics && !section.fields)
            throw new Error(`team_card section '${section.label}' needs at least one metric or field.`);
        const resolved = resolveSourceRow(section.ref, section.row, getSource, "team_card section");
        return {
            label: section.label,
            sourceRef: section.ref, sourceRow: section.row,
            ...(section.metrics ? { metrics: resolveMetrics(resolved.row, resolved.data, section.metrics, "team_card section") } : {}),
            ...(section.fields ? { fields: resolveFields(resolved.row, section.fields, "team_card section") } : {}),
            provenance: resolveProvenance(resolved.record, resolved.data)
        };
    });
    return {
        kind: "team_card", title: artifact.title, teamName,
        sourceRef: artifact.ref, sourceRow: artifact.row,
        nameColumn: artifact.nameColumn,
        metrics,
        ...(sections.length ? { sections } : {}),
        provenance: resolveProvenance(record, data)
    };
}
