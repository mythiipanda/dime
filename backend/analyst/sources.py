"""Opaque Pi records linked through the existing owner/thread conversation ledger."""
import json
import re
from pathlib import Path


def _artifacts(conversations, directory, owner, thread):
    artifacts = {}
    for run_id in dict.fromkeys(ref.run_id for ref in conversations.references(owner, thread) if ref.run_id):
        if not re.fullmatch(r"run-[a-f0-9]{32}", run_id):
            continue
        path = Path(directory) / f"{run_id}.json"
        if not path.is_file():
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("run_id") != run_id:
            raise ValueError("Source artifact identity mismatch")
        artifacts[run_id] = value
    return artifacts


def _records(artifacts):
    return {record["ref"]: record for artifact in artifacts.values() for record in artifact["sources"]}


def read_sources(conversations, directory, owner, thread, run_id):
    if not re.fullmatch(r"run-[a-f0-9]{32}", run_id):
        raise ValueError("Invalid run")
    artifacts = _artifacts(conversations, directory, owner, thread)
    if run_id not in artifacts:
        raise FileNotFoundError(run_id)
    artifact = artifacts[run_id]
    records = _records(artifacts)
    refs = artifact.get("source_refs", [record["ref"] for record in artifact["sources"]])
    try:
        return {"run_id": run_id, "sources": [records[ref] for ref in refs]}
    except KeyError as error:
        raise FileNotFoundError(run_id) from error


def prior_sources(conversations, directory, owner, thread):
    return list(_records(_artifacts(conversations, directory, owner, thread)).values())


def source_refs(records):
    return [record["ref"] for record in records]
