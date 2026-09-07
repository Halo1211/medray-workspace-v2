import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("medray_launcher", Path(__file__).resolve().parents[2] / "scripts/launch.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.mark.parametrize("version,expected", [("v21.7.2", False), ("v22.11.0", False), ("v22.12.0", True), ("v24.1.0", True), ("broken", False)])
def test_node_compatibility(version, expected):
    assert launcher.supported_node(version) is expected


def test_duplicate_launch_lock_and_unicode_path(tmp_path):
    path = tmp_path / "folder with spaces é"
    path.mkdir()
    first = launcher.acquire_lock(path / "launcher.lock")
    assert first is not None
    try:
        assert launcher.acquire_lock(path / "launcher.lock") is None
    finally:
        first.close()
    second = launcher.acquire_lock(path / "launcher.lock")
    assert second is not None
    second.close()


def test_failed_service_readiness_has_actionable_error():
    with pytest.raises(RuntimeError, match="Setup MedRay"):
        launcher.wait_ready(type("Stopped", (), {"poll": lambda _: 1})(), "http://127.0.0.1:1")


def test_windows_job_closes_its_child_process():
    import os
    import sys
    import subprocess
    if os.name != "nt":
        pytest.skip("Windows process lifecycle check")
    job_spec = importlib.util.spec_from_file_location("windows_job", Path(launcher.ROOT) / "scripts/windows_job.py")
    module = importlib.util.module_from_spec(job_spec)
    job_spec.loader.exec_module(module)
    job = module.WindowsJob()
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        job.assign(process.pid)
        job.close()
        process.wait(timeout=5)
        assert process.poll() is not None
    finally:
        job.close()
        if process.poll() is None:
            process.kill()
        process.wait()
