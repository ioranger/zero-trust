"""List files that differ between the dev tree and the git worktree.

Read-only comparison: no copying, no mutation. Used to scope what a
stage_migration.py run would actually change before running it.
"""
import hashlib
import pathlib
import sys

SRC = pathlib.Path(r"F:\zero trust\zero-trust")
DST = pathlib.Path(r"F:\zero trust\gitwork")

EXCLUDE_DIRS = {
    "artifacts/outputs/_baseline13",
    "artifacts/outputs/_mixed_provenance",
    "artifacts/outputs/_no_modality",
    "artifacts/outputs/_pre_domainaug",
    "artifacts/outputs/_pre_spatial",
    "artifacts/outputs/_shape13_seed60",
    "artifacts/outputs/_shape18_seed10",
    "artifacts/outputs/_shape18_seed60",
    "artifacts/outputs/logs/__pycache__",
    "artifacts/runs",
    "artifacts/analysis/runs/__pycache__",
    "paper/archive",
    "paper/Definitions/__pycache__",
}
EXCLUDE_FILES = {
    "artifacts/outputs/logs/per_step_trust_streams.csv",
}
SKIP_SUFFIX = {".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".bbl", ".blg"}


def excluded(rel: str) -> bool:
    if rel in EXCLUDE_FILES:
        return True
    if any(rel == d or rel.startswith(d + "/") for d in EXCLUDE_DIRS):
        return True
    return pathlib.Path(rel).suffix in SKIP_SUFFIX


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    changed, added, removed = [], [], []
    for base_rel in ("paper", "artifacts", "slides"):
        base = SRC / base_rel
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(SRC).as_posix()
            if excluded(rel):
                continue
            t = DST / rel
            if not t.exists():
                added.append((rel, f.stat().st_size))
            elif sha(f) != sha(t):
                changed.append((rel, f.stat().st_size))
        base_d = DST / base_rel
        if base_d.exists():
            for f in base_d.rglob("*"):
                if not f.is_file():
                    continue
                rel = f.relative_to(DST).as_posix()
                if excluded(rel):
                    continue
                if not (SRC / rel).exists():
                    removed.append(rel)

    print(f"CHANGED ({len(changed)}):")
    for rel, size in changed:
        print(f"  {rel}  ({size/1024:.1f} KB)")
    print(f"\nADDED ({len(added)}):")
    for rel, size in added:
        print(f"  {rel}  ({size/1024:.1f} KB)")
    print(f"\nREMOVED ({len(removed)}):")
    for rel in removed:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
