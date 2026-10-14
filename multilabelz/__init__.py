#!/usr/bin/env python3
"""
MultiLabelZ - Zebra label printer from CSV batches with visual layout editor.
Subclass of ttk.Frame (not Tk). Cross-platform (Windows/Linux).
"""

import csv
import json
import os
import re
import subprocess
import threading
from collections import OrderedDict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def app_config_dir() -> Path:
    if "LOCALAPPDATA" in os.environ:
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path.home() / ".config"
    d = base / "multilabelz"
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_path() -> Path:
    return app_config_dir() / "settings.json"


def find_latest_csv(base_filename: str) -> Path | None:
    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        return None
    stem = Path(base_filename).stem
    suffix = Path(base_filename).suffix or ".csv"
    pattern = re.compile(
        rf"^{re.escape(stem)}(?: \((\d+)\))?{re.escape(suffix)}$",
        re.IGNORECASE,
    )
    candidates: list[tuple[int, Path]] = []
    for p in downloads.iterdir():
        if not p.is_file():
            continue
        m = pattern.match(p.name)
        if m:
            num = int(m.group(1)) if m.group(1) else 0
            candidates.append((num, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1].stat().st_mtime), reverse=True)
    return candidates[0][1]


def next_available_path(directory: Path, stem: str, suffix: str = ".csv") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    n = 1
    while True:
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def get_system_printers() -> list[str]:
    if os.name == "nt":
        try:
            import win32print  # type: ignore
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers = win32print.EnumPrinters(flags)
            return sorted({p[2] for p in printers if p[2]})
        except Exception:
            return []
    else:
        try:
            out = subprocess.check_output(
                ["lpstat", "-p"], text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            names = []
            for line in out.splitlines():
                parts = line.split()
                if parts and parts[0] == "printer" and len(parts) > 1:
                    names.append(parts[1])
            return sorted(set(names))
        except Exception:
            return []


def send_raw_zpl(printer_name: str, zpl: str) -> None:
    data = zpl.encode("utf-8")
    if os.name == "nt":
        import win32print  # type: ignore
        h = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(h, 1, ("MultiLabelZ", None, "RAW"))
            try:
                win32print.StartPagePrinter(h)
                win32print.WritePrinter(h, data)
                win32print.EndPagePrinter(h)
            finally:
                win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
    else:
        proc = subprocess.Popen(
            ["lp", "-d", printer_name, "-o", "raw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate(input=data, timeout=30)
        if proc.returncode != 0:
            err = (stderr or stdout or b"").decode(errors="replace").strip()
            raise RuntimeError(err or f"lp exited with code {proc.returncode}")


def default_canvas_items() -> OrderedDict:
    """Default field layout matching previous 4x6 @ 203 dpi positions (inches)."""
    # Positions converted from previous ^FO dots / 203
    items = OrderedDict([
        ("company", {
            "x": "0.148", "y": "0.148", "w": "2.5", "h": "0.25",
            "caption": None, "font_size": "0.177", "font": "0", "bold": False,
            "barcode": None,
        }),
        ("address1", {
            "x": "0.148", "y": "0.369", "w": "2.5", "h": "0.15",
            "caption": None, "font_size": "0.108", "font": "0", "bold": False,
            "barcode": None,
        }),
        ("address2", {
            "x": "0.148", "y": "0.517", "w": "2.5", "h": "0.15",
            "caption": None, "font_size": "0.108", "font": "0", "bold": False,
            "barcode": None,
        }),
        ("phone", {
            "x": "0.148", "y": "0.665", "w": "2.0", "h": "0.15",
            "caption": "Tel: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": None,
        }),
        ("shipdate", {
            "x": "2.069", "y": "0.148", "w": "1.5", "h": "0.15",
            "caption": "Ship Date: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": None,
        }),
        ("brand", {
            "x": "0.148", "y": "0.862", "w": "3.0", "h": "0.2",
            "caption": "Brand: ", "font_size": "0.128", "font": "0", "bold": False,
            "barcode": "BC",
        }),
        ("pn", {
            "x": "0.148", "y": "1.379", "w": "3.5", "h": "0.18",
            "caption": "P/N: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": "BC",
        }),
        ("po", {
            "x": "0.148", "y": "1.970", "w": "3.5", "h": "0.18",
            "caption": "PO #: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": "BC",
        }),
        ("batch", {
            "x": "0.148", "y": "2.562", "w": "3.5", "h": "0.18",
            "caption": "Batch #: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": "BC",
        }),
        ("qty", {
            "x": "0.148", "y": "3.153", "w": "2.0", "h": "0.18",
            "caption": "Qty: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": "BC",
        }),
        ("datecode", {
            "x": "0.148", "y": "3.744", "w": "2.0", "h": "0.18",
            "caption": "Date Code: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": "BC",
        }),
        ("coo", {
            "x": "0.148", "y": "4.236", "w": "1.5", "h": "0.18",
            "caption": "COO: ", "font_size": "0.108", "font": "0", "bold": False,
            "barcode": "BC",
        }),
        ("notice", {
            "x": "0.148", "y": "4.680", "w": "3.5", "h": "0.4",
            "caption": None, "font_size": "0.098", "font": "0", "bold": False,
            "barcode": None,
        }),
    ])
    return items


def build_zpl(row: dict, ship_date_gui: str, sender: dict, canvas_items: OrderedDict,
              label_w: Decimal, label_h: Decimal, orientation: str, dpi: int = 203) -> str:
    """Generate ZPL from configurable canvas_items (inches)."""
    # Effective size
    if orientation == "landscape":
        pw_in, ll_in = label_h, label_w
    else:
        pw_in, ll_in = label_w, label_h
    pw = int(pw_in * dpi)
    ll = int(ll_in * dpi)

    # Data mapping
    data_map = {
        "company": sender.get("company", ""),
        "address1": sender.get("address1", ""),
        "address2": sender.get("address2", ""),
        "phone": sender.get("phone", ""),
        "shipdate": ship_date_gui.strip() or row.get("Ship Date", "").strip() or "",
        "brand": sender.get("brand", "TRAIN CONTROL SYSTEMS"),
        "pn": row.get("P/N", "").strip(),
        "po": row.get("PO #", "").strip(),
        "batch": row.get("Batch #", "").strip(),
        "qty": row.get("Qty", "").strip(),
        "datecode": row.get("Date Code", "").strip(),
        "coo": sender.get("coo", "US"),
        "notice": row.get("Notice", "").strip(),
    }

    lines = ["^XA", f"^PW{pw}", f"^LL{ll}", "^CI28"]

    for key, item in canvas_items.items():
        val = data_map.get(key, "")
        caption = item.get("caption")
        if caption is None or caption == "":
            text = val
        else:
            text = f"{caption}{val}"
        if not text and key == "notice":
            continue  # skip empty notice

        try:
            x_in = Decimal(str(item.get("x", "0")))
            y_in = Decimal(str(item.get("y", "0")))
            fs_in = Decimal(str(item.get("font_size", "0.1")))
        except (InvalidOperation, TypeError):
            continue
        x = int(x_in * dpi)
        y = int(y_in * dpi)
        fs = max(10, int(fs_in * dpi))  # dots

        font = str(item.get("font", "0"))
        bold = bool(item.get("bold", False))
        # ZPL font: ^A{font}N,{h},{w}  (bold not direct; some fonts thicker)
        lines.append(f"^FO{x},{y}^A{font}N,{fs},{fs}^FD{text}^FS")

        barcode = item.get("barcode")
        if barcode and val:
            # Simple Code128 below text
            by = y + fs + 5
            bh = int(Decimal("0.35") * dpi)  # ~0.35"
            lines.append(f"^FO{x},{by}^BY2,2,{bh}^BCN,{bh},Y,N,N^FD{val}^FS")

    lines.append("^XZ")
    return "\n".join(lines)
