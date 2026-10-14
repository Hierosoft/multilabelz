"""MultiLabelZ main GUI application (ttk.Frame subclass)."""

import json
import threading
from collections import OrderedDict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont

from . import (
    app_config_dir,
    settings_path,
    find_latest_csv,
    next_available_path,
    get_system_printers,
    send_raw_zpl,
    default_canvas_items,
    build_zpl,
)


class MultiLabelZ(ttk.Frame):
    def __init__(self, parent: tk.Tk, **kwargs):
        super().__init__(parent, **kwargs)
        self.root = parent

        self.settings: OrderedDict = self._load_settings()
        self.current_csv: Path | None = None

        # Ensure defaults
        self._ensure_defaults()

        # Variables
        self.csv_filename_var = tk.StringVar(value=self.settings.get("csv_filename", "Batches.csv"))
        self.current_file_var = tk.StringVar(value="")
        self.printer_var = tk.StringVar(value=self.settings.get("printer", ""))
        self.po_var = tk.StringVar()
        self.ship_date_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

        self.company_var = tk.StringVar(value=self.settings.get("company", "Train Control Systems"))
        self.addr1_var = tk.StringVar(value=self.settings.get("address1", "845 Blooming Glen Rd"))
        self.addr2_var = tk.StringVar(value=self.settings.get("address2", "Blooming Glen, PA 18911"))
        self.phone_var = tk.StringVar(value=self.settings.get("phone", "215-453-9145"))
        self.brand_var = tk.StringVar(value=self.settings.get("brand", "TRAIN CONTROL SYSTEMS"))
        self.coo_var = tk.StringVar(value=self.settings.get("coo", "US"))

        self.label_w_var = tk.StringVar(value=str(self.settings.get("label_width", "4")))
        self.label_h_var = tk.StringVar(value=str(self.settings.get("label_height", "6")))
        self.orientation_var = tk.StringVar(value=self.settings.get("orientation", "portrait"))
        self.divisor_var = tk.StringVar(value=str(self.settings.get("grid_divisor", "8")))
        self.barcode_var = tk.BooleanVar(value=False)

        self.selected_key: str | None = None
        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.canvas_scale = 1.0  # pixels per inch
        self.item_ids: dict[str, list[int]] = {}  # key -> [rect_id, text_id, barcode_id?]

        self._build_ui()
        self._refresh_csv_display()
        self._refresh_printers()
        self._update_print_button_state()
        self._update_divisor_label()
        self._redraw_canvas()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    # ----- Settings -----
    def _load_settings(self) -> OrderedDict:
        p = settings_path()
        if p.is_file():
            try:
                with p.open(encoding="utf-8") as f:
                    return json.load(f, object_pairs_hook=OrderedDict)
            except Exception:
                pass
        return OrderedDict()

    def _ensure_defaults(self) -> None:
        defaults = OrderedDict([
            ("csv_filename", "Batches.csv"),
            ("printer", ""),
            ("company", "Train Control Systems"),
            ("address1", "845 Blooming Glen Rd"),
            ("address2", "Blooming Glen, PA 18911"),
            ("phone", "215-453-9145"),
            ("brand", "TRAIN CONTROL SYSTEMS"),
            ("coo", "US"),
            ("label_width", "4"),
            ("label_height", "6"),
            ("orientation", "portrait"),
            ("grid_divisor", "8"),
            ("canvas_items", default_canvas_items()),
        ])
        for k, v in defaults.items():
            if k not in self.settings:
                self.settings[k] = v
        if not isinstance(self.settings.get("canvas_items"), OrderedDict):
            self.settings["canvas_items"] = default_canvas_items()

    def _save_settings(self) -> None:
        # Sync current UI values
        self.settings["csv_filename"] = self.csv_filename_var.get().strip() or "Batches.csv"
        self.settings["printer"] = self.printer_var.get().strip()
        self.settings["company"] = self.company_var.get().strip()
        self.settings["address1"] = self.addr1_var.get().strip()
        self.settings["address2"] = self.addr2_var.get().strip()
        self.settings["phone"] = self.phone_var.get().strip()
        self.settings["brand"] = self.brand_var.get().strip()
        self.settings["coo"] = self.coo_var.get().strip()
        self.settings["label_width"] = self.label_w_var.get().strip() or "4"
        self.settings["label_height"] = self.label_h_var.get().strip() or "6"
        self.settings["orientation"] = self.orientation_var.get()
        self.settings["grid_divisor"] = self.divisor_var.get().strip() or "8"
        # canvas_items already mutated in place
        try:
            with settings_path().open("w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            self.setStatus(f"Could not save settings: {e}")

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()

    def _on_tab_changed(self, event=None) -> None:
        # Save when leaving Layout tab
        current = self.notebook.tab(self.notebook.select(), "text")
        if hasattr(self, "_last_tab") and self._last_tab == "Layout" and current != "Layout":
            self._save_settings()
        self._last_tab = current

    # ----- Thread-safe -----
    def setStatus(self, text: str) -> None:
        self.root.after_idle(lambda: self.status_var.set(text))

    def logLine(self, text: str) -> None:
        def _do():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after_idle(_do)

    # ----- Decimal helpers (static / generic) -----
    @staticmethod
    def getDecimal(container: dict | OrderedDict, key: str, default: str = "0") -> tuple[Decimal | None, str | None]:
        """Generic getter: returns (Decimal, None) or (None, error_str)."""
        raw = container.get(key, default)
        try:
            d = Decimal(str(raw))
            return d, None
        except (InvalidOperation, TypeError, ValueError) as e:
            return None, f"Invalid decimal for {key}: {e}"

    @staticmethod
    def setDecimal(container: dict | OrderedDict, key: str, value: Decimal) -> None:
        """Store Decimal as string for JSON compatibility."""
        container[key] = str(value)

    def getDivisor(self) -> tuple[Decimal | None, str | None]:
        d, err = self.getDecimal(self.settings, "grid_divisor", "8")
        if err:
            return None, err
        if d is not None and d <= 0:
            return None, "Divisor must be positive"
        return d, None

    def getCanvasDecimal(self, itemKey: str, valueKey: str, default: str = "0") -> tuple[Decimal | None, str | None]:
        items = self.settings.get("canvas_items", OrderedDict())
        item = items.get(itemKey)
        if not isinstance(item, dict):
            return None, f"No canvas item {itemKey}"
        return self.getDecimal(item, valueKey, default)

    def setCanvasDecimal(self, itemKey: str, valueKey: str, value: Decimal) -> None:
        items = self.settings.setdefault("canvas_items", OrderedDict())
        item = items.setdefault(itemKey, OrderedDict())
        self.setDecimal(item, valueKey, value)

    def getCanvasCoords(self, itemKey: str) -> tuple[tuple[Decimal, Decimal, Decimal, Decimal] | None, str | None]:
        """Return ((x, y, w, h), None) or (None, error). All as Decimal."""
        xs = []
        for k in ("x", "y", "w", "h"):
            d, err = self.getCanvasDecimal(itemKey, k, "0")
            if err or d is None:
                return None, err or f"Missing {k}"
            xs.append(d)
        return tuple(xs), None  # type: ignore

    def setCanvasCoords(self, itemKey: str, coords: tuple[Decimal, Decimal, Decimal, Decimal]) -> None:
        """Store (x, y, w, h) Decimals as strings."""
        for k, v in zip(("x", "y", "w", "h"), coords):
            self.setCanvasDecimal(itemKey, k, v)

    # ----- Divisor -----
    def _update_divisor_label(self) -> None:
        d, err = self.getDivisor()
        if err:
            self.setStatus(err)
            messagebox.showerror("Divisor error", err, parent=self.root)
            self.settings["grid_divisor"] = "8"
            self.divisor_var.set("8")
            d = Decimal("8")
            self._save_settings()
        decimal_val = (Decimal(1) / d).quantize(Decimal("0.0001"))
        self.divisor_decimal_label.configure(text=f'" = {decimal_val}"')

    # ----- UI -----
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # --- Layout tab (primary, with print buttons + canvas) ---
        layout_tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(layout_tab, text="Layout")
        self._last_tab = "Layout"

        # Print controls
        ctrl = ttk.Frame(layout_tab)
        ctrl.pack(fill="x", pady=(0, 4))
        ttk.Label(ctrl, text="PO # (required):").pack(side="left")
        ttk.Entry(ctrl, textvariable=self.po_var, width=18).pack(side="left", padx=4)
        ttk.Label(ctrl, text="Ship Date:").pack(side="left", padx=(8, 0))
        ttk.Entry(ctrl, textvariable=self.ship_date_var, width=14).pack(side="left", padx=4)
        ttk.Label(ctrl, text="(blank = use sheet or none)", foreground="gray").pack(side="left")

        print_row = ttk.Frame(layout_tab)
        print_row.pack(fill="x", pady=2)
        self.print_btn = ttk.Button(print_row, text="Print to", command=self._on_print, state="disabled")
        self.print_btn.pack(side="left")
        self.printer_combo = ttk.Combobox(print_row, textvariable=self.printer_var, width=36, state="readonly")
        self.printer_combo.pack(side="left", padx=6)
        self.printer_combo.bind("<<ComboboxSelected>>", lambda e: self._update_print_button_state())
        ttk.Button(print_row, text="Refresh printers", command=self._refresh_printers).pack(side="left")

        # Snap controls
        snap_row = ttk.Frame(layout_tab)
        snap_row.pack(fill="x", pady=4)
        ttk.Label(snap_row, text="Snap: ").pack(side="left")
        ttk.Button(snap_row, text="X", width=3, command=lambda: self._snap_selected("x")).pack(side="left", padx=2)
        ttk.Button(snap_row, text="Y", width=3, command=lambda: self._snap_selected("y")).pack(side="left", padx=2)
        ttk.Label(snap_row, text=" to: 1/").pack(side="left")
        div_entry = ttk.Entry(snap_row, textvariable=self.divisor_var, width=6)
        div_entry.pack(side="left")
        div_entry.bind("<FocusOut>", lambda e: self._update_divisor_label())
        div_entry.bind("<Return>", lambda e: self._update_divisor_label())
        self.divisor_decimal_label = ttk.Label(snap_row, text='" = 0.1250"')
        self.divisor_decimal_label.pack(side="left", padx=4)

        # Barcode checkbox
        self.barcode_cb = ttk.Checkbutton(
            snap_row, text="Barcode", variable=self.barcode_var,
            command=self._on_barcode_toggle, state="disabled"
        )
        self.barcode_cb.pack(side="left", padx=12)

        # Canvas
        self.canvas = tk.Canvas(layout_tab, bg="white", highlightthickness=1, highlightbackground="gray")
        self.canvas.pack(fill="both", expand=True, pady=4)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        # --- Settings tab ---
        settings_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(settings_tab, text="Settings")

        ttk.Label(settings_tab, text="CSV filename (base name in Downloads):").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(settings_tab, textvariable=self.csv_filename_var, width=40).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Button(settings_tab, text="Refresh", command=self._refresh_csv_display).grid(row=0, column=2, padx=4)

        ttk.Label(settings_tab, text="Resolved file:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(settings_tab, textvariable=self.current_file_var, state="readonly", width=50).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=2
        )

        ttk.Separator(settings_tab, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Label(settings_tab, text="Label size (inches):").grid(row=3, column=0, sticky="w")
        size_f = ttk.Frame(settings_tab)
        size_f.grid(row=3, column=1, sticky="w")
        ttk.Label(size_f, text="W:").pack(side="left")
        ttk.Entry(size_f, textvariable=self.label_w_var, width=6).pack(side="left", padx=2)
        ttk.Label(size_f, text="H:").pack(side="left", padx=(8, 0))
        ttk.Entry(size_f, textvariable=self.label_h_var, width=6).pack(side="left", padx=2)
        ttk.Button(size_f, text="Apply", command=self._redraw_canvas).pack(side="left", padx=8)

        ttk.Label(settings_tab, text="Orientation:").grid(row=4, column=0, sticky="w", pady=2)
        orient_f = ttk.Frame(settings_tab)
        orient_f.grid(row=4, column=1, sticky="w")
        ttk.Radiobutton(orient_f, text="Portrait", variable=self.orientation_var, value="portrait",
                        command=self._redraw_canvas).pack(side="left")
        ttk.Radiobutton(orient_f, text="Landscape", variable=self.orientation_var, value="landscape",
                        command=self._redraw_canvas).pack(side="left", padx=8)

        ttk.Separator(settings_tab, orient="horizontal").grid(row=5, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Label(settings_tab, text="Sender / fixed fields (saved)").grid(row=6, column=0, columnspan=3, sticky="w")
        fields = [
            ("Company:", self.company_var),
            ("Address line 1:", self.addr1_var),
            ("Address line 2:", self.addr2_var),
            ("Phone:", self.phone_var),
            ("Brand:", self.brand_var),
            ("COO:", self.coo_var),
        ]
        for i, (lab, var) in enumerate(fields, start=7):
            ttk.Label(settings_tab, text=lab).grid(row=i, column=0, sticky="w", pady=1)
            ttk.Entry(settings_tab, textvariable=var, width=40).grid(row=i, column=1, columnspan=2, sticky="ew", pady=1)

        settings_tab.columnconfigure(1, weight=1)

        # --- Log tab ---
        log_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(log_tab, text="Log")

        log_frame = ttk.Frame(log_tab)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, wrap="word", state="disabled", height=18)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        log_btns = ttk.Frame(log_tab)
        log_btns.pack(fill="x", pady=4)
        ttk.Button(log_btns, text="Copy", command=self._copy_log).pack(side="left", padx=2)
        ttk.Button(log_btns, text="Save...", command=self._save_log).pack(side="left", padx=2)

        # Status
        status = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=4)
        status.grid(row=1, column=0, sticky="ew")

    # ----- Canvas -----
    def _get_label_size(self) -> tuple[Decimal, Decimal]:
        try:
            w = Decimal(self.label_w_var.get() or "4")
            h = Decimal(self.label_h_var.get() or "6")
        except InvalidOperation:
            w, h = Decimal("4"), Decimal("6")
        if self.orientation_var.get() == "landscape":
            return h, w  # swap for display
        return w, h

    def _redraw_canvas(self) -> None:
        self.canvas.delete("all")
        self.item_ids.clear()
        self.selected_key = None
        self.barcode_cb.configure(state="disabled")
        self.barcode_var.set(False)

        # Canvas size: max half screen height
        screen_h = self.root.winfo_screenheight()
        max_h = screen_h // 2
        lw, lh = self._get_label_size()
        # Prefer height-constrained
        canvas_h = min(max_h, 700)
        self.canvas_scale = float(canvas_h / float(lh))  # px per inch
        canvas_w = int(float(lw) * self.canvas_scale)
        self.canvas.configure(width=canvas_w, height=canvas_h)

        items = self.settings.get("canvas_items", OrderedDict())
        for key, item in items.items():
            self._draw_item(key, item)

    def _draw_item(self, key: str, item: dict) -> None:
        try:
            x = float(Decimal(str(item.get("x", "0")))) * self.canvas_scale
            y = float(Decimal(str(item.get("y", "0")))) * self.canvas_scale
            w = float(Decimal(str(item.get("w", "1.5")))) * self.canvas_scale
            h = float(Decimal(str(item.get("h", "0.2")))) * self.canvas_scale
            fs_in = Decimal(str(item.get("font_size", "0.1")))
        except (InvalidOperation, TypeError):
            return

        # Font size in pixels: (fs_in / label_h) * canvas_h
        lh = self._get_label_size()[1]
        canvas_h = self.canvas.winfo_height() or int(float(lh) * self.canvas_scale)
        font_px = max(6, int(float(fs_in / lh) * canvas_h))
        weight = "bold" if item.get("bold") else "normal"
        font = tkfont.Font(family="Helvetica", size=font_px, weight=weight)

        caption = item.get("caption")
        display = key if caption is None or caption == "" else f"{caption}{key}"
        # Use key as placeholder text on canvas

        rect = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            outline="gray", width=1, tags=(key, "field")
        )
        text = self.canvas.create_text(
            x + 4, y + h / 2, anchor="w", text=display, font=font, tags=(key, "field")
        )
        ids = [rect, text]

        if item.get("barcode"):
            bh = 20  # fixed gray box height in px for preview
            bc = self.canvas.create_rectangle(
                x, y + h + 2, x + w, y + h + 2 + bh,
                fill="gray70", outline="", tags=(key, "barcode")
            )
            ids.append(bc)

        self.item_ids[key] = ids
        # Store key on items via tags already; also monkeypatch via canvas item config if needed
        for iid in ids:
            self.canvas.itemconfig(iid, tags=(key, "field" if iid != ids[-1] or not item.get("barcode") else "barcode"))

    def _on_canvas_press(self, event) -> None:
        # Find item under cursor
        items = self.canvas.find_overlapping(event.x - 2, event.y - 2, event.x + 2, event.y + 2)
        key = None
        for iid in items:
            tags = self.canvas.gettags(iid)
            for t in tags:
                if t in self.item_ids:
                    key = t
                    break
            if key:
                break
        self._select_item(key)
        if key:
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            self.drag_data["item"] = key

    def _on_canvas_drag(self, event) -> None:
        key = self.drag_data.get("item")
        if not key:
            return
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        for iid in self.item_ids.get(key, []):
            self.canvas.move(iid, dx, dy)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def _on_canvas_release(self, event) -> None:
        key = self.drag_data.get("item")
        if not key:
            return
        # Update settings with new position (from main rect) using helpers
        ids = self.item_ids.get(key, [])
        if ids:
            coords = self.canvas.coords(ids[0])  # x1,y1,x2,y2
            if len(coords) >= 4:
                x_in = Decimal(str(coords[0] / self.canvas_scale)).quantize(Decimal("0.001"))
                y_in = Decimal(str(coords[1] / self.canvas_scale)).quantize(Decimal("0.001"))
                # keep existing w/h
                old, _ = self.getCanvasCoords(key)
                w = old[2] if old else Decimal("1.5")
                h = old[3] if old else Decimal("0.2")
                self.setCanvasCoords(key, (x_in, y_in, w, h))
        self.drag_data["item"] = None

    def _select_item(self, key: str | None) -> None:
        # Reset all outlines
        for k, ids in self.item_ids.items():
            if ids:
                self.canvas.itemconfig(ids[0], outline="gray", width=1)
        self.selected_key = key
        if key and key in self.item_ids:
            ids = self.item_ids[key]
            if ids:
                self.canvas.itemconfig(ids[0], outline="black", width=2)
            item = self.settings["canvas_items"].get(key, {})
            has_bc = bool(item.get("barcode"))
            self.barcode_var.set(has_bc)
            self.barcode_cb.configure(state="normal")
        else:
            self.barcode_var.set(False)
            self.barcode_cb.configure(state="disabled")

    def _on_barcode_toggle(self) -> None:
        if not self.selected_key:
            return
        key = self.selected_key
        item = self.settings["canvas_items"][key]
        if self.barcode_var.get():
            item["barcode"] = "BC"
        else:
            item["barcode"] = None
        self._redraw_canvas()
        # re-select
        self._select_item(key)

    def _snap_selected(self, axis: str) -> None:
        if not self.selected_key:
            return
        d, err = self.getDivisor()
        if err or d is None:
            return
        step = Decimal(1) / d
        key = self.selected_key
        try:
            if axis == "x":
                val, err = self.getCanvasDecimal(key, "x", "0")
                if err or val is None:
                    return
                snapped = (val / step).quantize(Decimal("1")) * step
                self.setCanvasDecimal(key, "x", snapped.quantize(Decimal("0.001")))
            else:
                val, err = self.getCanvasDecimal(key, "y", "0")
                if err or val is None:
                    return
                snapped = (val / step).quantize(Decimal("1")) * step
                self.setCanvasDecimal(key, "y", snapped.quantize(Decimal("0.001")))
        except (InvalidOperation, TypeError):
            return
        self._redraw_canvas()
        self._select_item(key)

    # ----- CSV / printers (unchanged logic) -----
    def _refresh_csv_display(self) -> None:
        base = self.csv_filename_var.get().strip() or "Batches.csv"
        found = find_latest_csv(base)
        self.current_csv = found
        if found:
            self.current_file_var.set(str(found))
            self.setStatus(f"Using {found.name}")
        else:
            self.current_file_var.set("")
            stem = Path(base).stem
            msg = (
                f"No matching CSV found in Downloads.\n\n"
                f"Please save the {stem} table as CSV from the {stem} Google Doc "
                f"(or elsewhere) so it is in your Downloads folder."
            )
            self.setStatus("No CSV found")
            messagebox.showinfo("CSV required", msg, parent=self.root)

    def _refresh_printers(self) -> None:
        printers = get_system_printers()
        self.printer_combo["values"] = printers
        current = self.printer_var.get()
        if current and current in printers:
            self.printer_var.set(current)
        self._update_print_button_state()
        self.setStatus(f"Found {len(printers)} printer(s)")

    def _update_print_button_state(self) -> None:
        if self.printer_var.get().strip():
            self.print_btn.configure(state="normal")
        else:
            self.print_btn.configure(state="disabled")

    # ----- Print -----
    def _on_print(self) -> None:
        po = self.po_var.get().strip()
        if not po:
            self.setStatus("Enter a PO number before printing.")
            messagebox.showwarning("PO required", "Please enter a PO number.", parent=self.root)
            return
        if not self.current_csv or not self.current_csv.is_file():
            self.setStatus("No CSV selected.")
            self._refresh_csv_display()
            return
        printer = self.printer_var.get().strip()
        if not printer:
            self.setStatus("No printer selected.")
            return
        self._save_settings()
        threading.Thread(
            target=self._do_print,
            args=(po, printer, self.current_csv),
            daemon=True,
        ).start()

    def _do_print(self, po: str, printer: str, csv_path: Path) -> None:
        self.setStatus(f"Filtering and printing PO {po} ...")
        try:
            matching_rows: list[list[str]] = []
            title_row: list[str] | None = None
            with csv_path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not any(cell.strip() for cell in row):
                        continue
                    if title_row is None:
                        title_row = row
                        continue
                    rowD = OrderedDict()
                    for idx, cell in enumerate(row):
                        key = title_row[idx] if idx < len(title_row) else f"col{idx}"
                        rowD[key] = cell
                    if rowD.get("PO #", "").strip() == po:
                        matching_rows.append(row)

            if title_row is None:
                self.setStatus("CSV has no title row.")
                self.logLine("ERROR: CSV has no title row.")
                return
            if not matching_rows:
                self.setStatus(f"No rows matched PO '{po}'.")
                self.logLine(f"No rows matched PO '{po}'.")
                return

            today = date.today().strftime("%Y-%m-%d")
            stem = Path(self.csv_filename_var.get().strip() or "Batches").stem
            out_dir = Path.home() / "Documents"
            final_path = next_available_path(out_dir, f"{stem} ({today})")
            tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
            with tmp_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(title_row)
                writer.writerows(matching_rows)
            tmp_path.rename(final_path)
            self.logLine(f"Filtered CSV written: {final_path.name} ({len(matching_rows)} row(s))")

            sender = {
                "company": self.company_var.get(),
                "address1": self.addr1_var.get(),
                "address2": self.addr2_var.get(),
                "phone": self.phone_var.get(),
                "brand": self.brand_var.get(),
                "coo": self.coo_var.get(),
            }
            try:
                lw = Decimal(self.label_w_var.get() or "4")
                lh = Decimal(self.label_h_var.get() or "6")
            except InvalidOperation:
                lw, lh = Decimal("4"), Decimal("6")
            orient = self.orientation_var.get()
            canvas_items = self.settings.get("canvas_items", OrderedDict())

            success_count = 0
            for raw_row in matching_rows:
                rowD = OrderedDict()
                for idx, cell in enumerate(raw_row):
                    key = title_row[idx] if idx < len(title_row) else f"col{idx}"
                    rowD[key] = cell
                pn = rowD.get("P/N", "").strip()
                qty = rowD.get("Qty", "").strip()
                try:
                    zpl = build_zpl(rowD, self.ship_date_var.get(), sender, canvas_items, lw, lh, orient)
                    send_raw_zpl(printer, zpl)
                    self.logLine(f"P/N: {pn}  Qty: {qty}  SUCCESS")
                    success_count += 1
                except Exception as e:
                    self.logLine(f"P/N: {pn}  Qty: {qty}  FAIL ({e})")

            if success_count == len(matching_rows):
                self.setStatus(f"Printed {success_count} label(s) for PO {po}.")
            else:
                self.setStatus(f"Finished with errors: {success_count}/{len(matching_rows)} succeeded for PO {po}.")
        except Exception as e:
            self.setStatus(f"Print failed: {e}")
            self.logLine(f"ERROR: {e}")

    # ----- Log -----
    def _copy_log(self) -> None:
        text = self.log_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.setStatus("Log copied to clipboard.")

    def _save_log(self) -> None:
        today = date.today().strftime("%Y-%m-%d")
        default_name = f"MultiLabelZ-{today}.log"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save log",
            initialdir=str(Path.home() / "Documents"),
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Log files", "*.log"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = self.log_text.get("1.0", "end-1c")
            Path(path).write_text(text, encoding="utf-8")
            self.setStatus(f"Log saved to {path}")
        except Exception as e:
            self.setStatus(f"Could not save log: {e}")
            messagebox.showerror("Save failed", str(e), parent=self.root)


def main() -> None:
    root = tk.Tk()
    root.title("MultiLabelZ")
    root.geometry("900x700")
    root.minsize(700, 500)
    app = MultiLabelZ(root)
    app.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
