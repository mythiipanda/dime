import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import sqlglot
from sqlglot import exp
_CHILD_SRC = (
"import sys,json\n"
"def main():\n"
"    req=json.load(sys.stdin)\n"
"    try:\n"
"        import duckdb\n"
"    except Exception as e:\n"
"        sys.stdout.write(json.dumps({\"ok\":False,\"error\":\"duckdb import failed: \"+str(e)}))\n"
"        return\n"
"    try:\n"
"        con=duckdb.connect(req[\"input_path\"],read_only=True,config={\"enable_external_access\":\"false\",\"autoinstall_known_extensions\":\"false\",\"autoload_known_extensions\":\"false\",\"lock_configuration\":\"true\"})\n"
"    except Exception as e:\n"
"        sys.stdout.write(json.dumps({\"ok\":False,\"error\":\"duckdb connect failed: \"+str(e)}))\n"
"        return\n"
"    try:\n"
"        cur=con.sql(req[\"sql\"])\n"
"        cols=[d[0] for d in cur.description] if cur.description else []\n"
"        rows=cur.fetchall()\n"
"        con.close()\n"
"    except Exception as e:\n"
"        sys.stdout.write(json.dumps({\"ok\":False,\"error\":\"duckdb query failed: \"+str(e)}))\n"
"        return\n"
"    out=[[float(c) if isinstance(c,float) else c for c in r] for r in rows]\n"
"    sys.stdout.write(json.dumps({\"ok\":True,\"columns\":cols,\"rows\":out}))\n"
"main()\n"
)
_THROUGH_WORDS = frozenset(["SELECT", "WITH", "VALUES"])
_WRITE_WORDS = frozenset(["DELETE", "INSERT", "UPDATE", "DROP", "CREATE", "ALTER", "TRUNCATE", "MERGE", "REPLACE", "GRANT", "REVOKE", "VACUUM", "CHECKPOINT"])
@dataclass(frozen=True)
class EnforcementState:
    job_object: str = "unsupported"
    tree_termination: str = "unsupported"
    stdin_gate: str = "unsupported"
    isolated_environment: str = "unsupported"
@dataclass(frozen=True)
class AnalysisRequest:
    run_id: str
    node_id: str
    sql: str
    input_path: str
    input_sha256: str
    artifact_dir: str
    deadline_s: float = 20.0
    row_cap: int = 25
    byte_cap: int = 65536
    allowed_tables: tuple = ()
    memory_limit_bytes: object = None
@dataclass
class AnalysisResult:
    status: str
    rows: object = None
    columns: object = None
    error: object = None
    dead: bool = False
    pid: object = None
    row_cap_hit: bool = False
    truncated: bool = False
    enforcement: EnforcementState = field(default_factory=EnforcementState)
    run_id: str = ""
    node_id: str = ""
    input_sha256: str = ""
def _sha_of(path: str):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
def _first_word(sql):
    nodes = _statement_nodes(sql)
    if nodes is None:
        return ""
    return type(nodes[0]).__name__
_THROUGH_TYPES = frozenset(["Select", "Values", "Union", "Intersect", "Except"])
_GATE_TYPES = frozenset(["Attach", "Copy", "Install", "Command", "Pragma", "Set"])
_DIALECT = "duckdb"
_LITERAL_FUNCTIONS = frozenset([
    "read_csv",
    "read_csv_auto",
    "read_parquet",
    "read_json",
    "read_json_auto",
    "read_blob",
    "parquet_scan",
    "csv_scan",
    "parquet_metadata",
    "sniff_csv",
    "delta_scan",
    "iceberg_scan",
    "glob",
])
_BARE_FUNCTIONS = frozenset(["current_schema", "current_catalog", "current_database"])
def _is_path_like(value):
    if not value:
        return False
    if value.startswith(("http://", "https://", "s3://", "file://", "gs://", "gcs://", "az://", "s3a://", "abfs://", "hf://")):
        return True
    if "/" in value or "\\" in value:
        return True
    if len(value) > 1 and value[1] == ":" and value[0].isalpha():
        return True
    low = value.lower()
    if low.endswith((".csv", ".parquet", ".json", ".jsonl", ".ndjson", ".tsv", ".gz", ".zip", ".duckdb", ".db", ".sqlite", ".xlsx")):
        return True
    return False
