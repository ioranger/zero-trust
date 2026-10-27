"""Package the current session so it can be continued on another machine.

The conversation lives in two places on the local runtime:

  v2/sqlite/runtime-state.sqlite      the session row and the message rows
  v2/sessions/<date>/<session-id>/   the raw message log, the compaction
                                      snapshots and the tool outputs

This writes both into one zip. The database is copied through SQLite's backup
api so that the live write-ahead log is folded in and the copy is consistent,
and the transient history-mutation working copy is left out because it only
duplicates the message log.

The zip carries a RESTORE.md with the instructions.

Usage:
    python -u realdata/build_session_bundle.py
"""

from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

HOME = Path(r"C:\Users\Administrator\.minimax")
V2 = HOME / "v2"
SESSION_ID = "05-34-22-554-session_bXZzX2FmMmUzYjk4MDgyZDRkODU5NTYyYWYyN2VjNzgyZTM1"
SESSION_DIR = V2 / "sessions" / "2026" / "10" / "11" / SESSION_ID
SQLITE_DIR = V2 / "sqlite"
OUT = Path(r"F:\zero trust\realdata") / f"session_bundle_{SESSION_ID[:12]}.zip"
TMP_DB = Path(r"F:\zero trust\realdata\runtime-state.snapshot.sqlite")

RESTORE = """# Moving this conversation to another machine

The zip holds two things the runtime needs and the Git repository does not:
the session record and the message history.

## 1. The repository

    git clone https://github.com/ioranger/zero-trust.git F:\\zero trust\\zero-trust
    cd F:\\zero trust\\zero-trust
    git checkout ioranger-patch-1

Keep the same absolute path. The session records its workspace as
`F:\\zero trust`, and the analysis scripts in `artifacts/analysis` resolve the
repository as `F:\\zero trust\\zero-trust`.

## 2. This bundle

Stop MiniMax Code on the new machine first, then unpack the zip over the
runtime data directory, so that

    C:\\Users\\<you>\\.minimax\\v2\\sqlite\\runtime-state.sqlite
    C:\\Users\\<you>\\.minimax\\v2\\sessions\\2026\\10\\11\\05-34-22-554-session_bXZzX2FmMmUzYjk4MDgyZDRkODU5NTYyYWYyN2VjNzgyZTM1\\...

exist. The `sqlite/` directory in the zip holds a consistent copy of the
runtime state database, including everything the write-ahead log held.

Do NOT copy `C:\\Users\\<you>\\.minimax\\auth\\` from the old machine. Sign in
on the new one instead.

## 3. Continuing

Start MiniMax Code and open the session
`mvs_af2e3b98082d4d859562af27ec782e35` ("推进 zero-trust 仓库的投稿成稿").
"""


def main() -> int:
    if SESSION_DIR.exists():
        for stale in (TMP_DB, TMP_DB.with_suffix(".sqlite-wal"),
                      TMP_DB.with_suffix(".sqlite-shm")):
            if stale.exists():
                stale.unlink()
        src = sqlite3.connect(f"file:{(SQLITE_DIR / 'runtime-state.sqlite').as_posix()}?mode=ro",
                              uri=True)
        dst = sqlite3.connect(str(TMP_DB))
        src.backup(dst)
        dst.close()
        src.close()
        print(f"database snapshot: {TMP_DB.stat().st_size / 1024 / 1024:.1f} MB")

    written = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("RESTORE.md", RESTORE)
        z.write(TMP_DB, "sqlite/runtime-state.sqlite")
        written += 1
        for f in sorted(SESSION_DIR.rglob("*")):
            if not f.is_file():
                continue
            if any(p.startswith(".history-mutation-") for p in f.parts):
                continue
            arc = f.relative_to(V2).as_posix()
            z.write(f, arc)
            written += 1
    if TMP_DB.exists():
        TMP_DB.unlink()

    print(f"wrote {OUT}")
    print(f"  {written} entries, {OUT.stat().st_size / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
