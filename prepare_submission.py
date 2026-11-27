"""Build an allowlisted organizer checkout, including the project brief."""
import argparse
from pathlib import Path
import shutil
import tempfile


RUNTIME = Path(__file__).resolve().parent / "submission"
FILES = (
    "raksha.toml", "README.md", "requirements.txt", "main.py", "project-brief.pdf",
    "rakshak/detection.py", "rakshak/formats.py", "rakshak/release.py",
    "rakshak/source_context.py", "rakshak/linkage.py", "rakshak/quasi.py",
)


def prepare(destination):
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be a new directory")
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        staging = Path(temp) / "package"
        for name in FILES:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RUNTIME / name, target)
        staging.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        prepare(args.destination)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Could not prepare submission: {error}\n")