def _collect_arguments(node):
    args = []
    if isinstance(node, exp.Anonymous):
        args = list(node.args.get("expressions") or [])
    elif isinstance(node, exp.Func):
        for key in ("this", "expression", "path", "table", "table_name", "name"):
            if key in node.args:
                args.append(node.args[key])
    else:
        args = list(node.args.values()) if node.args else []
    out = []
    for arg in args:
        if isinstance(arg, exp.Expression):
            out.append(arg)
        elif isinstance(arg, list):
            out.extend(v for v in arg if isinstance(v, exp.Expression))
    return out
def _literal_of(node):
    if node is None:
        return None
    if isinstance(node, exp.Literal):
        return node.this
    if isinstance(node, exp.Var):
        return node.name
    if isinstance(node, exp.Column):
        return ".".join(p for p in (node.catalog, node.db, node.name) if p)
    return None
def _relation_key(name):
    if name is None:
        return None
    parts = []
    for part in str(name).split("."):
        part = part.strip().strip('"').strip("'").strip("`")
        if part != "":
            parts.append(part)
    if not parts:
        return None
    return tuple(parts)
def _statement_nodes(sql):
    try:
        trees = sqlglot.parse(sql, read=_DIALECT)
    except Exception:
        return None
    nodes = [t for t in trees if t is not None]
    if not nodes:
        return None
    return nodes
def _cte_aliases(nodes):
    aliases = set()
    for node in nodes:
        for cte in node.find_all(exp.CTE):
            if cte.alias:
                aliases.add(cte.alias.lower())
    return aliases
def _table_reference(table, cte_aliases):
    qualified = bool(table.db or table.catalog)
    if not qualified and table.name.lower() in cte_aliases:
        return None
    if qualified:
        parts = [p for p in (table.catalog, table.db, table.name) if p]
    else:
        parts = [table.name]
    return _relation_key(".".join(parts))
def _function_references(func):
    if func.name.lower() in _BARE_FUNCTIONS:
        return []
    keys = []
    for arg in _collect_arguments(func):
        text = _literal_of(arg)
        if text is None or _is_path_like(text):
            continue
        keys.append(_relation_key(text))
    return keys
def _record_relation(relations, seen, key):
    if key is None or key in seen:
        return
    seen.add(key)
    relations.append(key)
def _referenced_relations(nodes):
    relations = []
    seen = set()
    cte_aliases = _cte_aliases(nodes)
    for node in nodes:
        for table in node.find_all(exp.Table):
            _record_relation(relations, seen, _table_reference(table, cte_aliases))
        for func in node.find_all(exp.Anonymous):
            for key in _function_references(func):
                _record_relation(relations, seen, key)
    return relations
def _relation_allowed(key, allowed):
    if not key:
        return False
    lowered = tuple(part.lower() for part in key)
    component = lowered[-1]
    if component == "duckdb_memory":
        return True
    if component == "information_schema":
        return True
    for candidate in allowed:
        cand = _relation_key(candidate)
        if not cand:
            continue
        cand = tuple(part.lower() for part in cand)
        if cand[-1] != component:
            continue
        if len(cand) > len(lowered):
            continue
        if lowered[-len(cand):] == cand:
            return True
    return False
def _policy_rejected_references(request, allowed_names):
    allowed = set(allowed_names or ())
    if not allowed:
        return _policy_rejected(request, "no tables approved for this run")
    nodes = _statement_nodes(request.sql)
    if nodes is None:
        return _policy_rejected(request, "statement could not be parsed")
    for node in nodes:
        if not isinstance(node, (exp.Select, exp.SetOperation, exp.Values, exp.With)):
            return _policy_rejected(request, "statement rejected: " + type(node).__name__)
        for func in node.find_all(exp.Anonymous):
            if func.name.lower() in _LITERAL_FUNCTIONS:
                return _policy_rejected(request, "external file function rejected: " + func.name.lower())
    for key in _referenced_relations(nodes):
        if not _relation_allowed(key, allowed):
            return _policy_rejected(request, "unauthorized table: " + ".".join(key))
    return None
