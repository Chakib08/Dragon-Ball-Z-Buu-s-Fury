#!/usr/bin/env python3
"""Start the installed iOS app once in a booted simulator, in smoke-test mode
(the SIMCTL_CHILD_DBZ_SMOKE_TEST* variables: a short fight, then it quits),
and tell whether it got through.

    python tools/ios_smoke_test.py <simulator udid> <bundle id>

The game notes its progress in Documents/smoke_test.log (src/smoke.py). If
it never says "smoke test passed", everything that may tell why is printed
and put in an error annotation (the run's logs need a sign-in to read): that
file, the app's output, its system log, a stack sample if it hangs, and a
crash report if it crashed.

Used by .github/workflows/ios.yml (macOS only: simctl, sample).
"""

import glob
import os
import subprocess
import sys
import time

TIMEOUT = 240
PASSED = "smoke test passed"


def run(*command, timeout=120):
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return done.stdout + done.stderr
    except (subprocess.TimeoutExpired, OSError) as error:
        return f"({' '.join(command[:4])}...: {error})"


def read(path, limit=None):
    try:
        with open(path, errors="replace") as file:
            text = file.read()
    except OSError:
        return f"(no {os.path.basename(path)})"
    return text[-limit:] if limit else text


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def escape(text):
    return text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def main():
    device, bundle = sys.argv[1], sys.argv[2]
    work = os.path.abspath("smoke")
    os.makedirs(work, exist_ok=True)
    out, err = os.path.join(work, "stdout.txt"), os.path.join(work, "stderr.txt")
    started = time.time()
    launch = run("xcrun", "simctl", "launch", "--terminate-running-process",
                 f"--stdout={out}", f"--stderr={err}", device, bundle)
    print("launch:", launch.strip())
    try:
        pid = int(launch.strip().rsplit(":", 1)[1])
    except (IndexError, ValueError):
        pid = None
    data = run("xcrun", "simctl", "get_app_container", device, bundle, "data").strip()
    progress_file = os.path.join(data, "Documents", "smoke_test.log")

    state = "timed out"
    while time.time() - started < TIMEOUT:
        if PASSED in read(progress_file) or PASSED in read(out):
            state = "passed"
            break
        if not alive(pid):
            time.sleep(2)  # the last notes
            state = "passed" if PASSED in read(progress_file) + read(out) else "exited"
            break
        time.sleep(2)
    elapsed = round(time.time() - started)

    progress, stdout, stderr = read(progress_file), read(out, 3000), read(err, 3000)
    print(f"== {state} after {elapsed} s (pid {pid})")
    print("== smoke_test.log\n" + progress + "\n== stdout\n" + stdout + "\n== stderr\n" + stderr)
    if state == "passed":
        print("The app started, played a fight and quit")
        return 0

    stack = ""
    if alive(pid):
        stack = run("sample", str(pid), "3", "-mayDie", timeout=60)
        run("xcrun", "simctl", "terminate", device, bundle)
    system_log = run("xcrun", "simctl", "spawn", device, "log", "show", "--last", "10m",
                     "--style", "compact", "--predicate",
                     f"processID == {pid}" if pid else 'process == "trunkshope"', timeout=180)
    crashes = sorted(glob.glob(os.path.expanduser("~/Library/Logs/DiagnosticReports/*trunkshope*")),
                     key=os.path.getmtime)
    crash = read(crashes[-1])[:6000] if crashes else "(no crash report)"
    print("== stack sample\n" + stack[:12000] + "\n== system log\n" + system_log[-12000:]
          + "\n== crash\n" + crash)

    # The main thread's frames say where a hang is
    stack_lines = [line.strip() for line in stack.splitlines() if "+" in line and "Thread" not in line]
    log_lines = [line for line in system_log.splitlines() if line.strip()]
    report = "\n".join([
        f"The app {state} after {elapsed} s without '{PASSED}' (pid {pid}, launch: {launch.strip()[:200]})",
        "smoke_test.log:", progress.strip()[-1200:],
        "stdout/stderr:", (stdout.strip() + "\n" + stderr.strip())[-1200:],
        "system log:", "\n".join(log_lines[-30:])[-2500:],
        "stack (main thread, innermost last):", "\n".join(stack_lines[:40])[-2500:],
        "crash:", crash[:1500],
    ])
    print("::error title=Smoke test in the simulator failed::" + escape(report))
    return 1


if __name__ == "__main__":
    sys.exit(main())
