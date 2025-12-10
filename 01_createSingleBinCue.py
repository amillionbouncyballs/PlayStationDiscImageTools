#!/usr/bin/env python3
"""
Create single-track BIN/CUE outputs for PS1 discs using chdman (and 7z when archives exist).

Behavior:
- If .7z archives are present in the working directory, each archive is extracted to a folder
  named after the archive (unless already extracted), a CUE is located or synthesized, and
  chdman is used to emit a single BIN/CUE into ./SingleTrackDiscImages.
- If no .7z archives are present, it processes existing CUE/BIN files in the working directory
  (depth <= 2) and writes single-track outputs to ./SingleTrackDiscImages.

Requirements: chdman (mandatory), 7z (only when archives are present).

Example:
  python 01_createSingleBinCue.py /path/to/ps1 --chdman /usr/bin/chdman --sevenzip /usr/bin/7z
"""

import argparse
import pathlib
import shutil
import subprocess
import tempfile
from typing import Iterable, List, Optional


def resolve_cmd(name: str, user_path: Optional[str], required: bool = True, instructions: Optional[str] = None) -> Optional[str]:
    """Return executable path or exit with guidance."""
    if user_path:
        path = pathlib.Path(user_path)
        if path.is_file():
            return str(path)
        found = shutil.which(user_path)
        if found:
            return found
        msg = f"[ERROR] Provided path for {name} not found: {user_path}"
        if instructions:
            msg += f"\n{instructions}"
        if required:
            raise SystemExit(msg)
        print(msg)
        return None

    found = shutil.which(name)
    if found:
        return found

    msg = f"[ERROR] Required command not found: {name}"
    if instructions:
        msg += f"\n{instructions}"
    if required:
        raise SystemExit(msg)
    print(msg)
    return None


def run(cmd: List[str], cwd: Optional[pathlib.Path] = None) -> None:
    subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def find_with_depth(root: pathlib.Path, pattern: str, max_depth: int) -> List[pathlib.Path]:
    """Return sorted paths matching pattern up to a max depth relative to root."""
    paths: List[pathlib.Path] = []
    for path in root.rglob(pattern):
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if len(rel_parts) <= max_depth:
            paths.append(path)
    return sorted(paths)


def synthesize_cue(bins: List[pathlib.Path], dest_dir: pathlib.Path, base_name: str) -> pathlib.Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    cue_path = dest_dir / f"{base_name}.cue"
    lines: List[str] = []
    if len(bins) == 1:
        bin_base = bins[0].name
        shutil.copy2(bins[0], dest_dir / bin_base)
        lines.append(f'FILE "{bin_base}" BINARY\n')
        lines.append("  TRACK 01 MODE2/2352\n")
        lines.append("    INDEX 01 00:00:00\n")
    else:
        print(f"    Synthesizing CUE for {len(bins)} BINs (track1 data, rest audio; order = sorted filenames)")
        track_num = 1
        for bin_path in bins:
            bin_base = bin_path.name
            shutil.copy2(bin_path, dest_dir / bin_base)
            lines.append(f'FILE "{bin_base}" BINARY\n')
            if track_num == 1:
                lines.append(f"  TRACK {track_num:02d} MODE2/2352\n")
            else:
                lines.append(f"  TRACK {track_num:02d} AUDIO\n")
            lines.append("    INDEX 01 00:00:00\n")
            track_num += 1
    cue_path.write_text("".join(lines), encoding="utf-8")
    return cue_path


