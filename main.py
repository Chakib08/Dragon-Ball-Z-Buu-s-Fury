import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import smoke  # noqa: E402  (no pygame: works even if pygame cannot load)

smoke.report("python started")
try:
    from main import main  # noqa: E402
    smoke.report("game code imported")
except BaseException:
    smoke.report_error()
    raise


if __name__ == "__main__":
    main()
