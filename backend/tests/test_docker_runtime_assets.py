from pathlib import Path


def test_docker_image_includes_analyst_build_inputs_and_runtime_skills():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    packaging, runtime = dockerfile.split("FROM python:3.11-slim-bookworm AS runtime", 1)
    assert "COPY analyst/*.py analyst/*.ts analyst/tsconfig.json analyst/gen-manifest.mjs ./" in packaging
    assert "COPY analyst/skills ./skills" in packaging
    assert "COPY --from=analyst-deps /analyst /srv/analyst" in runtime
