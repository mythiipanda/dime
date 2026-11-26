from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_routing_bullet_carries_max_tier_math():
    src = (ROOT / "backend/analyst/runtime.ts").read_text()
    assert "25%/30%/35% of the cap" in src
    assert "0-6/7-9/10+ years of service" in src


def test_cap_skill_has_tier_recipe():
    src = (ROOT / "backend/analyst/skills/free-agency-and-cap/SKILL.md").read_text()
    assert "Max-Contract Tier Math" in src
    assert "25% of cap" in src and "30%" in src and "35%" in src
