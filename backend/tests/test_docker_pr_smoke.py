from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "build-backend.yml").read_text())


def container_filters():
    steps = workflow()["jobs"]["changes"]["steps"]
    filter_step = next(step for step in steps if step.get("id") == "f")
    return set(yaml.safe_load(filter_step["with"]["filters"])["container"])


def analyst_copy_sources():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text()
    packaging = dockerfile.split("FROM python:3.11-slim-bookworm AS runtime", 1)[0]
    sources = []
    for line in packaging.splitlines():
        parts = line.split()
        if parts[:1] != ["COPY"]:
            continue
        sources.extend(part for part in parts[1:-1] if not part.startswith("--"))
    return sources


def expected_filter(source):
    path = "backend/" + source
    if "*" in source:
        return path
    if (ROOT / "backend" / source).is_dir():
        return path + "/**"
    return path


def test_container_filter_covers_every_analyst_packaging_input():
    filters = container_filters()
    missing = [expected_filter(source) for source in analyst_copy_sources()
               if expected_filter(source) not in filters]
    assert missing == []
    assert "backend/Dockerfile" in filters
    assert "backend/.dockerignore" in filters


def test_pr_container_smoke_builds_analyst_deps_without_publishing():
    job = workflow()["jobs"]["container-smoke"]
    assert "github.event_name == 'pull_request'" in job["if"]
    assert "needs.changes.outputs.container == 'true'" in job["if"]
    build_steps = [step for step in job["steps"] if "docker build" in step.get("run", "")]
    assert len(build_steps) == 1
    build = build_steps[0]
    assert build["working-directory"] == "backend"
    assert "--target analyst-deps" in build["run"]
    assert "--push" not in build["run"]
    assert "docker push" not in build["run"]
    assert all("docker/login-action" not in step.get("uses", "") for step in job["steps"])
