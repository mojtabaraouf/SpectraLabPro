#!/usr/bin/env python3
"""
SpectraLab Organic/Biosignature Suite
UV–VIS–NIR–SWIR reflectance and tracer GUI

SpectTek Co.
Password: Ask  SpectTek@gmail.com
"""

import os
import time
import queue
import logging
import threading
import platform
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

try:
    import seabreeze.spectrometers as sb
except ImportError:
    try:
        import seabreeze
        seabreeze.use("pyseabreeze")
        import seabreeze.spectrometers as sb
    except Exception:
        sb = None


DATA_DIR = "spectra_data"
os.makedirs(DATA_DIR, exist_ok=True)

SPECTTEK_LINK = "https://www.linkedin.com/in/specttek/"


@dataclass(frozen=True)
class TracerFeature:
    species: str
    tracer: str
    kind: str
    center_nm: float
    window_nm: float
    continuum_left: Tuple[float, float]
    continuum_right: Tuple[float, float]
    description: str
    color: str


TRACERS: List[TracerFeature] = [
    TracerFeature("Organic", "Deep-UV absorption edge", "absorption", 210.0, 14.0, (196, 202), (225, 235),
                  "Aromatic/conjugated organic or charge-transfer UV edge.", "tab:purple"),
    TracerFeature("Organic", "Aromatic / PAH band", "absorption", 255.0, 18.0, (225, 235), (285, 300),
                  "Aromatic carbon, PAH-like, kerogen-like, humic-like material.", "tab:purple"),
    TracerFeature("Organic", "Amino-acid / nucleobase UV", "absorption", 280.0, 12.0, (250, 260), (300, 315),
                  "UV screening region for prebiotic/biomolecule analogues.", "tab:purple"),
    TracerFeature("Organic", "Organic UV shoulder", "absorption", 330.0, 28.0, (285, 300), (370, 390),
                  "Broad organic/mineral UV absorption shoulder.", "tab:purple"),
    TracerFeature("Organic", "C-H overtone 1150 nm", "absorption", 1150.0, 35.0, (1080, 1110), (1210, 1240),
                  "Weak SWIR organic C-H overtone.", "tab:purple"),
    TracerFeature("Organic", "C-H overtone 1720 nm", "absorption", 1720.0, 35.0, (1650, 1680), (1770, 1800),
                  "Aliphatic organic C-H overtone/combination.", "tab:purple"),
    TracerFeature("Organic", "C-H combination 2300 nm", "absorption", 2300.0, 45.0, (2220, 2250), (2380, 2410),
                  "Organic C-H combination region; overlaps carbonate and Mg-OH.", "tab:purple"),

    TracerFeature("Bio-analogue", "Chlorophyll Soret band", "absorption", 430.0, 18.0, (390, 405), (460, 475),
                  "Chlorophyll-like blue absorption control.", "tab:green"),
    TracerFeature("Bio-analogue", "Carotenoid band", "absorption", 450.0, 25.0, (395, 415), (495, 520),
                  "Carotenoid-like pigment absorption control.", "tab:orange"),
    TracerFeature("Bio-analogue", "Chlorophyll red band", "absorption", 665.0, 16.0, (620, 635), (690, 705),
                  "Chlorophyll-a red absorption analogue.", "tab:green"),
    TracerFeature("Bio-analogue", "Red edge", "edge", 725.0, 35.0, (670, 690), (760, 800),
                  "Vegetation or microbial-mat red-edge analogue.", "tab:green"),

    TracerFeature("Lunar/Mineral", "Ti/Fe UV-blue transfer", "absorption", 410.0, 35.0, (350, 370), (455, 480),
                  "Basaltic, ilmenite-rich, or Fe/Ti charge-transfer region.", "tab:gray"),
    TracerFeature("Lunar/Mineral", "Ferric visible band", "absorption", 535.0, 35.0, (470, 495), (590, 620),
                  "Ferric oxide / alteration analogue feature.", "tab:brown"),
    TracerFeature("Lunar/Mineral", "npFe0 red slope", "slope", 720.0, 90.0, (500, 560), (820, 880),
                  "Space-weathering, nanophase iron, grain-size, and glass continuum slope.", "tab:gray"),
    TracerFeature("Lunar/Mineral", "Fe2+ 1 µm shoulder", "absorption", 890.0, 45.0, (740, 780), (930, 970),
                  "Beginning of olivine/pyroxene Fe2+ band.", "tab:olive"),
    TracerFeature("Lunar/Mineral", "Olivine / pyroxene 1 µm", "absorption", 1050.0, 95.0, (850, 900), (1240, 1300),
                  "Mafic lunar basalt, olivine, and pyroxene band.", "tab:olive"),
    TracerFeature("Lunar/Mineral", "1.25 µm shoulder", "absorption", 1250.0, 55.0, (1120, 1160), (1330, 1380),
                  "Plagioclase/mafic context shoulder.", "tab:olive"),
    TracerFeature("Lunar/Mineral", "Pyroxene 2 µm band", "absorption", 2000.0, 120.0, (1700, 1760), (2200, 2260),
                  "Diagnostic pyroxene band for lunar basalt analogues.", "tab:olive"),

    TracerFeature("H2O/OH", "OH A-X 308 nm", "emission", 308.5, 2.5, (300, 305), (312, 317),
                  "Indirect H2O/OH tracer.", "tab:blue"),
    TracerFeature("H2O/OH", "OH+ 335 nm", "emission", 335.0, 3.0, (326, 331), (339, 344),
                  "Ionized water-chemistry near-UV tracer.", "tab:cyan"),
    TracerFeature("H2O/OH", "H2O near-UV", "absorption", 363.0, 8.0, (345, 355), (372, 382),
                  "Weak near-UV H2O/OH screening region.", "tab:blue"),
    TracerFeature("H2O/OH", "H2O 940 nm", "absorption", 940.0, 18.0, (900, 915), (970, 985),
                  "Water overtone near 940 nm.", "tab:blue"),
    TracerFeature("H2O/OH", "H2O/OH 970 nm", "absorption", 970.0, 18.0, (930, 945), (1000, 1015),
                  "Water/OH overtone near 970 nm.", "tab:blue"),
    TracerFeature("H2O/OH", "H2O 1130 nm", "absorption", 1130.0, 30.0, (1065, 1090), (1180, 1210),
                  "Water absorption near 1130 nm.", "tab:cyan"),
    TracerFeature("H2O/OH", "H2O 1370 nm", "absorption", 1370.0, 45.0, (1280, 1310), (1450, 1480),
                  "Strong water band near 1370–1400 nm.", "tab:purple"),
    TracerFeature("H2O/OH", "H2O/OH 1450 nm", "absorption", 1450.0, 45.0, (1350, 1380), (1520, 1550),
                  "Strong H2O/OH hydration band.", "tab:purple"),
    TracerFeature("H2O/OH", "H2O 1870 nm", "absorption", 1870.0, 55.0, (1760, 1800), (1950, 1990),
                  "Strong SWIR water band.", "tab:blue"),
    TracerFeature("H2O/OH", "H2O 1950 nm", "absorption", 1950.0, 60.0, (1820, 1860), (2020, 2060),
                  "Strong molecular water band.", "tab:blue"),

    TracerFeature("Hydrated mineral", "Al-OH 2200 nm", "absorption", 2200.0, 28.0, (2130, 2160), (2245, 2275),
                  "Al-OH clay/mica-like hydrated mineral feature.", "tab:cyan"),
    TracerFeature("Hydrated mineral", "Mg-OH 2300 nm", "absorption", 2300.0, 35.0, (2240, 2265), (2350, 2380),
                  "Mg-OH serpentine/chlorite-like feature.", "tab:cyan"),

    TracerFeature("CO2/Carbon", "CO Cameron band", "band", 240.0, 40.0, (196, 205), (272, 280),
                  "CO Cameron band linked to CO2/CO photochemistry.", "tab:gray"),
    TracerFeature("CO2/Carbon", "C I 247.9", "emission", 247.9, 1.5, (242, 245), (251, 254),
                  "Atomic carbon line.", "tab:olive"),
    TracerFeature("CO2/Carbon", "CO2+ 288.3", "emission", 288.3, 1.2, (284, 286.5), (290.5, 293),
                  "CO2+ near-UV ion tracer.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2+ 289.6", "emission", 289.6, 1.2, (285, 287), (292, 294),
                  "CO2+ near-UV ion tracer.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2+ FDB 325 nm", "band", 325.0, 15.0, (300, 308), (342, 350),
                  "CO2+ Fox-Duffendack-Barker band.", "tab:brown"),
    TracerFeature("CO2/Carbon", "C I 872.7", "emission", 872.7, 2.0, (865, 869), (876, 880),
                  "Red/NIR atomic carbon line.", "tab:olive"),
    TracerFeature("CO2/Carbon", "CO2 1437 nm", "absorption", 1437.0, 18.0, (1390, 1410), (1470, 1490),
                  "Near-IR CO2 absorption.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2 1570 nm", "absorption", 1570.0, 20.0, (1515, 1540), (1605, 1630),
                  "CO2 gas sensing band.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2 1600 nm", "absorption", 1600.0, 28.0, (1525, 1550), (1650, 1680),
                  "CO2 1.6 µm complex.", "tab:brown"),
    TracerFeature("CO2/Carbon", "CO2 1955 nm", "absorption", 1955.0, 22.0, (1900, 1925), (1995, 2020),
                  "CO2 absorption near 1955 nm.", "tab:red"),
    TracerFeature("CO2/Carbon", "CO2 2013 nm", "absorption", 2013.0, 25.0, (1950, 1975), (2050, 2075),
                  "CO2 SWIR absorption.", "tab:red"),
    TracerFeature("CO2/Carbon", "CO2 2060 nm", "absorption", 2060.0, 30.0, (1990, 2015), (2110, 2140),
                  "CO2 2.06 µm band.", "tab:red"),
    TracerFeature("CO2/Carbon", "Carbonate 2330 nm", "absorption", 2330.0, 45.0, (2230, 2260), (2400, 2450),
                  "Carbonate/carbon-bearing mineral feature.", "tab:brown"),
    TracerFeature("CO2/Carbon", "CO2 2350 nm", "absorption", 2350.0, 45.0, (2250, 2290), (2420, 2460),
                  "Strong CO2/carbonate SWIR region.", "tab:brown"),
]