def process_disc(base: str, cue_path: pathlib.Path, out_dir: pathlib.Path, tmp_root: pathlib.Path, chdman: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_cue = out_dir / f"{base}.cue"
    out_bin = out_cue.with_suffix(".bin")
    out_cue.unlink(missing_ok=True)
    out_bin.unlink(missing_ok=True)

    chd_tmp = tmp_root / f"{base}.chd"
    print(f"    Building CHD from {cue_path.name}")
    run([chdman, "createcd", "-i", str(cue_path), "-o", str(chd_tmp)])
    print(f"    Extracting single BIN/CUE -> {out_dir}/")
    run([chdman, "extractcd", "-i", str(chd_tmp), "-o", str(out_cue)])
    chd_tmp.unlink(missing_ok=True)


def locate_or_build_cue(game_dir: pathlib.Path, base: str, tmp_root: pathlib.Path) -> Optional[pathlib.Path]:
    cues = find_with_depth(game_dir, "*.cue", max_depth=2)
    if cues:
        return cues[0]

    bins = find_with_depth(game_dir, "*.bin", max_depth=2)
    if not bins:
        print("    No CUE or BIN files found; skipping")
        return None
    tmp_assets_dir = pathlib.Path(tempfile.mkdtemp(dir=tmp_root))
    return synthesize_cue(bins, tmp_assets_dir, base)


def process_archives(root: pathlib.Path, out_dir: pathlib.Path, tmp_root: pathlib.Path, chdman: str, sevenzip: Optional[str]) -> None:
    archives = sorted(root.glob("*.7z"))
    if not archives:
        process_existing_cues(root, out_dir, tmp_root, chdman)
        return

    for archive in archives:
        base = archive.stem
        game_dir = root / base
        print(f"==> Processing {archive.name}")
        if game_dir.is_dir():
            print(f"    Using existing extracted folder: {game_dir.name}")
        else:
            if not sevenzip:
                print("    [ERROR] 7z is required to extract this archive; skipping.")
                continue
            print(f"    Extracting to {game_dir}/")
            run([sevenzip, "x", "-y", f"-o{game_dir}", str(archive)])

        cue_path = locate_or_build_cue(game_dir, base, tmp_root)
        if cue_path is None:
            continue
        process_disc(base, cue_path, out_dir, tmp_root, chdman)

    print(f"Done. Single-track BIN/CUE files are in {out_dir}/")


def process_existing_cues(root: pathlib.Path, out_dir: pathlib.Path, tmp_root: pathlib.Path, chdman: str) -> None:
    print("No .7z archives found; processing existing CUE/BIN files instead.")
    cues = [
        p
        for p in find_with_depth(root, "*.cue", max_depth=2)
        if out_dir not in p.parents and str(out_dir) not in str(p.parent)
    ]
    if not cues:
        print("No CUE files found to process.")
        return

    for cue_path in cues:
        base = cue_path.stem
        print(f"==> Processing existing CUE: {cue_path.name}")
        process_disc(base, cue_path, out_dir, tmp_root, chdman)

    print(f"Done. Single-track BIN/CUE files are in {out_dir}/")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create single-track BIN/CUE outputs (via chdman) from archives or existing BIN/CUEs."
    )
    parser.add_argument("directory", nargs="?", default=".", help="Working directory (default: current directory)")
    parser.add_argument("--chdman", help="Path to chdman (if not on PATH)")
    parser.add_argument("--sevenzip", help="Path to 7z/7zz/7za (if not on PATH)")
    args = parser.parse_args()

    root = pathlib.Path(args.directory).resolve()
    out_dir = root / "SingleTrackDiscImages"

    chdman_instructions = (
        "chdman is part of MAME tools. On Linux try packages like 'mame-tools' or 'mame'. "
        "On macOS: 'brew install mame'. On Windows: use the official MAME release and point --chdman to chdman.exe."
    )
    chdman = resolve_cmd("chdman", args.chdman, required=True, instructions=chdman_instructions)

    has_archives = any(root.glob("*.7z"))
    sevenzip = None
    if has_archives:
        sevenzip_instructions = "Install p7zip (Linux), 'brew install p7zip' (macOS), or 7-Zip (Windows) and supply --sevenzip if not on PATH."
        sevenzip = resolve_cmd("7z", args.sevenzip, required=True, instructions=sevenzip_instructions)

    with tempfile.TemporaryDirectory() as tmp_root_str:
        tmp_root = pathlib.Path(tmp_root_str)
        process_archives(root, out_dir, tmp_root, chdman, sevenzip)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
