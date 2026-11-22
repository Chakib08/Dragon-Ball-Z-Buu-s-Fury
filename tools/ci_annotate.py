#!/usr/bin/env python3
"""Turn a failed CI step's output into GitHub error annotations, so the
reason shows on the run's summary page (annotations are visible without
opening, or being allowed to download, the logs).

    python tools/ci_annotate.py tests <unittest output file>
        one annotation per failing test: its name and the end of its traceback
    python tools/ci_annotate.py tail <output file> [title]
        one annotation with the last lines of the output

Used by the workflows in .github/workflows/ when a step fails.
"""

import re
import sys

# GitHub keeps 10 error annotations per step
MAX_ANNOTATIONS = 10
TRACE_LINES = 14
TAIL_LINES = 40


def escape(text):
    """Workflow command escaping (the message is one line)."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotate(title, message):
    print(f"::error title={escape(title).replace(',', '%2C').replace(':', '%3A')}::{escape(message)}")


def tests(text):
    """unittest's report: each failure starts with a line of '=' and
    'FAIL: test' or 'ERROR: test', then a line of '-' and its traceback."""
    blocks = re.split(r"^={20,}\n", text, flags=re.M)[1:]
    count = 0
    for block in blocks:
        lines = block.splitlines()
        if not lines or not lines[0].startswith(("FAIL:", "ERROR:")):
            continue
        title = lines[0]
        body = [line for line in lines[1:] if not set(line) <= set("-")]
        # The traceback ends where unittest's summary starts
        for index, line in enumerate(body):
            if line.startswith("Ran ") and " test" in line:
                body = body[:index]
                break
        annotate(title, "\n".join(body[-TRACE_LINES:]))
        count += 1
        if count == MAX_ANNOTATIONS:
            break
    summary = [line for line in text.splitlines() if line.startswith(("Ran ", "FAILED", "OK"))]
    if count == 0:
        # No test report (the tests did not even start): the end of the output
        tail(text, "Tests did not run")
    print("\n".join(summary))


def tail(text, title="Step failed"):
    annotate(title, "\n".join(text.splitlines()[-TAIL_LINES:]))


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("tests", "tail"):
        sys.exit(__doc__)
    with open(sys.argv[2], encoding="utf-8", errors="replace") as file:
        text = file.read()
    if sys.argv[1] == "tests":
        tests(text)
    else:
        tail(text, sys.argv[3] if len(sys.argv) > 3 else "Step failed")


if __name__ == "__main__":
    main()
