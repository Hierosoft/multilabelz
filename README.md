# MultiLabelZ

Print multiple labels on Zebra: adjust layout, and query a set of lines from a CSV file by a specific PO #!

Zebra 4×6 (and configurable) label printer from CSV batches with a visual layout editor.

Prints raw ZPL to Zebra or ZPL-compatible printers. Designed for fixed CSV location in Downloads (with numbered variants), PO# filtering, and a draggable canvas layout editor.

## Features

- Visual layout editor (drag fields, snap to grid, barcodes, fonts)
- CSV discovery from `~/Downloads` (highest numbered variant)
- PO# filter with dated output CSV in Documents
- Cross-platform (Linux CUPS / Windows win32print)
- Settings persisted as OrderedDict JSON
- GPL-3.0

## Install / Run

```bash
# From the repo root (development runner that adjusts sys.path)
./scripts/multilabelz

# Or as a module
python -m multilabelz
```

Or install in editable mode (optional):

```bash
pip install -e .
multilabelz
```

On Windows, for raw printing:

```bash
pip install -r dependencies.windows.txt
```

## License

GPL-3.0-or-later. See LICENSE.