class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]
class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_ulonglong),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]
class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOBOBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
def _create_job(limit):
    if os.name != "nt":
        return (None, "unsupported: non-windows host")
    try:
        k = ctypes.windll.kernel32
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k.SetInformationJobObject.restype = wintypes.BOOL
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        handle = k.CreateJobObjectW(None, None)
        if not handle:
            return (None, "unsupported: CreateJobObjectW failed")
        ext = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        limit_val = None
        if limit is not None:
            try:
                limit_val = int(limit)
            except Exception as e:
                k.CloseHandle(wintypes.HANDLE(handle))
                return (None, "unsupported: memory limit not an integer: " + str(e))
            if limit_val <= 0:
                k.CloseHandle(wintypes.HANDLE(handle))
                return (None, "unsupported: memory limit must be positive")
            flags |= _JOB_OBJECT_LIMIT_PROCESS_MEMORY | _JOB_OBJECT_LIMIT_JOB_MEMORY
            ext.ProcessMemoryLimit = limit_val
            ext.JobMemoryLimit = limit_val
        ext.BasicLimitInformation.LimitFlags = flags
        ok = k.SetInformationJobObject(
            wintypes.HANDLE(handle),
            _JOBOBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(ext),
            ctypes.sizeof(ext),
        )
        if not ok:
            err = ctypes.get_last_error()
            k.CloseHandle(wintypes.HANDLE(handle))
            if limit is not None:
                return (None, "unsupported: memory limit rejected by OS: " + str(err))
            return (None, "unsupported: SetInformationJobObject failed: " + str(err))
        if limit is not None:
            return (int(handle), "established with memory limit " + str(limit_val))
        return (int(handle), "established")
    except Exception as e:
        return (None, "unsupported: " + str(e))
def _assign_to_job(job, proc):
    try:
        k = ctypes.windll.kernel32
        k.AssignProcessToJobObject.restype = wintypes.BOOL
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        ok = k.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(proc._handle))
        return bool(ok)
    except Exception:
        return False
def _terminate_job(job):
    try:
        k = ctypes.windll.kernel32
        k.TerminateJobObject.restype = wintypes.BOOL
        k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.TerminateJobObject(wintypes.HANDLE(job), 1)
    except Exception:
        pass
def _close_job(job):
    try:
        k = ctypes.windll.kernel32
        k.CloseHandle.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle(wintypes.HANDLE(job))
    except Exception:
        pass
