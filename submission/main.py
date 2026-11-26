"""Run the offline Secret Wards Phase A regex pipeline."""
import argparse
import os
from pathlib import Path
import sys

from rakshak.formats import UnsafeInput
from rakshak.release import publish_release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    secret = os.environ.get("RAKSHA_SECRET", "")
    if not secret:
        print("release failed: missing_secret", file=sys.stderr)
        return 1
    try:
        counts = publish_release(args.input, args.output, secret.encode())
    except UnsafeInput as exc:
        print("release failed: " + exc.args[0], file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print("release failed: filesystem_error", file=sys.stderr)
        return 1
    print("files", counts["files_total"], "sanitized", counts["files_sanitized"],
          "quarantined", counts["files_quarantined"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
