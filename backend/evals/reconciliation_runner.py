from evals.reconciliation_scorer import score_task


def run_benchmark(rows, model_fn):
    per_slice = {}
    failed = []
    for task in rows:
        result = score_task(task, model_fn(task))
        entry = per_slice.setdefault(task["slice"], {"total": 0, "passed": 0})
        entry["total"] += 1
        if result["passed"]:
            entry["passed"] += 1
        else:
            failed.append(task["task_id"])
    report = {"total": len(rows), "slices": {}, "failed": failed}
    for name, entry in per_slice.items():
        report["slices"][name] = {
            "total": entry["total"],
            "passed": entry["passed"],
            "pass_rate": entry["passed"] / entry["total"],
        }
    return report