def _policy_rejected(request, reason):
    return AnalysisResult(status="policy_rejected", rows=None, columns=None, error=reason, dead=False, pid=None, enforcement=EnforcementState(), run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
def _failure(request, error, dead, pid, enforcement):
    return AnalysisResult(status="execution_failed", rows=None, columns=None, error=error, dead=dead, pid=pid, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
def _admit_request(request):
    try:
        os.makedirs(request.artifact_dir, exist_ok=True)
    except Exception as e:
        return _failure(request, "artifact dir failed: " + str(e), False, None, EnforcementState())
    try:
        actual = _sha_of(request.input_path)
    except Exception as e:
        return _failure(request, "input read failed: " + str(e), False, None, EnforcementState())
    if actual.lower() != str(request.input_sha256).lower():
        return _policy_rejected(request, "input pin mismatch")
    return None
def _admit_statement(request):
    nodes = _statement_nodes(request.sql)
    if nodes is None:
        return _policy_rejected(request, "statement could not be parsed")
    for node in nodes:
        kind = type(node).__name__
        if kind in _WRITE_WORDS:
            return _policy_rejected(request, "write statement rejected")
        if kind not in _THROUGH_TYPES and kind not in _GATE_TYPES:
            return _policy_rejected(request, "statement rejected: " + kind)
    return _policy_rejected_references(request, request.allowed_tables or ())
def _child_payload(request):
    return json.dumps({"input_path": request.input_path, "sql": request.sql, "row_cap": request.row_cap})
def _spawn_child(request, job, enforcement):
    try:
        proc = subprocess.Popen([sys.executable, "-I", "-B", "-c", _CHILD_SRC], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        _close_job(job)
        return None, _failure(request, "spawn failed: " + str(e), False, None, enforcement)
    return proc, None
def _reap_child(job, proc):
    _terminate_job(job)
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass
def _assign_child(job, proc, request, enforcement):
    if _assign_to_job(job, proc):
        return None
    _reap_child(job, proc)
    _close_job(job)
    return _failure(request, "job assignment failed", True, proc.pid, enforcement)
def _write_payload(proc, payload):
    try:
        proc.stdin.write(payload.encode("utf-8"))
        proc.stdin.close()
    except Exception:
        pass
def _child_status(proc, request, cancel_event):
    start = time.monotonic()
    while True:
        if cancel_event is not None and cancel_event.is_set():
            return "cancelled"
        if proc.poll() is not None:
            return None
        if (time.monotonic() - start) > float(request.deadline_s):
            return "timeout"
        time.sleep(0.02)
def _stop_child(job, proc, status, request, enforcement):
    _reap_child(job, proc)
    try:
        proc.communicate(timeout=5)
    except Exception:
        pass
    dead = proc.poll() is not None
    _close_job(job)
    return AnalysisResult(status=status, rows=None, columns=None, error=None, dead=bool(dead), pid=proc.pid, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
def _collect_child(job, proc, request, enforcement):
    try:
        stdout_data, _ = proc.communicate(timeout=10)
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        _close_job(job)
        dead = proc.poll() is not None
        return None, dead, _failure(request, "collect failed: " + str(e), dead, proc.pid, enforcement)
    dead = proc.poll() is not None
    _close_job(job)
    return stdout_data, dead, None
def _truncate_rows(rows, cap):
    truncated = False
    while rows and len(json.dumps(rows)) > cap:
        rows = rows[:-1]
        truncated = True
    return rows, truncated
def _shape_result(request, stdout_data, dead, pid, enforcement):
    try:
        doc = json.loads(stdout_data.decode("utf-8", errors="replace") or "{}")
    except Exception as e:
        return _failure(request, "bad child output: " + str(e), bool(dead), pid, enforcement)
    if not doc.get("ok"):
        return _failure(request, doc.get("error") or "duckdb failed", bool(dead), pid, enforcement)
    columns = tuple(doc.get("columns") or [])
    rows = [list(r) for r in (doc.get("rows") or [])]
    row_cap_hit = False
    if len(rows) > int(request.row_cap):
        rows = rows[:int(request.row_cap)]
        row_cap_hit = True
    rows, truncated = _truncate_rows(rows, int(request.byte_cap))
    return AnalysisResult(status="success", rows=rows, columns=columns, error=None, dead=bool(dead), pid=pid, row_cap_hit=row_cap_hit, truncated=truncated, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
def execute_analysis(request, cancel_event=None):
    rejected = _admit_request(request)
    if rejected is not None:
        return rejected
    rejected = _admit_statement(request)
    if rejected is not None:
        return rejected
    job, job_reason = _create_job(request.memory_limit_bytes)
    if job is None:
        return AnalysisResult(status="unsupported", rows=None, columns=None, error=job_reason, dead=False, pid=None, enforcement=EnforcementState(job_object=job_reason), run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    enforcement = EnforcementState(job_object=job_reason, tree_termination="job terminate", stdin_gate="stdin request gate", isolated_environment="-I -B allowlist")
    payload = _child_payload(request)
    proc, failure = _spawn_child(request, job, enforcement)
    if failure is not None:
        return failure
    failure = _assign_child(job, proc, request, enforcement)
    if failure is not None:
        return failure
    _write_payload(proc, payload)
    status = _child_status(proc, request, cancel_event)
    if status is not None:
        return _stop_child(job, proc, status, request, enforcement)
    stdout_data, dead, failure = _collect_child(job, proc, request, enforcement)
    if failure is not None:
        return failure
    return _shape_result(request, stdout_data, dead, proc.pid, enforcement)
def build_envelope(result, evidence_id, capability, source, observed_at):
    from v2.contracts import EvidenceEnvelope
    table = []
    cols = list(result.columns or [])
    for row in (result.rows or []):
        table.append({str(k): v for k, v in zip(cols, list(row))})
    lineage = ["run:" + str(result.run_id), "node:" + str(result.node_id), "input:" + str(result.input_sha256)[:16]]
    return EvidenceEnvelope(evidence_id=evidence_id, capability=capability, source=source, observed_at=observed_at, rows=table, lineage=lineage)
