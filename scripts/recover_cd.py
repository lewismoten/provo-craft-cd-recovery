#!/usr/bin/env python3
"""Recover Provo Craft CD-ROM artwork into a modern per-disc folder.

The build command expects an already extracted classic-Mac CD layout containing
TIFF/, EPS/, and optionally FONT (original Mac files)/*.suit.bin. It creates:

<output>/<disc-slug>/
  contact-sheet-01.png ...
  All Occasions Normal.ttf       (when a .suit font is present)
  GIF/
  SVG/
  manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"


@dataclass(frozen=True)
class OutputLayout:
    root: Path
    gif_dir: Path
    svg_dir: Path
    ttf: Path

    def contact_sheet(self, number: int) -> Path:
        return self.root / f"contact-sheet-{number:02d}.png"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "untitled-cd"


def output_layout(destination: Path, disc_name: str, font_name: str = "All Occasions Normal") -> OutputLayout:
    root = destination / slugify(disc_name)
    return OutputLayout(root=root, gif_dir=root / "GIF", svg_dir=root / "SVG", ttf=root / f"{font_name}.ttf")


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Command failed: {' '.join(command[:2])}\n{detail}")


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise RuntimeError(f"Required command not found: {name}")


def find_files(root: Path, suffix: str) -> list[Path]:
    return sorted(path for path in root.rglob(f"*{suffix}") if path.is_file())


def copy_as_gif(source_root: Path, layout: OutputLayout) -> list[dict[str, str]]:
    require_tool("magick")
    sources = find_files(source_root / "TIFF", ".tiff")
    records: list[dict[str, str]] = []
    for source in sources:
        target = (layout.gif_dir / source.relative_to(source_root / "TIFF")).with_suffix(".gif")
        target.parent.mkdir(parents=True, exist_ok=True)
        # The recovered TIFF artwork is 1-bit; keep GIF palette minimal.
        run(["magick", str(source), "-type", "Bilevel", "-colors", "2", str(target)])
        records.append({"source": str(source.relative_to(source_root)), "output": str(target.relative_to(layout.root))})
    return records


def copy_as_svg(source_root: Path, layout: OutputLayout) -> list[dict[str, str]]:
    require_tool("pstoedit")
    sources = find_files(source_root / "EPS", ".eps")
    records: list[dict[str, str]] = []
    for source in sources:
        target = (layout.svg_dir / source.relative_to(source_root / "EPS")).with_suffix(".svg")
        target.parent.mkdir(parents=True, exist_ok=True)
        run(["pstoedit", "-f", "svg:-standalone", str(source), str(target)])
        records.append({"source": str(source.relative_to(source_root)), "output": str(target.relative_to(layout.root))})
    return records


def find_suitcase(source_root: Path) -> Path | None:
    candidates: list[Path] = []
    for directory in (source_root / "FONT (original Mac files)", source_root / "FONT (decoded legacy Mac files)"):
        if directory.exists():
            candidates.extend(sorted(directory.glob("*.suit.bin")))
            candidates.extend(sorted(directory.glob("*.suit")))
    return candidates[0] if candidates else None


def convert_suitcase(source_root: Path, layout: OutputLayout, font_name: str) -> dict[str, str] | None:
    suitcase = find_suitcase(source_root)
    if suitcase is None:
        return None
    require_tool("fontforge")
    postscript_name = re.sub(r"[^A-Za-z0-9]", "", font_name) or "RecoveredFont"
    code = (
        "import fontforge,sys; "
        "f=fontforge.open(sys.argv[1]); "
        "f.fontname=sys.argv[3]; f.familyname=sys.argv[4]; f.fullname=sys.argv[4]; "
        "f.version='Converted from the original Macintosh .suit resource'; "
        "f.generate(sys.argv[2],flags=('dummy-dsig',))"
    )
    run(["fontforge", "-lang=py", "-c", code, str(suitcase), str(layout.ttf), postscript_name, font_name])
    return {"source": str(suitcase.relative_to(source_root)), "output": str(layout.ttf.relative_to(layout.root))}


def create_contact_sheets(layout: OutputLayout, columns: int = 8, rows: int = 8) -> list[str]:
    require_tool("magick")
    sources = find_files(layout.gif_dir, ".gif")
    if not sources:
        return []
    if not Path(ARIAL).is_file():
        raise RuntimeError(f"Required label font is missing: {ARIAL}")
    per_sheet = columns * rows
    names: list[str] = []
    with tempfile.TemporaryDirectory(prefix="provo-craft-cells-") as temp:
        tempdir = Path(temp)
        cells: list[Path] = []
        for number, source in enumerate(sources, 1):
            cell = tempdir / f"{number:04d}.png"
            label = f"caption:{source.parent.name}\n{source.stem}"
            run([
                "magick", "(", str(source), "-alpha", "remove", "-background", "white", "-resize", "254x190", "-gravity", "center", "-extent", "254x190", ")",
                "(", "-size", "254x58", "-background", "white", "-fill", "#111111", "-font", ARIAL, "-pointsize", "15", "-gravity", "center", label, ")",
                "-append", "-background", "white", "-gravity", "center", "-extent", "254x254", "-bordercolor", "#c8c8c8", "-border", "1", str(cell),
            ])
            cells.append(cell)
        for page, start in enumerate(range(0, len(cells), per_sheet), 1):
            group = cells[start : start + per_sheet]
            # Last page shrinks to fit rather than adding blank contact cells.
            page_rows = min(rows, (len(group) + columns - 1) // columns)
            target = layout.contact_sheet(page)
            run(["magick", "montage", *map(str, group), "-tile", f"{columns}x{page_rows}", "-geometry", "256x256+0+0", "-background", "white", str(target)])
            names.append(target.name)
    return names


def build(source: Path, destination: Path, disc_name: str, font_name: str, overwrite: bool) -> OutputLayout:
    if not source.is_dir():
        raise RuntimeError(f"Source directory does not exist: {source}")
    layout = output_layout(destination, disc_name, font_name)
    if layout.root.exists() and not overwrite:
        raise RuntimeError(f"Output already exists: {layout.root} (use --overwrite to replace it)")
    if layout.root.exists():
        shutil.rmtree(layout.root)
    layout.gif_dir.mkdir(parents=True)
    layout.svg_dir.mkdir(parents=True)
    gifs = copy_as_gif(source, layout)
    svgs = copy_as_svg(source, layout)
    font = convert_suitcase(source, layout, font_name)
    sheets = create_contact_sheets(layout)
    manifest = {
        "disc_name": disc_name,
        "source": str(source.resolve()),
        "outputs": {"gif": gifs, "svg": svgs, "font": font, "contact_sheets": sheets},
    }
    (layout.root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (layout.root / "README.txt").write_text(
        "Recovered from a legacy Provo Craft CD-ROM. Generated content is intentionally separate from this scripts repository.\n",
        encoding="utf-8",
    )
    return layout


def archive(device: Path, destination: Path) -> None:
    """Preserve a Mode-1 optical disc as raw 2352-byte sectors plus derived ISO."""
    require_tool("dd")
    if destination.exists():
        raise RuntimeError(f"Refusing to overwrite: {destination}")
    run(["dd", f"if={device}", f"of={destination}", "bs=2352"])
    raw = destination.read_bytes()
    if len(raw) % 2352:
        raise RuntimeError("Raw capture is not an integer number of 2352-byte sectors")
    iso = destination.with_suffix(".iso")
    with iso.open("wb") as output:
        for offset in range(0, len(raw), 2352):
            sector = raw[offset : offset + 2352]
            if sector[:12] != b"\0" + b"\xff" * 10 + b"\0" or sector[15] != 1:
                raise RuntimeError(f"Unexpected Mode-1 sector framing at sector {offset // 2352}")
            output.write(sector[16:2064])
    checksum = hashlib.sha256(raw).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(f"{checksum}  {destination.name}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="convert an extracted CD folder into GIF, SVG, TTF, and contact sheets")
    build_parser.add_argument("source", type=Path, help="extracted CD folder containing TIFF/, EPS/, and optional FONT folders")
    build_parser.add_argument("destination", type=Path, help="parent folder for the generated per-CD folder")
    build_parser.add_argument("--disc-name", required=True)
    build_parser.add_argument("--font-name", default="All Occasions Normal")
    build_parser.add_argument("--overwrite", action="store_true")
    archive_parser = subparsers.add_parser("archive", help="make a raw Mode-1 CD archive and derived ISO")
    archive_parser.add_argument("device", type=Path, help="raw device, e.g. /dev/rdisk12")
    archive_parser.add_argument("destination", type=Path, help="output .cdr path")
    args = parser.parse_args()
    try:
        if args.command == "build":
            layout = build(args.source, args.destination, args.disc_name, args.font_name, args.overwrite)
            print(layout.root)
        else:
            archive(args.device, args.destination)
            print(args.destination)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
