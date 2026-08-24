from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> dict[str, object]:
    path = ROOT / ".github" / "workflows" / name
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_ci_runs_the_complete_local_acceptance_contract() -> None:
    workflow = _workflow("ci.yml")
    job = workflow["jobs"]["validate"]
    commands = "\n".join(
        step.get("run", "") for step in job["steps"] if isinstance(step, dict)
    )

    assert workflow["permissions"] == {"contents": "read"}
    assert "python -m ruff check ." in commands
    assert "python -m pytest -q" in commands
    assert "npm test" in commands
    assert "npm run build" in commands
    assert "npm run test:e2e" in commands
    assert "CONFERENCE_RELEASE_ROOT" in commands


def test_pages_deploys_only_main_or_manual_after_the_same_validation() -> None:
    workflow = _workflow("pages.yml")
    triggers = workflow["on"]
    build = workflow["jobs"]["build"]
    deploy = workflow["jobs"]["deploy"]
    commands = "\n".join(
        step.get("run", "") for step in build["steps"] if isinstance(step, dict)
    )

    assert triggers == {
        "push": {"branches": ["main"]},
        "workflow_dispatch": "",
    }
    assert "python -m pytest -q" in commands
    assert "npm test" in commands
    assert "npm run build" in commands
    assert "npm run test:e2e" in commands
    assert build["permissions"] == {"contents": "read", "pages": "read"}
    assert deploy["needs"] == "build"
    assert deploy["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    assert any(
        step.get("uses") == "actions/upload-pages-artifact@v4"
        for step in build["steps"]
    )
    assert any(
        step.get("uses") == "actions/deploy-pages@v4"
        for step in deploy["steps"]
    )
