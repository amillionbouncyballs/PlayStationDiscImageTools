#!/usr/bin/env python3
"""
Add PS2 product codes (SLUS/SLES/SCUS/SCES/SLPM/SLPS/etc.) to ISO filenames.

The script scans each .iso for a disc ID string (or uses the code already in
the filename), renames the ISO to append or normalize `[CODE]` (e.g.,
`[SLUS-20312]`), and normalizes existing codes like `SLES_509.50` ->
`SLES-50950`.

Usage:
  python 04_tagPs2IsosWithIDs.py [directory] [--dry-run]
"""

import argparse
import pathlib
import re
from typing import Optional

ID_BYTES_RE = re.compile(rb"([A-Z]{4,5}[-_][0-9]{3,5}(?:\.[0-9]{2})?)")
NAME_CODE_RE = re.compile(r"([A-Z]{4,5}[-_][0-9]{3,5}(?:\.[0-9]{2})?)", re.IGNORECASE)
MAX_SCAN = 64 * 1024 * 1024  # scan first 64MB
READ_CHUNK = 4 * 1024 * 1024


def normalize_code(raw: str) -> str:
    """Normalize code text like 'SLUS_203.12' -> 'SLUS-20312'."""
    text = raw.replace("_", "-").replace(".", "")
    return text.upper()


def find_disc_code(iso_path: pathlib.Path) -> Optional[str]:
    """Scan the ISO for a disc code string."""
    scanned = 0
    with iso_path.open("rb") as handle:
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


def extract_code_from_name(path: pathlib.Path) -> Optional[str]:
    match = NAME_CODE_RE.search(path.stem)
    return match.group(1) if match else None


def build_new_stem(stem: str, code: str, has_code: bool) -> str:
    if has_code:
        return NAME_CODE_RE.sub(code, stem, count=1)
    return f"{stem.rstrip()} [{code}]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Append PS2 disc IDs to ISO filenames.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory containing PS2 ISOs (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="Preview renames without touching files")
    args = parser.parse_args()

    root = pathlib.Path(args.directory).resolve()
    if not root.is_dir():
        print(f"[ERROR] Not a directory: {root}")
        return 1

    iso_files = sorted(p for p in root.iterdir() if p.suffix.lower() == ".iso")
    if not iso_files:
        print(f"[INFO] No ISO files found in {root}")
        return 0

    work_items = []
    for iso in iso_files:
        code_in_name = extract_code_from_name(iso)
        code_from_iso = find_disc_code(iso) if not code_in_name else None
        code = normalize_code(code_in_name) if code_in_name else code_from_iso
        if not code:
            print(f"[WARN] No disc code found in {iso.name}; skipping")
            continue

        new_stem = build_new_stem(iso.stem, code, bool(code_in_name))
        new_path = iso.with_name(new_stem + iso.suffix)

        if new_path.exists() and new_path != iso:
            print(f"[WARN] Target already exists ({new_path.name}); skipping {iso.name}")
            continue

        work_items.append((iso, new_path, code))
        print(f"[PLAN] {iso.name} -> {new_path.name}")

    if not work_items:
        print("[INFO] Nothing to do.")
        return 0

    if args.dry_run:
        print(f"[INFO] Dry run complete; {len(work_items)} planned rename(s).")
        return 0

    for old, new, code in work_items:
        old.rename(new)
        print(f"[DONE] {old.name} -> {new.name} [{code}]")

    print(f"[INFO] Renamed {len(work_items)} ISO(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
