#!/usr/bin/env python3
"""
Add PS1 disc IDs (SLES/SLUS/SCUS/SCES/etc.) to BIN/CUE filenames and cue contents.

Usage:
  python tag_ps1_ids.py [directory] [--dry-run]

The script scans each BIN for the disc ID (or uses the code already in the filename),
renames the BIN/CUE to append or normalize `[CODE]`, and rewrites FILE lines in
the cue to point at the new BIN name. Filenames with an existing code are
normalized (e.g., `SLES_01816` -> `SLES-01816`).
"""

import argparse
import pathlib
import re
from typing import Optional

# Matches common PS1 disc ID strings inside the binary (underscore or hyphen, optional dot)
ID_BYTES_RE = re.compile(rb"(S[LC][A-Z]{2}[A-Z]?[-_][0-9]{3,5}(?:\.[0-9]{2})?)")
# Extract a code from a filename (allows underscore/hyphen and optional dot)
NAME_CODE_RE = re.compile(r"(S[LC][A-Z]{2}[A-Z]?[-_][0-9]{3,5}(?:\.[0-9]{2})?)", re.IGNORECASE)
# Stop scanning after this many bytes if no code is found (most discs expose it early)
MAX_SCAN = 64 * 1024 * 1024
READ_CHUNK = 4 * 1024 * 1024


def normalize_code(raw: str) -> str:
    """Normalize ID text like 'SLUS_005.94' -> 'SLUS-00594'."""
    text = raw.replace("_", "-").replace(".", "").upper()
    return text


def find_disc_code(bin_path: pathlib.Path) -> Optional[str]:
    """Scan the BIN for a disc code string."""
    scanned = 0
    with bin_path.open("rb") as handle:
        while True:
            chunk = handle.read(READ_CHUNK)
            if not chunk:
                break
            scanned += len(chunk)
            match = ID_BYTES_RE.search(chunk)
            if match:
                return normalize_code(match.group().decode("ascii", errors="ignore"))
            if scanned >= MAX_SCAN:
                break
    return None


def cue_for_bin(bin_path: pathlib.Path) -> Optional[pathlib.Path]:
    cue_path = bin_path.with_suffix(".cue")
    return cue_path if cue_path.exists() else None


FILE_LINE_RE = re.compile(r"(?i)^FILE\s+\"?([^\"]+?)\"?\s*(.*)$")


def update_cue_file(cue_path: pathlib.Path, new_bin_name: str) -> bool:
    """Rewrite FILE lines to point at the renamed BIN."""
    raw_lines = cue_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    changed = False
    for idx, line in enumerate(raw_lines):
        # Preserve original line endings
        line_end = ""
        if line.endswith("\r\n"):
            line_end = "\r\n"
            core = line[:-2]
        elif line.endswith("\n"):
            line_end = "\n"
            core = line[:-1]
        else:
            core = line

        match = FILE_LINE_RE.match(core)
        if not match:
            continue

        rest = match.group(2).strip()
        new_line = f'FILE "{new_bin_name}"'
        if rest:
            new_line += f" {rest}"
        raw_lines[idx] = new_line + line_end
        changed = True

    if changed:
        cue_path.write_text("".join(raw_lines), encoding="utf-8")
    return changed


def extract_code_from_name(path: pathlib.Path) -> Optional[str]:
    m = NAME_CODE_RE.search(path.stem)
    return m.group(1) if m else None


def build_new_base(stem: str, code: str) -> str:
    return f"{stem.rstrip()} [{code}]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Append PS1 disc IDs to BIN/CUE filenames.")
    parser.add_argument(
        "directory", nargs="?", default=".", help="Directory containing BIN/CUE pairs (default: current directory)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview renames without touching files")
    args = parser.parse_args()

    root = pathlib.Path(args.directory).resolve()
    if not root.is_dir():
        print(f"[ERROR] Not a directory: {root}")
        return 1

    bin_files = sorted(p for p in root.iterdir() if p.suffix.lower() == ".bin")
    if not bin_files:
        print(f"[INFO] No BIN files found in {root}")
        return 0

    work_items = []
    for bin_path in bin_files:
        code_in_name = extract_code_from_name(bin_path)
        code_from_bin = find_disc_code(bin_path) if not code_in_name else None
        code = normalize_code(code_in_name) if code_in_name else code_from_bin
        if not code:
            print(f"[WARN] No disc code found in {bin_path.name}; skipping")
            continue

        cue_path = cue_for_bin(bin_path)

        if code_in_name:
            # Replace the first occurrence of the raw code with the normalized one
            new_stem = NAME_CODE_RE.sub(code, bin_path.stem, count=1)
        else:
            new_stem = build_new_base(bin_path.stem, code)

        new_base = new_stem
        new_bin = bin_path.with_name(new_base + bin_path.suffix)
        new_cue = cue_path.with_name(new_base + ".cue") if cue_path else None

        if new_bin.exists() and new_bin != bin_path:
            print(f"[WARN] Target BIN already exists ({new_bin.name}); skipping {bin_path.name}")
            continue
        if new_cue and new_cue.exists() and new_cue != cue_path:
            print(f"[WARN] Target CUE already exists ({new_cue.name}); skipping {bin_path.name}")
            continue

        work_items.append((bin_path, cue_path, new_bin, new_cue, code))
        label = f"{bin_path.name} -> {new_bin.name}"
        print(f"[PLAN] {label}")

    if not work_items:
        print("[INFO] Nothing to do.")
        return 0

    if args.dry_run:
        print(f"[INFO] Dry run complete; {len(work_items)} planned rename(s).")
        return 0

    for bin_path, cue_path, new_bin, new_cue, code in work_items:
        if cue_path:
            updated = update_cue_file(cue_path, new_bin.name)
            if not updated:
                print(f"[WARN] No FILE line updated in {cue_path.name}; check manually")
        bin_path.rename(new_bin)
        if cue_path and new_cue:
            cue_path.rename(new_cue)
        print(f"[DONE] {bin_path.name} -> {new_bin.name} [{code}]")

    print(f"[INFO] Renamed {len(work_items)} BIN/CUE pair(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
