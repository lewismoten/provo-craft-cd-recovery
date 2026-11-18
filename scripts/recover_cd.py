#!/usr/bin/env python3
"""Recover Provo Craft CD-ROM artwork into a modern per-disc folder.

The build command expects an already extracted classic-Mac CD layout containing
TIFF/, EPS/, and optionally FONT (original Mac files)/*.suit.bin. It creates:

<output>/<disc-slug>/
  contact-sheet-01.png ...
  <font name>.ttf                (when a .suit font is present)
  PNG/
  SVG/
  manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"


def announce(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True)
class OutputLayout:
    root: Path
    png_dir: Path
    svg_dir: Path

    def contact_sheet(self, number: int) -> Path:
        return self.root / f"contact-sheet-{number:02d}.png"

    def font_path(self, font_name: str) -> Path:
        return self.root / f"{font_name}.ttf"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "untitled-cd"


def output_layout(destination: Path, disc_name: str) -> OutputLayout:
    root = destination / slugify(disc_name)
    return OutputLayout(root=root, png_dir=root / "PNG", svg_dir=root / "SVG")


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Command failed: {' '.join(command[:2])}\n{detail}")


def run_output(command: list[str]) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Command failed: {' '.join(command[:2])}\n{detail}")
    return result.stdout


def run_live(command: list[str]) -> None:
    result = subprocess.run(command)
    if result.returncode:
        raise RuntimeError(f"Command failed: {' '.join(command[:2])}")


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise RuntimeError(f"Required command not found: {name}")


def optical_device_from_drutil_status(status: str) -> Path:
    match = re.search(r"\bName:\s*/dev/(r?disk\d+)\b", status)
    if not match:
        raise RuntimeError("No optical disc device was reported by drutil")
    name = match.group(1)
    return Path("/dev") / (name if name.startswith("r") else f"r{name}")


def detect_optical_device() -> Path:
    require_tool("drutil")
    result = subprocess.run(["drutil", "status"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "drutil status failed")
    return optical_device_from_drutil_status(result.stdout)


def eject_optical_disc(device: Path) -> None:
    """Eject the physical disc after a successful recovery."""
    require_tool("diskutil")
    disk_name = device.name[1:] if device.name.startswith("r") else device.name
    disk = Path("/dev") / disk_name
    announce(f"Ejecting CD: {disk}")
    run(["diskutil", "eject", str(disk)])


def volume_name_from_hmount_output(output: str) -> str:
    match = re.search(r'Volume name is "(.+?)"', output)
    if not match:
        raise RuntimeError("Could not determine the classic-Mac HFS volume name")
    return match.group(1)


def attach_hfs_iso(iso: Path) -> tuple[Path, Path]:
    """Attach an ISO read-only and return (whole_disk, HFS_partition)."""
    require_tool("hdiutil")
    output = run_output(["hdiutil", "attach", "-readonly", "-nomount", "-plist", str(iso)])
    entities = plistlib.loads(output.encode())["system-entities"]
    whole = next((Path(entity["dev-entry"]) for entity in entities if entity.get("content-hint") == "Apple_partition_scheme"), None)
    hfs = next((Path(entity["dev-entry"]) for entity in entities if entity.get("content-hint") == "Apple_HFS"), None)
    if whole is None or hfs is None:
        raise RuntimeError("Derived ISO does not contain an Apple HFS partition")
    return whole, hfs


def safe_asset_name(name: str) -> str:
    return re.sub(r"[/:\\]", "-", name).strip() or "unnamed"


def hfs_entries(path: str) -> list[str]:
    run(["hcd", path])
    return [entry for entry in run_output(["hls", "-1", "-N"]).splitlines() if entry]


def is_missing_hfs_path_error(error: RuntimeError) -> bool:
    return "no such file or directory" in str(error).lower()


def font_folder_candidates(volume_name: str) -> list[str]:
    return [f"{volume_name}:FONT:MAC", f"{volume_name}:MAC FONT"]


def extract_classic_hfs(hfs_device: Path, destination: Path) -> str:
    """Export known Provo Craft asset folders from a read-only classic HFS image."""
    for tool in ("hmount", "humount", "hcd", "hls", "hcopy"):
        require_tool(tool)
    destination.mkdir(parents=True, exist_ok=True)
    mounted = False
    try:
        volume_name = volume_name_from_hmount_output(run_output(["hmount", str(hfs_device)]))
        mounted = True
        announce(f'Opened classic HFS volume: "{volume_name}"')
        for source_folder, target_folder, extension in (("MAC TIFF", "TIFF", ".tiff"), ("MAC EPS", "EPS", ".eps")):
            announce(f"Extracting {source_folder} into {target_folder}/")
            for category in hfs_entries(f"{volume_name}:{source_folder}"):
                source_path = f"{volume_name}:{source_folder}:{category}"
                target_dir = destination / target_folder / safe_asset_name(category)
                target_dir.mkdir(parents=True, exist_ok=True)
                items = hfs_entries(source_path)
                announce(f"  {category.strip()}: {len(items)} files")
                for item in items:
                    target = target_dir / f"{safe_asset_name(item)}{extension}"
                    run(["hcopy", "-r", item, str(target)])
        font_dir = destination / "FONT (original Mac files)"
        font_items: list[str] | None = None
        for font_folder in font_folder_candidates(volume_name):
            try:
                font_items = hfs_entries(font_folder)
                break
            except RuntimeError as error:
                if not is_missing_hfs_path_error(error):
                    raise
        if font_items is None:
            announce("No Macintosh font directory is present; skipping font extraction")
        else:
            font_dir.mkdir(parents=True, exist_ok=True)
            announce(f"Extracting {len(font_items)} classic Macintosh font files")
            for item in font_items:
                run(["hcopy", "-m", item, str(font_dir / f"{safe_asset_name(item)}.bin")])
        return volume_name
    finally:
        if mounted:
            subprocess.run(["humount"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def find_files(root: Path, suffix: str) -> list[Path]:
    return sorted(path for path in root.rglob(f"*{suffix}") if path.is_file())


def png_conversion_command(source: Path, target: Path) -> list[str]:
    """Convert black-on-white legacy TIFF art into a compact transparent PNG."""
    return [
        "magick", str(source), "-alpha", "off", "-bordercolor", "white", "-border", "1",
        "-fill", "none", "-draw", "color 0,0 floodfill", "-shave", "1x1", "-depth", "1",
        "-strip", "-compress", "Zip", str(target),
    ]


def copy_as_png(source_root: Path, layout: OutputLayout) -> list[dict[str, str]]:
    require_tool("magick")
    sources = find_files(source_root / "TIFF", ".tiff")
    announce(f"Converting {len(sources)} TIFF files to 1-bit PNG")
    records: list[dict[str, str]] = []
    for number, source in enumerate(sources, 1):
        target = (layout.png_dir / source.relative_to(source_root / "TIFF")).with_suffix(".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        # The recovered TIFF artwork is 1-bit; retain it as a compressed 1-bit PNG.
        if not target.exists():
            run(png_conversion_command(source, target))
        records.append({"source": str(source.relative_to(source_root)), "output": str(target.relative_to(layout.root))})
        if number % 25 == 0 or number == len(sources):
            announce(f"  PNG {number}/{len(sources)}")
    return records


def copy_as_svg(source_root: Path, layout: OutputLayout) -> list[dict[str, str]]:
    require_tool("pstoedit")
    sources = find_files(source_root / "EPS", ".eps")
    announce(f"Converting {len(sources)} EPS files to SVG")
    records: list[dict[str, str]] = []
    for number, source in enumerate(sources, 1):
        target = (layout.svg_dir / source.relative_to(source_root / "EPS")).with_suffix(".svg")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            run(["pstoedit", "-f", "svg:-standalone", str(source), str(target)])
        records.append({"source": str(source.relative_to(source_root)), "output": str(target.relative_to(layout.root))})
        if number % 25 == 0 or number == len(sources):
            announce(f"  SVG {number}/{len(sources)}")
    return records


def find_suitcase(source_root: Path) -> Path | None:
    candidates: list[Path] = []
    for directory in (source_root / "FONT (original Mac files)", source_root / "FONT (decoded legacy Mac files)"):
        if directory.exists():
            candidates.extend(sorted(directory.glob("*.suit.bin")))
            candidates.extend(sorted(directory.glob("*.suit")))
    return candidates[0] if candidates else None


def font_name_from_suitcase(suitcase: Path) -> str:
    name = suitcase.name
    for suffix in (".suit.bin", ".suit"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return re.sub(r"[-_]+", " ", name).strip() or "Recovered Font"


def convert_suitcase(source_root: Path, layout: OutputLayout, font_name: str | None) -> dict[str, str] | None:
    suitcase = find_suitcase(source_root)
    if suitcase is None:
        return None
    require_tool("fontforge")
    resolved_name = font_name or font_name_from_suitcase(suitcase)
    target = layout.font_path(resolved_name)
    if target.exists():
        announce(f'Skipping existing font "{target.name}"')
        return {"source": str(suitcase.relative_to(source_root)), "output": str(target.relative_to(layout.root))}
    announce(f'Converting Macintosh suitcase "{suitcase.name}" to "{target.name}"')
    postscript_name = re.sub(r"[^A-Za-z0-9]", "", resolved_name) or "RecoveredFont"
    code = (
        "import fontforge,sys; "
        "f=fontforge.open(sys.argv[1]); "
        "f.fontname=sys.argv[3]; f.familyname=sys.argv[4]; f.fullname=sys.argv[4]; "
        "f.version='Converted from the original Macintosh .suit resource'; "
        "f.generate(sys.argv[2],flags=('dummy-dsig',))"
    )
    run(["fontforge", "-lang=py", "-c", code, str(suitcase), str(target), postscript_name, resolved_name])
    return {"source": str(suitcase.relative_to(source_root)), "output": str(target.relative_to(layout.root))}


def create_contact_sheets(layout: OutputLayout, columns: int = 8, rows: int = 8) -> list[str]:
    require_tool("magick")
    sources = find_files(layout.png_dir, ".png")
    if not sources:
        return []
    if not Path(ARIAL).is_file():
        raise RuntimeError(f"Required label font is missing: {ARIAL}")
    announce(f"Creating labeled {columns}x{rows} contact sheets for {len(sources)} PNG files")
    per_sheet = columns * rows
    expected_sheets = [layout.contact_sheet(page) for page in range(1, (len(sources) + per_sheet - 1) // per_sheet + 1)]
    if all(sheet.exists() for sheet in expected_sheets):
        announce("  Skipping existing contact sheets")
        return [sheet.name for sheet in expected_sheets]
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
            if number % 25 == 0 or number == len(sources):
                announce(f"  Thumbnail {number}/{len(sources)}")
        for page, start in enumerate(range(0, len(cells), per_sheet), 1):
            group = cells[start : start + per_sheet]
            # Last page shrinks to fit rather than adding blank contact cells.
            page_rows = min(rows, (len(group) + columns - 1) // columns)
            target = layout.contact_sheet(page)
            existed = target.exists()
            if not existed:
                assembled = tempdir / f"sheet-{page}.png"
                run(["magick", "montage", *map(str, group), "-tile", f"{columns}x{page_rows}", "-geometry", "256x256+0+0", "-background", "white", str(assembled)])
                run(["magick", str(assembled), "-colorspace", "Gray", "-dither", "None", "-colors", "7", "-depth", "8", "-strip", "-compress", "Zip", str(target)])
            names.append(target.name)
            announce(f"  {'Kept existing' if existed else 'Wrote'} {target.name}")
    return names


def build(source: Path, destination: Path, disc_name: str, font_name: str | None, overwrite: bool) -> OutputLayout:
    if not source.is_dir():
        raise RuntimeError(f"Source directory does not exist: {source}")
    layout = output_layout(destination, disc_name)
    if layout.root.exists() and overwrite:
        shutil.rmtree(layout.root)
    announce(f'Building modern assets for "{disc_name}" in {layout.root} (existing files will be skipped)')
    layout.png_dir.mkdir(parents=True, exist_ok=True)
    layout.svg_dir.mkdir(parents=True, exist_ok=True)
    pngs = copy_as_png(source, layout)
    svgs = copy_as_svg(source, layout)
    font = convert_suitcase(source, layout, font_name)
    sheets = create_contact_sheets(layout)
    manifest = {
        "disc_name": disc_name,
        "source": str(source.resolve()),
        "outputs": {"png": pngs, "svg": svgs, "font": font, "contact_sheets": sheets},
    }
    (layout.root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (layout.root / "README.txt").write_text(
        "Recovered from a legacy Provo Craft CD-ROM. Generated content is intentionally separate from this scripts repository.\n",
        encoding="utf-8",
    )
    announce(f"Finished {layout.root}")
    return layout


RAW_SECTOR_BYTES = 2352
CAPTURE_BLOCK_SECTORS = 128
FINGERPRINT_SECTORS = 256


def raw_capture_command(device: Path, destination: Path) -> list[str]:
    """Read a batch of complete raw sectors per I/O without altering bytes."""
    return [
        "dd", f"if={device}", f"of={destination}",
        f"bs={RAW_SECTOR_BYTES * CAPTURE_BLOCK_SECTORS}", "status=progress",
    ]


def fingerprint_command(device: Path) -> list[str]:
    batches = (FINGERPRINT_SECTORS + CAPTURE_BLOCK_SECTORS - 1) // CAPTURE_BLOCK_SECTORS
    return [
        "dd", f"if={device}", f"bs={RAW_SECTOR_BYTES * CAPTURE_BLOCK_SECTORS}", f"count={batches}",
    ]


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_device(device: Path) -> str:
    expected_bytes = RAW_SECTOR_BYTES * FINGERPRINT_SECTORS
    result = subprocess.run(fingerprint_command(device), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode or len(result.stdout) < expected_bytes:
        raise RuntimeError(f"Unable to read optical-media fingerprint from {device}")
    return fingerprint_bytes(result.stdout[:expected_bytes])


def find_matching_archive(destination: Path, fingerprint: str) -> Path | None:
    for candidate in destination.glob("*/archive/*.cdr"):
        with candidate.open("rb") as captured:
            if fingerprint_bytes(captured.read(2352 * FINGERPRINT_SECTORS)) == fingerprint:
                return candidate
    return None


def archive(device: Path, destination: Path) -> None:
    """Preserve a Mode-1 optical disc as raw 2352-byte sectors plus derived ISO."""
    require_tool("dd")
    iso = destination.with_suffix(".iso")
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    if destination.exists():
        announce(f"Skipping existing raw archive: {destination}")
    else:
        announce(f"Capturing raw CD sectors from {device} to {destination}")
        announce("  Reading the disc now; dd progress will update while the CD spins.")
        run_live(raw_capture_command(device, destination))
    raw: bytes | None = None
    if not iso.exists() or not checksum_path.exists():
        raw = destination.read_bytes()
        if len(raw) % 2352:
            raise RuntimeError("Raw capture is not an integer number of 2352-byte sectors")
    if iso.exists():
        announce(f"Skipping existing derived ISO: {iso}")
    else:
        announce("Deriving a 2048-byte-sector ISO from the raw capture")
        with iso.open("wb") as output:
            assert raw is not None
            for offset in range(0, len(raw), 2352):
                sector = raw[offset : offset + 2352]
                if sector[:12] != b"\0" + b"\xff" * 10 + b"\0" or sector[15] != 1:
                    raise RuntimeError(f"Unexpected Mode-1 sector framing at sector {offset // 2352}")
                output.write(sector[16:2064])
    if checksum_path.exists():
        announce(f"Skipping existing checksum: {checksum_path}")
    else:
        assert raw is not None
        checksum = hashlib.sha256(raw).hexdigest()
        checksum_path.write_text(f"{checksum}  {destination.name}\n", encoding="utf-8")
    announce("Archive is ready")


def recover_current_cd(destination: Path, overwrite: bool, device: Path | None = None) -> OutputLayout:
    """Run the complete read-only capture, HFS extraction, and conversion workflow."""
    device = device or detect_optical_device()
    announce(f"Detected optical drive: {device}")
    destination.mkdir(parents=True, exist_ok=True)
    announce("Reading a small disc fingerprint to find resumable work")
    existing_archive = find_matching_archive(destination, fingerprint_device(device))
    with tempfile.TemporaryDirectory(prefix="provo-craft-recover-") as temporary:
        temp = Path(temporary)
        if existing_archive:
            announce(f"Found matching prior archive: {existing_archive}")
            raw_capture = existing_archive
            iso = existing_archive.with_suffix(".iso")
            archive(device, raw_capture)
        else:
            raw_capture = temp / "disc.cdr"
            archive(device, raw_capture)
            iso = raw_capture.with_suffix(".iso")
        announce("Attaching the derived ISO read-only")
        whole_disk, hfs_partition = attach_hfs_iso(iso)
        extracted = temp / "extracted"
        try:
            disc_name = extract_classic_hfs(hfs_partition, extracted)
        finally:
            announce("Detaching the read-only ISO")
            run(["hdiutil", "detach", str(whole_disk)])
        layout = build(extracted, destination, disc_name, None, overwrite)
        if not existing_archive:
            archive_dir = layout.root / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            base = slugify(disc_name)
            shutil.move(str(raw_capture), archive_dir / f"{base}.cdr")
            shutil.move(str(iso), archive_dir / f"{base}.iso")
            shutil.move(str(raw_capture.with_suffix(raw_capture.suffix + ".sha256")), archive_dir / f"{base}.cdr.sha256")
        announce(f"Recovery complete: {layout.root}")
        eject_optical_disc(device)
        return layout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="convert an extracted CD folder into low-depth PNG, SVG, TTF, and contact sheets")
    build_parser.add_argument("source", type=Path, help="extracted CD folder containing TIFF/, EPS/, and optional FONT folders")
    build_parser.add_argument("destination", type=Path, help="parent folder for the generated per-CD folder")
    build_parser.add_argument("--disc-name", required=True)
    build_parser.add_argument("--font-name", help="optional display name override for a converted .suit font")
    build_parser.add_argument("--overwrite", action="store_true")
    archive_parser = subparsers.add_parser("archive", help="auto-detect the current CD and make a raw Mode-1 archive plus derived ISO")
    archive_parser.add_argument("destination", type=Path, help="output .cdr path")
    archive_parser.add_argument("--device", type=Path, help="optional raw-device override, e.g. /dev/rdisk12")
    recover_parser = subparsers.add_parser("recover", help="run the complete recovery workflow for the CD currently in the drive")
    recover_parser.add_argument("destination", type=Path, nargs="?", default=Path("CD"), help="parent output directory (default: ./CD)")
    recover_parser.add_argument("--device", type=Path, help="optional raw-device override, e.g. /dev/rdisk12")
    recover_parser.add_argument("--overwrite", action="store_true", help="replace an existing folder with the same detected disc name")
    args = parser.parse_args()
    try:
        if args.command == "build":
            layout = build(args.source, args.destination, args.disc_name, args.font_name, args.overwrite)
            print(layout.root)
        elif args.command == "archive":
            archive(args.device or detect_optical_device(), args.destination)
            print(args.destination)
        else:
            print(recover_current_cd(args.destination, args.overwrite, args.device).root)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