MODE_INFO = {
    "Scope": "Raw detector counts.",
    "Scope - Dark": "Dark-subtracted counts: I - Dark.",
    "Absorbance": "A = -log10((I-Dark)/(I0-Dark)). Requires dark and reference.",
    "Transmission": "T = 100*(I-Dark)/(I0-Dark). Requires dark and reference.",
    "Reflection": "Reflectance proxy = 100*(I-Dark)/(I0-Dark). Requires reference standard.",
    "Rel Irradiance": "Counts divided by integration time.",
    "Normalized": "Spectrum divided by maximum absolute value.",
}


@dataclass
class Channel:
    name: str
    device_index_var: tk.StringVar
    enabled_var: tk.BooleanVar
    connected: bool = False
    spectrometer: object = None
    wavelengths: Optional[np.ndarray] = None
    dark: Optional[np.ndarray] = None
    reference: Optional[Tuple[np.ndarray, np.ndarray]] = None
    last_live: Optional[Tuple[np.ndarray, np.ndarray, str]] = None


class SpectraLabOrganicSuite:
    def __init__(self, root):
        self.root = root
        self.root.title("SpectraLab Organic/Biosignature Suite — UV/VIS/NIR + SWIR")
        self.root.geometry("1650x900")
        self.root.minsize(1150, 700)

        self._connect_authorized = False
        self.running = False
        self.spec_lock = threading.RLock()
        self.task_q = queue.Queue()
        self.plot_q = queue.Queue()

        self.int_time_ms = 100.0
        self.scans_to_avg = 1
        self.mode = "Scope"

        self.normalize_to_max = tk.BooleanVar(value=False)
        self.show_tracers = tk.BooleanVar(value=True)
        self.show_band_shading = tk.BooleanVar(value=True)
        self.show_uvvis = tk.BooleanVar(value=True)
        self.show_swir = tk.BooleanVar(value=True)
        self.show_imported = tk.BooleanVar(value=True)
        self.auto_y_peak = tk.BooleanVar(value=True)

        self.selected_species = tk.StringVar(value="All")
        self.selected_feature = tk.StringVar(value="All signatures")
        self.quick_range_var = tk.StringVar(value="Full 196–2500")

        self.x_start_nm = 196.0
        self.x_end_nm = 2500.0
        self.xstart_var = tk.StringVar(value="196")
        self.xend_var = tk.StringVar(value="2500")
        self.y_min_var = tk.StringVar(value="-0.1")
        self.y_max_var = tk.StringVar(value="1.1")
        self.avg_state = tk.StringVar(value="🟢")
        self.avg_eta = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready")
        self._last_avg_ui_update = 0.0

        self.channels: Dict[str, Channel] = {
            "UVVIS": Channel("UV/VIS/NIR 196–900", tk.StringVar(value="0"), tk.BooleanVar(value=True)),
            "SWIR": Channel("SWIR 900–2500", tk.StringVar(value="1"), tk.BooleanVar(value=True)),
        }

        self.spectra: List[Tuple[np.ndarray, np.ndarray, object, str, str]] = []
        self.measurements: List[Dict[str, object]] = []

        self.setup_ui()
        self.show_os_info()
        self.start_workers()
        self.start_plotter()

    def setup_ui(self):
        top_bar = ttk.Frame(self.root, height=46)
        top_bar.pack(fill="x", padx=10, pady=6)
        top_bar.pack_propagate(False)

        ttk.Label(top_bar, text="SpectraLab Organic/Biosignature Suite",
                  font=("Helvetica", 17, "bold"), foreground="#2c3e50").pack(side="left")
        ttk.Label(top_bar, text="UV–VIS–NIR–SWIR signatures: 196–2500 nm",
                  foreground="gray").pack(side="left", padx=14)

        specttek_label = tk.Label(top_bar, text="SpectTek Co.", font=("Helvetica", 13, "bold"),
                                  fg="#1f4e79", cursor="hand2")
        specttek_label.pack(side="right", padx=10)
        specttek_label.bind("<Button-1>", lambda e: webbrowser.open(SPECTTEK_LINK))

        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=2)
        main.add(right, weight=5)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent):
        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)

        main_tab = ttk.Frame(tabs)
        sig_tab = ttk.Frame(tabs)
        swir_tab = ttk.Frame(tabs)
        files_tab = ttk.Frame(tabs)
        diagnostics_tab = ttk.Frame(tabs)

        tabs.add(main_tab, text="Main")
        tabs.add(sig_tab, text="Signatures")
        tabs.add(swir_tab, text="SWIR")
        tabs.add(files_tab, text="Files")
        tabs.add(diagnostics_tab, text="Diagnostics")

        dev = ttk.LabelFrame(main_tab, text="Spectrometers", padding=8)
        dev.pack(fill="x", pady=(0, 4))
        ttk.Button(dev, text="List Devices", command=self.list_devices).pack(fill="x", pady=1)

        for key, ch in self.channels.items():
            row = ttk.Frame(dev)
            row.pack(fill="x", pady=1)
            ttk.Checkbutton(row, text=ch.name, variable=ch.enabled_var,
                            command=lambda: self.plot_q.put(("redraw",))).pack(side="left")
            ttk.Label(row, text="Idx").pack(side="left", padx=(4, 1))
            ttk.Entry(row, textvariable=ch.device_index_var, width=3).pack(side="left")
            ttk.Button(row, text="Connect", width=10,
                       command=lambda k=key: self.connect_channel(k)).pack(side="left", padx=3)

        ttk.Button(dev, text="Connect Both", command=self.connect_enabled_channels).pack(fill="x", pady=1)

        cap = ttk.LabelFrame(main_tab, text="Capture / Calibration", padding=8)
        cap.pack(fill="x", pady=(0, 4))

        r1 = ttk.Frame(cap); r1.pack(fill="x", pady=1)
        r2 = ttk.Frame(cap); r2.pack(fill="x", pady=1)
        r3 = ttk.Frame(cap); r3.pack(fill="x", pady=1)

        ttk.Button(r1, text="Dark UV", command=lambda: self.capture_dark("UVVIS")).pack(side="left", fill="x", expand=True, padx=1)
        ttk.Button(r1, text="Dark SWIR", command=lambda: self.capture_dark("SWIR")).pack(side="left", fill="x", expand=True, padx=1)
        ttk.Button(r2, text="Cap UV", command=lambda: self.capture_spectrum("UVVIS")).pack(side="left", fill="x", expand=True, padx=1)
        ttk.Button(r2, text="Cap SWIR", command=lambda: self.capture_spectrum("SWIR")).pack(side="left", fill="x", expand=True, padx=1)
        ttk.Button(r3, text="Ref UV", command=lambda: self.set_reference_from_last("UVVIS")).pack(side="left", fill="x", expand=True, padx=1)
        ttk.Button(r3, text="Ref SWIR", command=lambda: self.set_reference_from_last("SWIR")).pack(side="left", fill="x", expand=True, padx=1)

        exp = ttk.LabelFrame(main_tab, text="Exposure / Mode", padding=8)
        exp.pack(fill="x", pady=(0, 4))

        row = ttk.Frame(exp)
        row.pack(fill="x", pady=1)

        ttk.Label(row, text="ms").pack(side="left")
        self.int_var = tk.StringVar(value="100")
        ttk.Entry(row, textvariable=self.int_var, width=6).pack(side="left", padx=2)

        ttk.Label(row, text="avg").pack(side="left")
        self.scans_var = tk.StringVar(value="1")
        ttk.Entry(row, textvariable=self.scans_var, width=4).pack(side="left", padx=2)

        ttk.Button(row, text="Apply", command=self.apply_exposure).pack(side="left", fill="x", expand=True, padx=2)

        self.mode_combo = ttk.Combobox(exp, state="readonly", values=list(MODE_INFO.keys()), height=7)
        self.mode_combo.set(self.mode)
        self.mode_combo.pack(fill="x", pady=1)
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self.set_mode(self.mode_combo.get()))

        exp_row2 = ttk.Frame(exp)
        exp_row2.pack(fill="x", pady=1)

        ttk.Checkbutton(exp_row2, text="Normalize", variable=self.normalize_to_max,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left")
        ttk.Button(exp_row2, text="Help", width=8, command=self.show_mode_help).pack(side="right")

        display = ttk.LabelFrame(main_tab, text="Display", padding=8)
        display.pack(fill="x", pady=(0, 4))

        d1 = ttk.Frame(display); d1.pack(fill="x")
        d2 = ttk.Frame(display); d2.pack(fill="x")

        ttk.Checkbutton(d1, text="UV live", variable=self.show_uvvis,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left")
        ttk.Checkbutton(d1, text="SWIR live", variable=self.show_swir,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left", padx=8)
        ttk.Checkbutton(d1, text="Stored", variable=self.show_imported,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left")

        ttk.Checkbutton(d2, text="Lines", variable=self.show_tracers,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left")
        ttk.Checkbutton(d2, text="Bands", variable=self.show_band_shading,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left", padx=8)

        range_box = ttk.LabelFrame(main_tab, text="Quick Signature Range", padding=8)
        range_box.pack(fill="x", pady=(0, 4))

        quick_values = [
            "Full 196–2500",
            "UV–NIR Organics 196–900",
            "H2O SWIR 900–2000",
            "CO2 SWIR 1400–2450",
            "Org SWIR 1100–2350",
            "Mafic minerals 850–2250",
            "Hydrated minerals 1350–2350",
        ]

        quick = ttk.Combobox(range_box, textvariable=self.quick_range_var,
                             values=quick_values, state="readonly", height=7)
        quick.pack(fill="x", pady=2)
        quick.bind("<<ComboboxSelected>>", lambda e: self.apply_quick_range())

        ttk.Label(range_box, text="Manual X/Y ranges and status are above the plot.",
                  foreground="gray", wraplength=280).pack(fill="x", pady=(5, 0))

        sig_box = ttk.LabelFrame(sig_tab, text="Selective Signature Mode", padding=8)
        sig_box.pack(fill="both", expand=True, padx=3, pady=3)

        row2 = ttk.Frame(sig_box)
        row2.pack(fill="x")

        ttk.Label(row2, text="Species").pack(side="left")

        species_values = ["All"] + sorted({f.species for f in TRACERS})
        sp_combo = ttk.Combobox(row2, textvariable=self.selected_species,
                                values=species_values, state="readonly", width=20)
        sp_combo.pack(side="left", padx=4)
        sp_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_feature_combo())

        self.feature_combo = ttk.Combobox(sig_box, textvariable=self.selected_feature,
                                          state="readonly", height=18)
        self.feature_combo.pack(fill="x", pady=6)
        self.refresh_feature_combo()

        ttk.Button(sig_box, text="Zoom Selected Signature", command=self.zoom_selected_feature).pack(fill="x", pady=2)
        ttk.Button(sig_box, text="Measure Selected Signature", command=self.measure_selected_feature).pack(fill="x", pady=2)
        ttk.Button(sig_box, text="Measure All Visible", command=self.measure_all_features).pack(fill="x", pady=2)
        ttk.Button(sig_box, text="Export Measurements", command=self.export_measurements).pack(fill="x", pady=2)

        ttk.Label(sig_box, text="Choose one species or signature to avoid overcrowding the plot.",
                  foreground="gray", wraplength=280, justify="left").pack(fill="x", pady=(10, 0))

        swir_box = ttk.LabelFrame(swir_tab, text="Important SWIR Signatures", padding=8)
        swir_box.pack(fill="both", expand=True, padx=3, pady=3)

        ttk.Button(swir_box, text="Full SWIR", command=lambda: self.set_range(900, 2500)).pack(fill="x", pady=2)
        ttk.Button(swir_box, text="H2O/OH SWIR", command=lambda: self.set_range(900, 2000)).pack(fill="x", pady=2)
        ttk.Button(swir_box, text="CO2 / Carbonate SWIR", command=lambda: self.set_range(1400, 2450)).pack(fill="x", pady=2)
        ttk.Button(swir_box, text="Organic C-H SWIR", command=lambda: self.set_range(1100, 2350)).pack(fill="x", pady=2)
        ttk.Button(swir_box, text="Mafic Lunar Minerals", command=lambda: self.set_range(850, 2250)).pack(fill="x", pady=2)
        ttk.Button(swir_box, text="Hydrated Minerals", command=lambda: self.set_range(1350, 2350)).pack(fill="x", pady=2)

        ttk.Label(
            swir_box,
            text=(
                "SWIR guide:\n\n"
                "H2O/OH: 940, 970, 1130, 1370–1450, 1870, 1950 nm.\n\n"
                "CO2/carbonates: 1437, 1570–1600, 1955–2060, 2300–2350 nm.\n\n"
                "Organic C-H: weak bands near 1150, 1720, and 2300 nm.\n\n"
                "Hydrated minerals: Al-OH near 2200 nm and Mg-OH near 2300 nm.\n\n"
                "Mafic minerals: 1 µm olivine/pyroxene, 1.25 µm shoulder, 2 µm pyroxene."
            ),
            foreground="gray",
            wraplength=300,
            justify="left"
        ).pack(fill="both", expand=True, pady=(8, 0))

        files = ttk.LabelFrame(files_tab, text="Imported / Captured Spectra", padding=8)
        files.pack(fill="both", expand=True, padx=3, pady=3)

        ttk.Button(files, text="Import Spectrum CSV", command=self.import_spectrum_csv).pack(fill="x", pady=2)
        ttk.Button(files, text="Save Last Spectrum", command=self.save_current).pack(fill="x", pady=2)

        self.spectrum_list = tk.Listbox(files, height=12, exportselection=False)
        self.spectrum_list.pack(fill="both", expand=True, pady=5)

        ttk.Button(files, text="Remove Selected", command=self.remove_selected_spectrum).pack(fill="x", pady=2)
        ttk.Button(files, text="Change Color", command=self.change_selected_spectrum_color).pack(fill="x", pady=2)
        ttk.Button(files, text="Clear All", command=self.clear_all).pack(fill="x", pady=2)

        diagnostics_box = ttk.LabelFrame(diagnostics_tab, text="Diagnostic Guide", padding=8)
        diagnostics_box.pack(fill="both", expand=True, padx=3, pady=3)

        diagnostics_text = (
            "Deep UV to NIR, 196–900 nm:\n"
            "• Organics: UV absorption edge 196–230 nm; aromatic/PAH bands 230–300 nm.\n"
            "• Bio-analogue: chlorophyll ~430 and ~665 nm; carotenoids ~450 nm; red edge ~700–750 nm.\n"
            "• Lunar/mineral: Ti/Fe UV-blue transfer, ferric bands, npFe0 red slope, Fe2+ 1 µm shoulder.\n\n"
            "SWIR, 900–2500 nm:\n"
            "• H2O/OH: 940, 970, 1130, 1370–1450, 1870, 1950 nm.\n"
            "• Organics: C-H near 1150, 1720, 2300 nm.\n"
            "• CO2/carbonates: 1437, 1570–1600, 1955–2060, 2300–2350 nm.\n"
            "• Mafic minerals: 1 µm and 2 µm olivine/pyroxene bands.\n\n"
            "Note: these are candidate screening signatures, not proof of biology."
        )

        ttk.Label(diagnostics_box, text=diagnostics_text,
                  foreground="gray", wraplength=300, justify="left").pack(fill="both", expand=True)

    def _build_right(self, parent):
        top_controls = ttk.Frame(parent)
        top_controls.pack(fill="x", pady=(0, 4))

        ttk.Label(top_controls, text="X nm:").pack(side="left")
        ttk.Entry(top_controls, textvariable=self.xstart_var, width=7).pack(side="left", padx=2)
        ttk.Label(top_controls, text="to").pack(side="left")
        ttk.Entry(top_controls, textvariable=self.xend_var, width=7).pack(side="left", padx=2)
        ttk.Button(top_controls, text="Set X", command=self.apply_x_range).pack(side="left", padx=2)
        ttk.Button(top_controls, text="Full", command=lambda: self.set_range(196, 2500)).pack(side="left", padx=2)

        ttk.Label(top_controls, text="Y:").pack(side="left", padx=(8, 0))
        ttk.Entry(top_controls, textvariable=self.y_min_var, width=7).pack(side="left", padx=2)
        ttk.Label(top_controls, text="to").pack(side="left")
        ttk.Entry(top_controls, textvariable=self.y_max_var, width=7).pack(side="left", padx=2)
        ttk.Button(top_controls, text="Set Y", command=self.apply_y_range).pack(side="left", padx=2)

        ttk.Checkbutton(top_controls, text="Auto Y", variable=self.auto_y_peak,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left", padx=4)
        ttk.Button(top_controls, text="Auto Y Now", command=self.auto_y_to_peak).pack(side="left", padx=2)

        ttk.Label(top_controls, text="Avg:").pack(side="left", padx=(8, 2))
        ttk.Label(top_controls, textvariable=self.avg_state).pack(side="left")
        ttk.Label(top_controls, textvariable=self.avg_eta, foreground="gray").pack(side="left", padx=2)

        ttk.Label(top_controls, text="Status:").pack(side="left", padx=(10, 2))
        ttk.Label(top_controls, textvariable=self.status, foreground="#c0392b",
                  font=("Helvetica", 9, "bold")).pack(side="left", fill="x", expand=True)

        self.fig = Figure(figsize=(12, 8), dpi=100)
        self.ax = self.fig.add_axes([0.07, 0.28, 0.90, 0.66])
        self.ax_resid = self.fig.add_axes([0.10, 0.08, 0.82, 0.11])

        self._init_axes()

        self.canvas = FigureCanvasTkAgg(self.fig, parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        table_frame = ttk.LabelFrame(parent, text="Measured Features", padding=4)
        table_frame.pack(fill="x", pady=(4, 0))

        cols = ("species", "tracer", "center_nm", "kind", "peak", "integrated", "equiv_width", "snr", "note")
        self.measure_table = ttk.Treeview(table_frame, columns=cols, show="headings", height=5)

        widths = [90, 200, 80, 80, 95, 105, 105, 65, 220]
        for c, w in zip(cols, widths):
            self.measure_table.heading(c, text=c)
            self.measure_table.column(c, width=w, anchor="center")

        self.measure_table.pack(fill="x")

    def _init_axes(self):
        self.ax.set_title("UV–VIS–NIR–SWIR Spectrum with Selective Signature Windows",
                          fontsize=14, fontweight="bold")
        self.ax.set_xlabel("Wavelength (nm)")
        self.ax.set_ylabel("Intensity / Mode units")
        self.ax.grid(True, alpha=0.3, linestyle="--")
        self.ax.set_xlim(self.x_start_nm, self.x_end_nm)

        self.ax_resid.set_title("Residual / feature profile", fontsize=8, pad=2)
        self.ax_resid.set_xlabel("Wavelength (nm)", fontsize=8)
        self.ax_resid.set_ylabel("Residual", fontsize=8)
        self.ax_resid.tick_params(axis="both", labelsize=7)
        self.ax_resid.grid(True, alpha=0.25)

    def show_os_info(self):
        osys = platform.system()
        if osys == "Windows":
            osys += f" {platform.release()}"
        elif osys == "Darwin":
            osys = "macOS"

        backend = "available" if sb else "not installed"
        tk.Label(self.root, text=f"OS: {osys} • SeaBreeze: {backend}",
                 fg="gray", font=("Helvetica", 9)).pack(anchor="w", padx=20)

    def start_workers(self):
        def worker():
            while True:
                task = self.task_q.get()
                if task is None:
                    break

                func, args = task

                try:
                    result = func(*args)
                    if result is not None:
                        self.root.after(0, result)
                except Exception as e:
                    logging.exception("Worker error")
                    self.root.after(0, lambda err=e: messagebox.showerror("Error", str(err)))

                self.task_q.task_done()

        threading.Thread(target=worker, daemon=True).start()

    def queue_task(self, func, *args):
        self.task_q.put((func, args))

    def ask_connect_password(self) -> bool:
        if self._connect_authorized:
            return True

        result = {"ok": False}

        dlg = tk.Toplevel(self.root)
        dlg.title("Authorization")
        dlg.geometry("340x145")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Enter Password to Connect",
                  font=("Helvetica", 11, "bold")).pack(pady=(16, 8))

        pw = tk.StringVar()
        ent = ttk.Entry(dlg, textvariable=pw, show="*", width=25)
        ent.pack()
        ent.focus_set()

        status = ttk.Label(dlg, text="", foreground="red")
        status.pack(pady=4)

        def ok(event=None):
            if pw.get() == "SpectTek":
                result["ok"] = True
                dlg.destroy()
            else:
                status.config(text="Incorrect password")

        def cancel(event=None):
            dlg.destroy()

        row = ttk.Frame(dlg)
        row.pack(pady=8)

        ttk.Button(row, text="OK", command=ok).pack(side="left", padx=5)
        ttk.Button(row, text="Cancel", command=cancel).pack(side="left", padx=5)

        dlg.bind("<Return>", ok)
        dlg.bind("<Escape>", cancel)

        self.root.wait_window(dlg)
        self._connect_authorized = result["ok"]
        return result["ok"]

    def list_devices(self):
        if not sb:
            messagebox.showerror("SeaBreeze missing", "Install with: pip install seabreeze[cse]")
            return

        try:
            devs = sb.list_devices()
            if not devs:
                messagebox.showinfo("Devices", "No spectrometers found.")
                return

            lines = []
            for i, d in enumerate(devs):
                model = getattr(d, "model", "Spectrometer")
                serial = getattr(d, "serial_number", "unknown")
                lines.append(f"Index {i}: {model} / Serial {serial}")

            messagebox.showinfo("Available Spectrometers", "\n".join(lines))

        except Exception as e:
            messagebox.showerror("Device Error", str(e))

    def connect_enabled_channels(self):
        for key, ch in self.channels.items():
            if ch.enabled_var.get():
                self.connect_channel(key)

    def connect_channel(self, key: str):
        if not self.ask_connect_password():
            self.status.set("Connect canceled")
            return

        if not sb:
            messagebox.showerror("SeaBreeze missing", "Install with: pip install seabreeze[cse]")
            return

        ch = self.channels[key]

        def task():
            devs = sb.list_devices()
            idx = int(ch.device_index_var.get())

            if idx < 0 or idx >= len(devs):
                return lambda: messagebox.showerror("Index Error", f"No device at index {idx}")

            if ch.spectrometer:
                try:
                    ch.spectrometer.close()
                except Exception:
                    pass

            ch.spectrometer = sb.Spectrometer(devs[idx])
            ch.spectrometer.integration_time_micros(int(self.int_time_ms * 1000.0))
            ch.wavelengths = np.array(ch.spectrometer.wavelengths(), dtype=float)
            ch.connected = True
            self.running = True

            model = getattr(devs[idx], "model", "Spectrometer")
            serial = getattr(devs[idx], "serial_number", "unknown")

            return lambda: [
                self.status.set(f"Connected {ch.name}: {model}"),
                messagebox.showinfo("Connected", f"{ch.name}\n{model}\nSerial: {serial}"),
                self.start_live_thread()
            ]

        self.queue_task(task)

    def start_live_thread(self):
        if hasattr(self, "live_thread") and self.live_thread.is_alive():
            return

        self.live_thread = threading.Thread(target=self.live_loop, daemon=True)
        self.live_thread.start()

    def live_loop(self):
        while self.running:
            try:
                with self.spec_lock:
                    for key, ch in self.channels.items():
                        if not ch.connected or not ch.spectrometer or not ch.enabled_var.get():
                            continue

                        ch.spectrometer.integration_time_micros(int(self.int_time_ms * 1000.0))

                        wl = ch.wavelengths
                        if wl is None:
                            wl = np.array(ch.spectrometer.wavelengths(), dtype=float)

                        raw = self._read_avg(ch.spectrometer)
                        proc, ylabel = self._apply_mode(wl, raw, ch)
                        ch.last_live = (np.array(wl), np.array(proc), ylabel)

                self.plot_q.put(("redraw",))

            except Exception as e:
                logging.exception("Live loop stopped")
                self.root.after(0, lambda err=e: self.status.set(f"Live stopped: {err}"))
                break

    def _read_avg(self, spectrometer):
        n = max(1, int(self.scans_to_avg))
        total_est = n * max(1.0, self.int_time_ms) / 1000.0
        t0 = time.time()
        acc = None

        for _ in range(n):
            arr = np.array(spectrometer.intensities(), dtype=float)
            acc = arr if acc is None else acc + arr
            self._set_avg_ui(True, total_est - (time.time() - t0))

        self._set_avg_ui(False)
        return acc / float(n)

    def _set_avg_ui(self, working: bool, seconds_left: Optional[float] = None):
        now = time.time()

        if working and (now - self._last_avg_ui_update) < 0.10:
            return

        self._last_avg_ui_update = now

        def apply():
            self.avg_state.set("🔴" if working else "🟢")
            self.avg_eta.set(f"{max(0.0, seconds_left):.2f}s" if working and seconds_left is not None else "")

        self.root.after(0, apply)

    def apply_exposure(self):
        try:
            self.int_time_ms = float(self.int_var.get())
            self.scans_to_avg = int(float(self.scans_var.get()))

            if not (1 <= self.int_time_ms <= 1_000_000) or not (1 <= self.scans_to_avg <= 10_000):
                raise ValueError

            self.status.set(f"Exposure applied: {self.int_time_ms:.0f} ms, avg {self.scans_to_avg}")

        except Exception:
            messagebox.showerror("Error", "Integration: 1–1,000,000 ms | Avg scans: 1–10,000")

    def set_mode(self, mode: str):
        self.mode = mode
        self.status.set(f"Mode: {mode}")
        self.plot_q.put(("redraw",))

    def show_mode_help(self):
        messagebox.showinfo("Processing Mode", MODE_INFO.get(self.mode, self.mode))

    def _normalize(self, y):
        arr = np.asarray(y, dtype=float)
        finite = np.isfinite(arr)

        if not np.any(finite):
            return arr

        scale = np.nanmax(np.abs(arr[finite]))

        if not np.isfinite(scale) or scale <= 0:
            return arr

        return arr / scale

    def _apply_mode(self, wl, raw, ch: Channel):
        eps = 1e-12

        if self.mode in ("Scope", "Normalized"):
            y, label = raw, "Intensity (counts)"

        elif self.mode == "Scope - Dark":
            y = raw - ch.dark if ch.dark is not None and len(ch.dark) == len(raw) else raw
            label = "Dark-subtracted counts"

        elif self.mode in ("Absorbance", "Transmission", "Reflection"):
            if ch.reference is None:
                y, label = raw, "Intensity; reference required"
            else:
                wref, iref = ch.reference
                iref_i = np.interp(wl, wref, iref, left=np.nan, right=np.nan)

                if ch.dark is not None and len(ch.dark) == len(raw):
                    I = raw - ch.dark
                    I0 = iref_i - ch.dark
                else:
                    I, I0 = raw, iref_i

                ratio = (I + eps) / (I0 + eps)

                if self.mode == "Absorbance":
                    y, label = -np.log10(np.maximum(ratio, eps)), "Absorbance"
                elif self.mode == "Transmission":
                    y, label = 100.0 * ratio, "Transmission (%)"
                else:
                    y, label = 100.0 * ratio, "Reflection (%)"

        elif self.mode == "Rel Irradiance":
            y, label = raw / max(1.0, self.int_time_ms), "Relative irradiance (counts/ms)"

        else:
            y, label = raw, "Intensity"

        if self.normalize_to_max.get() or self.mode == "Normalized":
            return self._normalize(y), label + " / max|y|"

        return y, label

    def capture_dark(self, key: str):
        ch = self.channels[key]

        if not ch.connected:
            messagebox.showwarning("Not connected", f"Connect {ch.name} first.")
            return

        if not messagebox.askyesno("Dark Frame", f"Cover {ch.name} sensor/source, then click Yes."):
            return

        def task():
            with self.spec_lock:
                ch.dark = self._read_avg(ch.spectrometer)

            return lambda: self.status.set(f"Dark captured: {ch.name}")

        self.queue_task(task)

    def capture_spectrum(self, key: str):
        ch = self.channels[key]

        if not ch.connected:
            messagebox.showwarning("Not connected", f"Connect {ch.name} first.")
            return

        def task():
            with self.spec_lock:
                wl = ch.wavelengths
                if wl is None:
                    wl = np.array(ch.spectrometer.wavelengths(), dtype=float)

                raw = self._read_avg(ch.spectrometer)
                y, _ = self._apply_mode(wl, raw, ch)

            color = plt.cm.tab10(len(self.spectra) % 10)
            label = f"{ch.name} {datetime.now():%H:%M:%S} • {self.mode}"
            self.spectra.append((np.array(wl), np.array(y), color, label, key))

            return lambda: [
                self.refresh_spectrum_list(),
                self.plot_q.put(("redraw",)),
                self.status.set(f"Captured: {label}")
            ]

        self.queue_task(task)

    def set_reference_from_last(self, key: str):
        ch = self.channels[key]
        candidates = [s for s in self.spectra if s[4] == key]

        if not candidates:
            messagebox.showinfo("No spectrum", f"Capture/load a {ch.name} reference first.")
            return

        wl, y, *_ = candidates[-1]
        ch.reference = (np.array(wl, copy=True), np.array(y, copy=True))
        self.status.set(f"Reference set: {ch.name}")

    def import_spectrum_csv(self):
        paths = filedialog.askopenfilenames(
            title="Import spectrum CSV file(s)",
            initialdir=os.path.expanduser("~"),
            filetypes=[("Spectrum CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not paths:
            return

        for p in paths:
            try:
                df = pd.read_csv(p)

                if {"wavelength_nm", "intensity"}.issubset(df.columns):
                    wl = df["wavelength_nm"].to_numpy(float)
                    y = df["intensity"].to_numpy(float)
                else:
                    wl = df.iloc[:, 0].to_numpy(float)
                    y = df.iloc[:, 1].to_numpy(float)

                channel = "SWIR" if np.nanmax(wl) > 900 else "UVVIS"
                label = "Imported: " + os.path.basename(p)
                color = plt.cm.tab20(len(self.spectra) % 20)

                self.spectra.append((wl, y, color, label, channel))

            except Exception as e:
                messagebox.showwarning("Import skipped", f"{p}\n{e}")

        self.refresh_spectrum_list()
        self.plot_q.put(("redraw",))
        self.status.set(f"Imported {len(paths)} spectrum CSV file(s)")

    def save_current(self):
        if not self.spectra:
            messagebox.showinfo("Info", "No captured/imported spectrum to save.")
            return

        wl, y, _, label, _ = self.spectra[-1]

        f = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"spectrum_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )

        if f:
            pd.DataFrame({"wavelength_nm": wl, "intensity": y}).to_csv(f, index=False)
            messagebox.showinfo("Saved", f"Saved: {f}")

    def refresh_spectrum_list(self):
        self.spectrum_list.delete(0, tk.END)

        for i, (_wl, _y, _c, label, channel) in enumerate(self.spectra):
            self.spectrum_list.insert(tk.END, f"{i + 1}: [{channel}] {label}")

    def get_selected_spectrum_index(self) -> Optional[int]:
        sel = self.spectrum_list.curselection()

        if not sel:
            messagebox.showinfo("Select spectrum", "Select a spectrum first.")
            return None

        return int(sel[0])

    def remove_selected_spectrum(self):
        idx = self.get_selected_spectrum_index()

        if idx is None:
            return

        removed = self.spectra.pop(idx)
        self.refresh_spectrum_list()
        self.plot_q.put(("redraw",))
        self.status.set(f"Removed: {removed[3]}")

    def change_selected_spectrum_color(self):
        idx = self.get_selected_spectrum_index()

        if idx is None:
            return

        chosen = colorchooser.askcolor(title="Choose spectrum color")

        if not chosen or not chosen[1]:
            return

        wl, y, _old, label, channel = self.spectra[idx]
        self.spectra[idx] = (wl, y, chosen[1], label, channel)
        self.plot_q.put(("redraw",))

    def clear_all(self):
        self.spectra.clear()
        self.measurements.clear()
        self.refresh_spectrum_list()

        for row in self.measure_table.get_children():
            self.measure_table.delete(row)

        self.plot_q.put(("redraw",))

    def apply_x_range(self):
        try:
            self.set_range(float(self.xstart_var.get()), float(self.xend_var.get()))
        except Exception:
            messagebox.showerror("Range Error", "Enter valid X range: start < end")

    def set_range(self, x0, x1):
        if x0 >= x1:
            messagebox.showerror("Range Error", "Start wavelength must be smaller than end wavelength.")
            return

        self.x_start_nm, self.x_end_nm = float(x0), float(x1)
        self.xstart_var.set(f"{x0:.0f}")
        self.xend_var.set(f"{x1:.0f}")
        self.plot_q.put(("redraw",))

    def apply_quick_range(self):
        ranges = {
            "Full 196–2500": (196, 2500),
            "UV–NIR Organics 196–900": (196, 900),
            "H2O SWIR 900–2000": (900, 2000),
            "CO2 SWIR 1400–2450": (1400, 2450),
            "Org SWIR 1100–2350": (1100, 2350),
            "Mafic minerals 850–2250": (850, 2250),
            "Hydrated minerals 1350–2350": (1350, 2350),
        }

        x0, x1 = ranges.get(self.quick_range_var.get(), (196, 2500))
        self.set_range(x0, x1)

    def apply_y_range(self):
        try:
            ymin = float(self.y_min_var.get())
            ymax = float(self.y_max_var.get())

            if ymin >= ymax:
                raise ValueError

            self.auto_y_peak.set(False)
            self.ax.set_ylim(ymin, ymax)
            self.plot_q.put(("redraw",))

        except Exception:
            messagebox.showerror("Y Range Error", "Enter valid Y range. Example: -0.2 to 1.0")

    def auto_y_to_peak(self):
        ys = []
        x0, x1 = self.x_start_nm, self.x_end_nm

        if self.show_imported.get():
            for wl, y, _color, _label, _channel in self.spectra:
                yy = self._normalize(y) if self.normalize_to_max.get() else y
                mask = (wl >= x0) & (wl <= x1) & np.isfinite(yy)
                if np.any(mask):
                    ys.append(yy[mask])

        uv = self.channels["UVVIS"]
        sw = self.channels["SWIR"]

        if self.show_uvvis.get() and uv.last_live is not None:
            wl, y, _ = uv.last_live
            mask = (wl >= x0) & (wl <= x1) & np.isfinite(y)
            if np.any(mask):
                ys.append(y[mask])

        if self.show_swir.get() and sw.last_live is not None:
            wl, y, _ = sw.last_live
            mask = (wl >= x0) & (wl <= x1) & np.isfinite(y)
            if np.any(mask):
                ys.append(y[mask])

        if not ys:
            self.y_min_var.set("-0.1")
            self.y_max_var.set("1.1")
            self.plot_q.put(("redraw",))
            return

        data = np.concatenate(ys)
        ymin = float(np.nanmin(data))
        ymax = float(np.nanmax(data))

        if not np.isfinite(ymin) or not np.isfinite(ymax):
            return

        pad = 0.08 * (ymax - ymin) if ymin != ymax else 1.0

        self.y_min_var.set(f"{ymin - pad:.4g}")
        self.y_max_var.set(f"{ymax + pad:.4g}")
        self.auto_y_peak.set(True)
        self.plot_q.put(("redraw",))

    def visible_tracers(self):
        sp = self.selected_species.get()
        return [f for f in TRACERS if sp == "All" or f.species == sp]

    def refresh_feature_combo(self):
        sp = self.selected_species.get()
        names = ["All signatures"]

        for f in TRACERS:
            if sp == "All" or f.species == sp:
                names.append(f"{f.species}: {f.tracer} @ {f.center_nm:g} nm")

        self.feature_combo["values"] = names
        self.selected_feature.set(names[0])
        self.plot_q.put(("redraw",))

    def get_selected_feature(self) -> Optional[TracerFeature]:
        label = self.selected_feature.get()

        if label == "All signatures":
            return None

        for f in TRACERS:
            if label.startswith(f"{f.species}: {f.tracer} @"):
                return f

        return None

    def zoom_selected_feature(self):
        f = self.get_selected_feature()

        if f is None:
            messagebox.showinfo("Select feature", "Select one signature first.")
            return

        pad = max(10.0, f.window_nm * 2.2)
        self.set_range(f.center_nm - pad, f.center_nm + pad)

    def get_active_spectrum(self) -> Optional[Tuple[np.ndarray, np.ndarray, str]]:
        if self.spectra:
            wl, y, *_rest = self.spectra[-1]
            yy = self._normalize(y) if self.normalize_to_max.get() else np.array(y)
            return np.array(wl), yy, "last stored"

        for key in ("SWIR", "UVVIS"):
            ch = self.channels[key]
            if ch.last_live is not None:
                wl, y, _ = ch.last_live
                return np.array(wl), np.array(y), ch.name

        return None

    def measure_selected_feature(self):
        f = self.get_selected_feature()

        if f is None:
            messagebox.showinfo("Select feature", "Select one signature, or use Measure All Visible.")
            return

        r = self.measure_feature(f)

        if r:
            self.add_measurement(r)
            self.plot_residual(f, r)

    def measure_all_features(self):
        count = 0

        for f in self.visible_tracers():
            if self.x_start_nm <= f.center_nm <= self.x_end_nm:
                r = self.measure_feature(f)
                if r:
                    self.add_measurement(r)
                    count += 1

        self.status.set(f"Measured {count} visible feature(s)")

    def measure_feature(self, f: TracerFeature) -> Optional[Dict[str, object]]:
        active = self.get_active_spectrum()

        if active is None:
            messagebox.showinfo("No spectrum", "Capture/import a spectrum first.")
            return None

        wl, y, label = active

        if np.nanmin(wl) > f.center_nm + f.window_nm or np.nanmax(wl) < f.center_nm - f.window_nm:
            return None

        feature_mask = (wl >= f.center_nm - f.window_nm) & (wl <= f.center_nm + f.window_nm)

        cont_mask = (
            ((wl >= f.continuum_left[0]) & (wl <= f.continuum_left[1])) |
            ((wl >= f.continuum_right[0]) & (wl <= f.continuum_right[1]))
        )

        if feature_mask.sum() < 3 or cont_mask.sum() < 4:
            return None

        x_cont, y_cont = wl[cont_mask], y[cont_mask]
        finite = np.isfinite(x_cont) & np.isfinite(y_cont)

        if finite.sum() < 4:
            return None

        coeff = np.polyfit(x_cont[finite], y_cont[finite], 1)

        x = wl[feature_mask]
        baseline = np.polyval(coeff, x)
        residual = y[feature_mask] - baseline

        integrated = float(np.trapz(residual, x))
        peak = float(np.nanmax(residual))
        trough = float(np.nanmin(residual))

        noise = float(np.nanstd(y_cont[finite] - np.polyval(coeff, x_cont[finite])))
        noise = noise if noise > 0 else np.nan

        peak_value = trough if f.kind == "absorption" else peak
        strength = abs(integrated) if f.kind == "absorption" else integrated

        cont_level = float(np.nanmedian(baseline))
        ew = float(np.trapz(residual / (cont_level + 1e-12), x))

        snr = float(abs(peak_value) / noise) if np.isfinite(noise) else np.nan
        note = "candidate" if np.isfinite(snr) and snr >= 3 else "weak / upper-limit"

        return {
            "spectrum": label,
            "species": f.species,
            "tracer": f.tracer,
            "center_nm": f.center_nm,
            "kind": f.kind,
            "peak": peak_value,
            "integrated": strength,
            "equiv_width": ew,
            "snr": snr,
            "note": note,
            "x": x,
            "residual": residual
        }

    def add_measurement(self, r: Dict[str, object]):
        public = {k: v for k, v in r.items() if k not in {"x", "residual"}}
        self.measurements.append(public)

        vals = (
            r["species"],
            r["tracer"],
            f"{r['center_nm']:.1f}",
            r["kind"],
            f"{r['peak']:.4g}",
            f"{r['integrated']:.4g}",
            f"{r['equiv_width']:.4g}",
            f"{r['snr']:.2f}" if np.isfinite(r["snr"]) else "nan",
            r["note"]
        )

        self.measure_table.insert("", "end", values=vals)

    def plot_residual(self, f: TracerFeature, r: Dict[str, object]):
        self.ax_resid.cla()
        self.ax_resid.grid(True, alpha=0.25)
        self.ax_resid.axhline(0, color="gray", lw=1)
        self.ax_resid.plot(r["x"], r["residual"], lw=1.4, color=f.color)
        self.ax_resid.set_title(f"{f.species} {f.tracer}: residual", fontsize=8, pad=2)
        self.ax_resid.set_xlabel("Wavelength (nm)", fontsize=8)
        self.ax_resid.set_ylabel("Residual", fontsize=8)
        self.ax_resid.tick_params(axis="both", labelsize=7)
        self.canvas.draw_idle()

    def export_measurements(self):
        if not self.measurements:
            messagebox.showinfo("No measurements", "Measure features first.")
            return

        f = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"signature_measurements_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )

        if f:
            pd.DataFrame(self.measurements).to_csv(f, index=False)
            messagebox.showinfo("Saved", f"Saved: {f}")

    def _draw_tracers(self):
        if not self.show_tracers.get():
            return

        x0, x1 = self.ax.get_xlim()

        for f in self.visible_tracers():
            if not (x0 <= f.center_nm <= x1):
                continue

            if self.show_band_shading.get():
                self.ax.axvspan(f.center_nm - f.window_nm,
                                f.center_nm + f.window_nm,
                                color=f.color,
                                alpha=0.08)

            self.ax.axvline(f.center_nm, color=f.color, linestyle="--", lw=1.0, alpha=0.85)

            ymin, ymax = self.ax.get_ylim()
            self.ax.text(f.center_nm, ymax, f" {f.species} {f.tracer}",
                         rotation=90, va="top", ha="left",
                         fontsize=7.5, color=f.color, clip_on=True)

    def _apply_y_axis(self):
        if self.auto_y_peak.get():
            ys = []
            x0, x1 = self.x_start_nm, self.x_end_nm

            for line in self.ax.get_lines():
                x = np.asarray(line.get_xdata(), dtype=float)
                y = np.asarray(line.get_ydata(), dtype=float)
                mask = (x >= x0) & (x <= x1) & np.isfinite(y)

                if np.any(mask):
                    ys.append(y[mask])

            if ys:
                data = np.concatenate(ys)
                ymin = float(np.nanmin(data))
                ymax = float(np.nanmax(data))

                pad = 0.08 * (ymax - ymin) if ymax != ymin else 1.0

                self.ax.set_ylim(ymin - pad, ymax + pad)
                self.y_min_var.set(f"{ymin - pad:.4g}")
                self.y_max_var.set(f"{ymax + pad:.4g}")
                return

        try:
            self.ax.set_ylim(float(self.y_min_var.get()), float(self.y_max_var.get()))
        except Exception:
            self.ax.relim()
            self.ax.autoscale_view(scalex=False, scaley=True)

    def start_plotter(self):
        def plot():
            redraw = False

            while not self.plot_q.empty():
                self.plot_q.get_nowait()
                redraw = True

            if redraw:
                self.ax.cla()
                self.ax.grid(True, alpha=0.3, linestyle="--")
                self.ax.set_title("UV–VIS–NIR–SWIR Spectrum with Selective Signature Windows",
                                  fontsize=14, fontweight="bold")
                self.ax.set_xlabel("Wavelength (nm)")

                ylabel = "Intensity / Mode units"

                if self.show_imported.get():
                    for wl, y, color, label, _channel in self.spectra:
                        yy = self._normalize(y) if self.normalize_to_max.get() else y
                        self.ax.plot(wl, yy, color=color, label=label, lw=1.3)

                uv = self.channels["UVVIS"]
                sw = self.channels["SWIR"]

                if self.show_uvvis.get() and uv.last_live is not None:
                    wl, y, ylabel = uv.last_live
                    self.ax.plot(wl, y, color="black", lw=2.0, label="LIVE UV/VIS/NIR")

                if self.show_swir.get() and sw.last_live is not None:
                    wl, y, ylabel = sw.last_live
                    self.ax.plot(wl, y, color="dimgray", lw=2.0, label="LIVE SWIR")

                if self.normalize_to_max.get() or self.mode == "Normalized":
                    ylabel = ylabel + " / max|y|"

                self.ax.set_ylabel(ylabel)
                self.ax.set_xlim(self.x_start_nm, self.x_end_nm)

                self._apply_y_axis()
                self._draw_tracers()

                if self.spectra or uv.last_live is not None or sw.last_live is not None:
                    self.ax.legend(fontsize=8, loc="upper right")

                self.canvas.draw_idle()

            self.root.after(120, plot)

        self.root.after(120, plot)

    def on_close(self):
        self.running = False
        self.task_q.put(None)

        for ch in self.channels.values():
            if ch.spectrometer:
                try:
                    ch.spectrometer.close()
                except Exception:
                    pass

        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SpectraLabOrganicSuite(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()