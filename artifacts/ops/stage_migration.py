"""Stage the migration of the project layout into the git worktree.

Three kinds of change:

  ADD     paper/, artifacts/, slides/, and the top-level project files
  REMOVE  root template.tex and template.pdf, which the paper/ copy replaces.
          Leaving both would put two mutually contradictory manuscripts in one
          repository, which is worse than either version alone.
  KEEP    root figures, decks, template_backup.pdf and mtim_paper.* -- those are
          not ours to delete; they are reported to the user instead.

Scratch snapshots created during this work and the 11.5 MB regenerable
per-step log are excluded.
"""
import fnmatch
import pathlib
import shutil

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
    # An earlier draft of the ns-3 scenario. The live copy is
    # artifacts/ns3/mtim_uav_trust.cc, and that is the one the traces were
    # generated from, so the draft is not carried.
    "artifacts/scratch",
    # Full per-arm run snapshots: 44 MB of regenerable intermediate data.
    # The four files each analysis script actually reads are committed in
    # artifacts/analysis/runs/ instead.
    "artifacts/runs",
    "artifacts/analysis/runs/__pycache__",
    "paper/archive",
    "paper/Definitions/__pycache__",
}
EXCLUDE_GLOBS = {
    # The converted trust streams are 8.4 MB and are regenerated from the
    # committed raw ns-3 traces by the committed converter, so they are not
    # carried. The per-trace metrics and the regime verdicts next to them
    # are the evidence the manuscript's packet-level table rests on, and
    # they are small enough to keep.
    "artifacts/outputs/logs/ns3_multitrace/*_streams.csv",
}
EXCLUDE_FILES = {
    "artifacts/outputs/logs/per_step_trust_streams.csv",
    # LaTeX byproducts: .gitignore already declares these unwanted
    "paper/template.aux",
    "paper/template.log",
    "paper/template.out",
    "paper/pass1.log",
    "paper/pass2.log",
}
TOP_FILES = [".gitignore", "Makefile", "build.bat", "README.md",
             "REPOSITORY_STRUCTURE.md"]

added, skipped = [], []


def rel(p: pathlib.Path) -> str:
    return p.relative_to(SRC).as_posix()


def walk(base_rel: str):
    base = SRC / base_rel
    if not base.exists():
        return
    for f in base.rglob("*"):
        if not f.is_file():
            continue
        r = rel(f)
        if any(r == d or r.startswith(d + "/") for d in EXCLUDE_DIRS):
            skipped.append(r)
            continue
        if r in EXCLUDE_FILES:
            skipped.append(r)
            continue
        if any(fnmatch.fnmatch(r, g) for g in EXCLUDE_GLOBS):
            skipped.append(r)
            continue
        if f.suffix in {".aux", ".log", ".out", ".fls", ".fdb_latexmk",
                        ".bbl", ".blg"}:
            skipped.append(r)
            continue
        yield f, r


for base_rel in ("paper", "artifacts", "slides"):
    for f, r in walk(base_rel):
        target = DST / r
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        added.append(r)

for name in TOP_FILES:
    f = SRC / name
    if f.exists():
        shutil.copy2(f, DST / name)
        added.append(name)

# empty scratch directories would otherwise be created by earlier runs
for d in EXCLUDE_DIRS:
    t = DST / d
    if t.is_dir() and not any(t.iterdir()):
        t.rmdir()
        print(f"removed empty scratch dir: {d}")

print(f"staged {len(added)} files")
print(f"excluded {len(skipped)} files")
print()
print("excluded, for the record:")
for s in sorted(skipped):
    print(f"  {s}")

total = sum((DST / a).stat().st_size for a in added if (DST / a).exists())
print()
print(f"total staged bytes: {total/1024/1024:.2f} MB")