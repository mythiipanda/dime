import type { TSchema } from "typebox";
import { Value } from "typebox/value";
import { objectValue } from "./python-tools.js";
export function validationDetail(type: string, loc: (string | number)[], msg: string, input: unknown, ctx?: Record<string, unknown>) {
    return { type, loc, msg, input, ...(ctx ? { ctx } : {}), url: `https://errors.pydantic.dev/2.12/v/${type}` };
}
function atPath(input: unknown, path: (string | number)[]): unknown {
    let value = input;
    for (const key of path) {
        if (Array.isArray(value) && typeof key === "number")
            value = value[key];
        else
            value = objectValue(value)?.[key];
    }
    return value;
}
function validationContext(schema: TSchema, input: unknown) {
    return { errors: [...Value.Errors(schema, input)], rootSchema: objectValue(schema) ?? {}, input, seen: new Set<string>() };
}
function stringList(value: unknown): string[] {
    if (!Array.isArray(value))
        return [];
    return value.filter((item: unknown): item is string => typeof item === "string");
}
type ValidationContext = ReturnType<typeof validationContext>;
function formatIssue(error: ValidationContext["errors"][number], context: ValidationContext) {
    const { errors, seen, rootSchema, input } = context;
    const details: ReturnType<typeof validationDetail>[] = [];
    const path = error.instancePath.split("/").slice(1).map(part => /^\d+$/.test(part) ? Number(part) : part.replaceAll("~1", "/").replaceAll("~0", "~"));
    const loc = ["body", ...path], value = atPath(input, path), params = objectValue(error.params) ?? {};
    const add = (type: string, msg: string, ctx?: Record<string, unknown>) => details.push(validationDetail(type, loc, msg, value, ctx));
    switch (error.keyword) {
        case "required":
            for (const name of stringList(params.requiredProperties))
                details.push(validationDetail("missing", [...loc, name], "Field required", value));
            break;
        case "additionalProperties":
            for (const name of stringList(params.additionalProperties))
                details.push(validationDetail("extra_forbidden", [...loc, name], "Extra inputs are not permitted", objectValue(value)?.[name]));
            break;
        case "type": {
            const type = params.type;
            if (type === "null")
                break;
            const types: Record<string, [
                string,
                string
            ]> = { string: ["string_type", "Input should be a valid string"], integer: ["int_type", "Input should be a valid integer"], array: ["list_type", "Input should be a valid list"], object: ["model_attributes_type", "Input should be a valid dictionary or object to extract fields from"], boolean: ["bool_type", "Input should be a valid boolean"] };
            const known = typeof type === "string" ? types[type] : undefined;
            if (known)
                add(known[0], known[1]);
            break;
        }
        case "pattern": {
            if (errors.some(item => item.instancePath === error.instancePath && item.keyword === "minLength"))
                break;
            const field = path.at(-1), required = Array.isArray(rootSchema.required) && rootSchema.required.includes(String(field));
            const messages: Record<string, string> = { q: "question must be non-empty", model: "model must be non-empty when present", goal: "project goal must be non-empty", content: "conversation content must be non-empty", thread: "thread and client must be non-empty" + (required ? "" : " when present"), client: "thread and client must be non-empty" + (required ? "" : " when present"), branch_id: "branch id must be non-empty when present" };
            add("value_error", "Value error, " + (messages[String(field)] ?? "value must be non-empty"), { error: {} });
            break;
        }
        case "minimum":
            add("greater_than_equal", `Input should be greater than or equal to ${params.limit}`, { ge: params.limit });
            break;
        case "maximum":
            add("less_than_equal", `Input should be less than or equal to ${params.limit}`, { le: params.limit });
            break;
        case "minLength":
            add("string_too_short", `String should have at least ${params.limit} character${params.limit === 1 ? "" : "s"}`, { min_length: params.limit });
            break;
        case "maxLength":
            add("string_too_long", `String should have at most ${params.limit} character${params.limit === 1 ? "" : "s"}`, { max_length: params.limit });
            break;
        case "const": {
            if (seen.has(error.instancePath))
                break;
            seen.add(error.instancePath);
            const values = errors.filter(item => item.keyword === "const" && item.instancePath === error.instancePath).map(item => objectValue(item.params)?.allowedValue).filter(value => typeof value === "string");
            const expected = values.map(value => `'${value}'`).join(" or ");
            add("literal_error", "Input should be " + expected, { expected });
            break;
        }
        case "maxItems":
            add("too_long", `List should have at most ${params.limit} items after validation, not ${Array.isArray(value) ? value.length : 0}`, { field_type: "List", max_length: params.limit, actual_length: Array.isArray(value) ? value.length : 0 });
            break;
        case "anyOf":
        case "boolean": break;
        default: add("value_error", error.message);
    }
    return details;
}
export function validationDetails(schema: TSchema, input: unknown) {
    const context = validationContext(schema, input);
    const details = context.errors.flatMap(error => formatIssue(error, context));
    const order = Object.keys(objectValue(context.rootSchema.properties) ?? {});
    return details.sort((a, b) => {
        const rank = (value: typeof a) => value.type === "extra_forbidden" ? order.length : order.indexOf(String(value.loc[1]));
        return rank(a) - rank(b);
    });
}
