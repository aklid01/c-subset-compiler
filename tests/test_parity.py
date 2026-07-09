import os
import subprocess
import sys


def test_parity():
    script_path = os.path.join("scripts", "verify_parity.py")
    cmd = [sys.executable, script_path]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert (
        res.returncode == 0
    ), f"Parity verification failed:\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}"
