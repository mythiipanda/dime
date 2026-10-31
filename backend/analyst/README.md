# Analyst host

The application runs in Node and embeds Pi 1.4.0 directly. `createAnalyst().stream()` owns model selection, conversation reads/writes, source artifacts and session lifetime. HTTP and CLI call that iterable in the same process.

Build from this directory with `npm ci --ignore-scripts` and `npm run build`. Use Node 22.19 or later and install `../requirements.txt` for the Python data engine. Set `DIME_PI_PYTHON` to an absolute Python executable when it is not available as `python`.

From `backend`, generate the startup manifest and start the server:

```sh
node analyst/dist/host.js manifest manifest/expected_asset_manifest.json
DIME_EXPECTED_ASSET_MANIFEST=$PWD/manifest/expected_asset_manifest.json node analyst/dist/host.js
```

Supply provider settings in the process environment. To load an explicit env file, use Node's `--env-file=PATH` flag on each command. The CLI uses the same configuration and analyst:

```sh
node analyst/dist/host.js chat "question" --model "reflection:beam-1"
```

Reflection requires explicit activation and a key. Unsupported selections fail without a provider fallback. The adapter uses known SDK token metadata and adds no request output ceiling. Nvidia's unsupported request options produce a configuration failure.

`python_tools.py` serves explicit data operations. Pi receives only `sql_exec` and `warehouse_schema`; `read_source` is registered locally in Node. Internal product mutations remain outside codemode. Python retains the NBA domain implementation, warehouse semantics and existing DuckDB state-table functions. Provider credentials are excluded from the MCP environment.

Conversations, projects and workspaces retain their SQLite tables and disk defaults. Workspace tokens retain the existing SHA-256 identity binding and exact membership rules. Source files store new records and prior refs. Raw rows, failed results, units and provenance remain intact. Prior model context contains source metadata; scripts must call `read_source` to read prior rows. The public answer stays unassessed.

`npm run check` runs strict TypeScript checking. `verify_product.py ABS_ROOT prepare` creates a synthetic owned warehouse. Separate supervised `host` stages cover `normal`, `followup`, `cli`, `frontend`, `model` and `abort`. Normal must run first; followup reuses that root. `policy`, `inprocess`, `packaging` and `contracts BASELINE_JSON` are separate checks. The route contract baseline is captured from the previous host with controlled data dependencies.

Each proof uses the ordinary 30-second, 1-GiB, 32-process and 1-MiB output limits. Numerical pools remain at one. Runtime proof currently uses Node 24.13.1; Node 22 runtime behavior and a full container execution remain unproved. No live provider or answer-quality claim follows from the synthetic fixtures.
