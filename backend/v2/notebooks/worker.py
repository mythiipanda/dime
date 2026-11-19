from __future__ import annotations

import ast
import base64
import contextlib
import io
import json
import math
import sys
import traceback
from pathlib import Path


class BoundedText(io.StringIO):
    def __init__(self, path):
        super().__init__()
        self.path = Path(path)

    def write(self, text):
        remaining = max(0, 65536 - self.tell())
        super().write(text[:remaining])
        self.path.write_text(self.getvalue())
        return len(text)


def plotting(warnings):
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot
        return pyplot
    except ImportError:
        warnings.append("Figure capture is unavailable because matplotlib is not installed. Install backend requirements to enable plots.")
        return None


def main():
    job = json.loads(Path(sys.argv[1]).read_text())
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (job["cpu_s"], job["cpu_s"] + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2, 8 * 1024**2))
    except (ImportError, AttributeError, ValueError):
        pass
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    stdout, stderr = BoundedText("captured-stdout"), BoundedText("captured-stderr")
    result = {"ok": True, "tables": [], "figures": [], "warnings": []}
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            import polars as pl
            plt = plotting(result["warnings"])
            from v2.notebooks.sql import connection, validate

            def sql(query, **params):
                with connection(Path(job["warehouse"])) as con:
                    statement = validate(con, query)
                    cursor = con.execute(statement, params)
                    columns = [d[0] for d in cursor.description]
                    rows = cursor.fetchmany(5001)
                if len(rows) > 5000:
                    raise ValueError("Python sql() results are limited to 5000 rows; add a LIMIT")
                return pl.DataFrame(rows, schema=columns, orient="row", infer_schema_length=None)

            def show(obj):
                if isinstance(obj, pl.DataFrame):
                    if len(result["tables"]) >= 4:
                        raise ValueError("At most four tables can be displayed per call")
                    rows = obj.head(500).to_dicts()
                    payload = {"columns": [{"name": n, "type": str(t)} for n, t in obj.schema.items()],
                               "rows": rows, "row_count": obj.height, "truncated": obj.height > 500}
                    if len(json.dumps(payload, default=str).encode()) > 256 * 1024:
                        raise ValueError("Displayed table exceeds 256KB; select fewer columns or rows")
                    result["tables"].append(payload)
                elif hasattr(obj, "to_dict") and type(obj).__module__.startswith("pandas"):
                    show(pl.from_pandas(obj))
                else:
                    print(obj)

            namespace = {"sql": sql, "show": show, "pl": pl, "__name__": "__notebook__"}
            tree = ast.parse(job["source"], filename="<notebook>", mode="exec")
            last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            exec(compile(tree, "<notebook>", "exec"), namespace)
            if last:
                value = eval(compile(ast.Expression(last.value), "<notebook>", "eval"), namespace)
                if value is not None:
                    show(value)
            for number in plt.get_fignums() if plt else []:
                if len(result["figures"]) == 4:
                    raise ValueError("At most four figures can be displayed per call")
                image = io.BytesIO()
                plt.figure(number).savefig(image, format="png", dpi=100)
                if image.tell() > 1024 * 1024:
                    raise ValueError("Figure exceeds 1MB")
                result["figures"].append({"mime_type": "image/png", "data": base64.b64encode(image.getvalue()).decode()})
            if plt:
                plt.close("all")
    except BaseException:
        result.update(ok=False, error=traceback.format_exc()[-16000:])
    result.update(stdout=stdout.getvalue(), stderr=stderr.getvalue())
    def safe(value):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, dict):
            return {k: safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [safe(v) for v in value]
        return value
    Path("result.json").write_text(json.dumps(safe(result), default=str, allow_nan=False))


if __name__ == "__main__":
    main()
