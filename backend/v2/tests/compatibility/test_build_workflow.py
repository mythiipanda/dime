from pathlib import Path


def test_backend_build_can_publish_isolated_v2_tag_with_revision():
    text = (Path(__file__).parents[4] / ".github/workflows/build-backend.yml").read_text()
    assert "image_tag:" in text
    assert "DIME_REVISION=${{ github.sha }}" in text
    assert "dime-backend:${{ inputs.image_tag || 'latest' }}" in text
