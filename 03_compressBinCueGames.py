#!/usr/bin/env python3
"""
Create one 7z archive per PS1 game, grouping multiple discs together.

For each CUE in the target directory, the script:
 - Pairs it with its BIN
 - Derives a game key by stripping the disc ID ([SLES-xxxxx]/[SLUS-xxxxx]) and any
   explicit disc markers (Disc 1, Disc_2, etc.)
 - Packs all BIN/CUE files for that game into a single archive named
   \"<Game Name>.7z\" (unless it already exists and overwrite is disabled).

Usage:
  python compress_ps1_games.py [directory] [--dry-run] [--overwrite]
                               [--sevenzip /path/to/7z] [--level 9]
                               [--threads 0]
"""

import argparse
import pathlib
import re
import shutil
import subprocess
import os
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Recognize disc ID suffixes like [SLUS-00627]
CODE_SUFFIX_RE = re.compile(r"\s*\[S[LC][A-Z]{2}[A-Z]?-?\d+\]\s*$", re.IGNORECASE)
# Remove disc markers such as "(Disc 1)", "Disc_2", "_Disc3" (with or without space/underscore)
DISC_MARKER_REPS: Iterable[Tuple[re.Pattern, str]] = (
    (re.compile(r"(?i)\s*\(disc\s*\d+\)"), ""),  # (Disc 1)
    (re.compile(r"(?i)[ _-]*disc[_-]?\s*\d+"), ""),  # _Disc1, Disc_2, -Disc 3
)
# Sanitizer for archive filenames (avoid path-unfriendly characters)
ILLEGAL_FS_CHARS_RE = re.compile(r'[\\/:*?"<>|]')


def strip_code(text: str) -> str:
    return CODE_SUFFIX_RE.sub("", text)


def strip_disc_markers(text: str) -> str:
    for pattern, repl in DISC_MARKER_REPS:
        text = pattern.sub(repl, text)
    return text


def normalize_title(text: str) -> str:
    """Turn underscores into spaces, collapse whitespace, trim."""
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def game_key_from_stem(stem: str) -> Tuple[str, str]:
    """
    Build a grouping key and a display name from a file stem.
    Returns (key, display_name).
    """
    cleaned = normalize_title(strip_disc_markers(strip_code(stem)))
    key = cleaned.lower()
    return key, cleaned


def sanitize_filename(name: str) -> str:
    sanitized = ILLEGAL_FS_CHARS_RE.sub("_", name)
    sanitized = sanitized.rstrip(".").strip()
    return sanitized or "archive"


def find_7z(custom_path: Optional[str]) -> Optional[str]:
    if custom_path:
        return custom_path if shutil.which(custom_path) else None
    for candidate in ("7z", "7zz", "7za"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def collect_games(root: pathlib.Path) -> Dict[str, Tuple[str, Set[pathlib.Path]]]:
    games: Dict[str, Tuple[str, Set[pathlib.Path]]] = {}
    for cue in sorted(root.glob("*.cue")):
        bin_path = cue.with_suffix(".bin")
        if not bin_path.exists():
            print(f"[WARN] Missing BIN for {cue.name}; skipping this disc")
            continue

        key, display = game_key_from_stem(cue.stem)
        if not key:
            print(f"[WARN] Could not derive game key for {cue.name}; skipping")
            continue

        if key not in games:
            games[key] = (display, set())
        games[key][1].update({cue, bin_path})
    return games


def build_archive(
    sevenzip: str,
    root: pathlib.Path,
    display_name: str,
    files: Set[pathlib.Path],
    level: int,
    threads: int,
    overwrite: bool,
    dry_run: bool,
) -> None:
    archive_name = sanitize_filename(display_name) + ".7z"
    archive_path = root / archive_name
    rel_files = [str(p.relative_to(root)) for p in sorted(files)]

    if archive_path.exists():
        if not overwrite:
            print(f"[SKIP] {archive_name} already exists")
            return
        if not dry_run:
            archive_path.unlink()

    if dry_run:
        print(f"[PLAN] {archive_name} <= {', '.join(rel_files)}")
        return

    thread_flag = f"-mmt={threads}" if threads > 0 else "-mmt=on"
    cmd = [
        sevenzip,
        "a",
        "-t7z",
        f"-mx={level}",
        thread_flag,
        archive_name,
        *rel_files,
    ]
    print(f"[RUN ] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=root, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack PS1 BIN/CUE sets into one 7z per game.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory containing BIN/CUE files (default: current dir)")
    parser.add_argument("--dry-run", action="store_true", help="List planned archives without creating them")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .7z files")
    parser.add_argument("--sevenzip", help="Path to 7z/7zz/7za binary (auto-detect if omitted)")
    parser.add_argument("--level", type=int, default=9, help="7z compression level (0-9, default: 9)")
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help="Thread count for 7z -mmt. 0 = auto (2x CPU cores, default).",
    )
    args = parser.parse_args()

    root = pathlib.Path(args.directory).resolve()
    if not root.is_dir():
        print(f"[ERROR] Not a directory: {root}")
        return 1

    sevenzip = find_7z(args.sevenzip)
    if not sevenzip:
        print("[ERROR] 7z binary not found. Install 7z/7zz/7za or pass --sevenzip /path/to/bin.")
        return 1

    games = collect_games(root)
    if not games:
        print(f"[INFO] No BIN/CUE pairs found in {root}")
        return 0

    if args.threads and args.threads < 1:
        print("[ERROR] --threads must be >= 1 or 0 for auto")
        return 1

    auto_threads = max(1, (os.cpu_count() or 1) * 2)
    threads = args.threads if args.threads > 0 else auto_threads

    for key in sorted(games):
        display, files = games[key]
        if not files:
            continue
        try:
            build_archive(
                sevenzip=sevenzip,
                root=root,
                display_name=display,
                files=files,
                level=args.level,
                threads=threads,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
        except subprocess.CalledProcessError as err:
            print(f"[ERROR] Failed to build archive for {display}: {err}")
            return err.returncode

    if args.dry_run:
        print("[INFO] Dry run complete.")
    else:
        print("[INFO] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
