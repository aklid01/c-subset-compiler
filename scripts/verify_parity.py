import os
import sys
import shutil
import subprocess

def run_compiler(input_path):
    cmd = [sys.executable, "-X", "utf8", "main.py", input_path]
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
    return res.stdout, res.stderr

def get_generated_files():
    files = {}
    for folder in ["output", "traces"]:
        if os.path.exists(folder):
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        files[os.path.join(folder, name).replace("\\", "/")] = f.read()
    return files

def record_golden():
    os.makedirs("golden/artifacts/input/output", exist_ok=True)
    os.makedirs("golden/artifacts/input/traces", exist_ok=True)
    os.makedirs("golden/artifacts/code/output", exist_ok=True)
    os.makedirs("golden/artifacts/code/traces", exist_ok=True)

    stdout, _ = run_compiler("input/input.txt")
    with open("golden/input_stdout.txt", "w", encoding="utf-8") as f:
        f.write(stdout)
    for folder in ["output", "traces"]:
        if os.path.exists(folder):
            for name in os.listdir(folder):
                src = os.path.join(folder, name)
                if os.path.isfile(src):
                    dst = os.path.join("golden/artifacts/input", folder, name)
                    shutil.copy2(src, dst)

    stdout, _ = run_compiler("code.txt")
    with open("golden/code_stdout.txt", "w", encoding="utf-8") as f:
        f.write(stdout)
    for folder in ["output", "traces"]:
        if os.path.exists(folder):
            for name in os.listdir(folder):
                src = os.path.join(folder, name)
                if os.path.isfile(src):
                    dst = os.path.join("golden/artifacts/code", folder, name)
                    shutil.copy2(src, dst)

    print("Golden files successfully recorded.")

def check_parity():
    if not os.path.exists("golden/input_stdout.txt") or not os.path.exists("golden/code_stdout.txt"):
        print("Error: Golden files do not exist. Run with --record first.")
        sys.exit(1)

    mismatch = False

    for key, input_file, golden_stdout_path, artifact_sub in [
        ("input", "input/input.txt", "golden/input_stdout.txt", "golden/artifacts/input"),
        ("code", "code.txt", "golden/code_stdout.txt", "golden/artifacts/code")
    ]:
        stdout, _ = run_compiler(input_file)
        with open(golden_stdout_path, "r", encoding="utf-8") as f:
            golden_stdout = f.read()

        if stdout != golden_stdout:
            print(f"FAIL: Stdout mismatch for {input_file}")
            mismatch = True
        else:
            print(f"PASS: Stdout matches for {input_file}")

        for folder in ["output", "traces"]:
            src_dir = folder
            gold_dir = os.path.join(artifact_sub, folder)
            if os.path.exists(gold_dir):
                for name in os.listdir(gold_dir):
                    gold_path = os.path.join(gold_dir, name)
                    curr_path = os.path.join(src_dir, name)
                    if os.path.isfile(gold_path):
                        if not os.path.exists(curr_path):
                            print(f"FAIL: Expected file {curr_path} was not generated")
                            mismatch = True
                            continue
                        with open(gold_path, "r", encoding="utf-8") as f:
                            gold_content = f.read()
                        with open(curr_path, "r", encoding="utf-8") as f:
                            curr_content = f.read()
                        if gold_content != curr_content:
                            print(f"FAIL: Content mismatch in {curr_path}")
                            mismatch = True
                        else:
                            print(f"PASS: {curr_path} matches golden copy")

    if mismatch:
        print("PARITY CHECK FAILED")
        sys.exit(1)
    else:
        print("PARITY CHECK PASSED")
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--record":
        record_golden()
    else:
        check_parity()
