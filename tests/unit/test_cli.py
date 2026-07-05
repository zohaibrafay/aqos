import subprocess
import sys


def test_cli_version():

    result = subprocess.run(
        [sys.executable, "-m", "aqos.cli", "version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_cli_health():

    result = subprocess.run(
        [sys.executable, "-m", "aqos.cli", "health"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "healthy" in result.stdout


def test_cli_run():

    result = subprocess.run(
        [sys.executable, "-m", "aqos.cli", "run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0