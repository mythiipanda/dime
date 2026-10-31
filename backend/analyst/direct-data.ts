import { McpClient, StdioTransport } from "@earendil-works/pi-mcp";
import { fileURLToPath } from "node:url";
import { objectValue, type PythonToolsOptions } from "./python-tools.js";
export type DirectOperations = {
    product_save_chat: {
        thread: string;
        role: string;
        content: string;
        owner: string;
    };
    product_save_run: {
        thread: string;
        question: string;
        answer: string;
        owner: string;
        run_id: string;
    };
    product_threads: {
        owner: string;
    };
    product_runs: {
        thread: string;
        owner: string;
    };
    product_warehouse_identity: Record<string, never>;
    product_warehouse_health: Record<string, never>;
    product_dataset: {
        name: string;
        season: string;
        player_id: number;
        team_id: number;
        game_id: string;
        game_date: string;
        stat: string;
        ids: string;
        player_a: string;
        player_b: string;
        fmt: string;
    };
    product_freshness: Record<string, never>;
    product_rerun: {
        sql: string;
    };
    product_resolve: {
        query: string;
    };
    product_trade: {
        team_a: string;
        players_a: string;
        team_b: string;
        players_b: string;
        season: string;
    };
    product_debate: {
        a: string;
        b: string;
        season: string;
    };
    product_today: {
        season: string;
    };
    product_briefing: {
        season: string;
    };
    product_watchlist: {
        season: string;
    };
    product_watchlist_add: {
        entity_type: string;
        entity_id: string;
        season: string;
    };
    product_watchlist_remove: {
        entity_type: string;
        entity_id: string;
    };
    product_movers: {
        season: string;
        days: number;
    };
};
export async function connectDirectData(options: PythonToolsOptions) {
    const transport = new StdioTransport({ command: options.python, args: ["-B", fileURLToPath(new URL("../python_tools.py", import.meta.url))], cwd: options.cwd, env: options.env, inheritEnv: false, maxStderrBytes: 65536 });
    const client = new McpClient({ name: "dime-product", version: "1", requestTimeoutMs: 360000 });
    try {
        await client.connect(transport);
    }
    catch (error) {
        await client.close();
        throw error;
    }
    return {
        async call<N extends keyof DirectOperations>(name: N, args: DirectOperations[N], signal?: AbortSignal) {
            const result = await client.callTool(name, args, { signal });
            if (result.isError)
                throw new Error("Data operation failed");
            const text = result.content.flatMap(item => item.type === "text" ? [item.text] : []).join("\n");
            const value: unknown = result.structuredContent ?? JSON.parse(text);
            const object = objectValue(value);
            if (!object)
                throw new Error("Invalid data operation result");
            return object;
        },
        close: () => client.close(),
    };
}
export type DirectData = Awaited<ReturnType<typeof connectDirectData>>;
