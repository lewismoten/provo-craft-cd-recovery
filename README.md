# Provo Craft CD Recovery

Scripts for preserving and modernizing the 1996 Provo Craft electronic clip-art CD-ROM collection.

This repository contains **scripts only**. It does not include disc images, clip art, fonts, or other recovered assets. Make sure you have the rights needed to use or distribute anything extracted from the CDs.

## What it does

`scripts/recover_cd.py` supports two steps:

1. `archive` preserves a Mode-1 CD as a raw 2352-byte-sector `.cdr` capture, generates a derived 2048-byte `.iso`, and writes a SHA-256 checksum.
2. `build` takes a previously extracted classic-Mac CD folder and creates a clean folder for one disc containing:

   ```text
   <output>/<disc-name>/
   ├── contact-sheet-01.png
   ├── contact-sheet-02.png
   ├── ...
   ├── All Occasions Normal.ttf   # when a Macintosh .suit is present
   ├── GIF/
   ├── SVG/
   ├── manifest.json
   └── README.txt
   ```

The root contact sheets use labeled 8×8 thumbnail grids. Labels show the source category folder and filename without the extension.

## Requirements

The scripts target macOS and require:

- Python 3.11+
- ImageMagick (`magick`)
- pstoedit (`pstoedit`)
- FontForge (`fontforge`)

For a classic Macintosh HFS disc, extract the source folders first with an HFS-aware tool such as `hfsutils`. Preserve legacy fonts in MacBinary form so both forks survive.

## Build a modern asset folder

The input folder must contain `TIFF/`, `EPS/`, and, when available, `FONT (original Mac files)/` with a `*.suit.bin` MacBinary font resource.

```bash
python3 scripts/recover_cd.py build \
  "/path/to/extracted-disc" \
  "/path/to/recovered-discs" \
  --disc-name "All Occasions"
```

Use `--overwrite` only when you intend to replace an existing generated per-disc folder.

## Preserve a raw optical-disc image

```bash
python3 scripts/recover_cd.py archive \
  /dev/rdisk12 \
  "/path/to/archive/all-occasions.cdr"
```

The archive step expects raw Mode-1 CD sectors. It never writes to the optical disc.

## Development

```bash
python3 -m unittest discover -s tests -v
```

## Status

The initial workflow has been tested against the recovered **All Occasions** disc layout: 202 TIFF-to-GIF conversions, 202 EPS-to-SVG conversions, direct Macintosh `.suit` to TTF conversion, and four packed contact sheets.
