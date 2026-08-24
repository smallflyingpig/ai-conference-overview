import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_installed_wheel_loads_packaged_venue_registry(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    install_dir = tmp_path / "site-packages"
    runtime_dir = tmp_path / "runtime"
    wheel_dir.mkdir()
    runtime_dir.mkdir()

    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(PROJECT_ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(wheel_dir.glob("ai_conference_overview-*.whl"))

    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(install_dir),
            str(wheel),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr

    environment = os.environ | {"PYTHONPATH": str(install_dir)}
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            """\
from conference_overview import registry
from conference_overview.registry import normalize_request
request = normalize_request('ACL', 2026, 'long')
print(registry.__file__)
print(request.source_key)
""",
        ],
        cwd=runtime_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert runtime.returncode == 0, runtime.stderr
    registry_path, source_key = runtime.stdout.splitlines()
    assert Path(registry_path).is_relative_to(install_dir)
    assert source_key == "2026.acl-long"
