#!/usr/bin/env python3
"""
Copyright (c) 2026 SpectTek Co.
All rights reserved.

SpectraLab UV–VIS–NIR–SWIR Organic/Biosignature Tracer Suite

Purpose
-------
GUI for one or two SeaBreeze-compatible spectrometers:
1) UV/VIS/NIR channel, for example 200–900 nm
2) SWIR channel, for example 900–2500 nm

The GUI can display either channel alone or both channels together. It includes
CO2, H2O/OH, mineral, organic, pigment, and biosignature-analogue tracer windows from 196–2500 nm, external CSV import, manual X/Y
range control, normalization, spectrum color changes, and feature measurement.

Important science note
----------------------
In 200–900 nm, H2O and CO2 are mostly measured through indirect tracers such as
OH, O I, CO2+, CO Cameron, and C I. In 900–2500 nm, H2O and CO2 have stronger
near-IR/SWIR absorption bands and can be measured more directly.
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


# Main reflectance/signature library from 196 to 2500 nm.
# 196–900 nm is the native deep-UV/VIS/NIR range requested for the UV-lamp reflectance
# channel. 900–2500 nm signatures are included for the optional SWIR channel/tab.
# Organic and biosignature labels are screening/analogue labels, not proof of biology.
TRACERS: List[TracerFeature] = [
    # ---------------- Deep UV / UV: organic electronic absorptions ----------------
    TracerFeature("Organic", "Deep-UV absorption edge", "absorption", 210.0, 14.0, (196.0, 202.0), (225.0, 235.0),
                  "Strong UV absorption edge from aromatic/conjugated organics, nitriles, and mineral charge-transfer overlap.", "tab:purple"),
    TracerFeature("Organic", "Aromatic/PAH π-π* band", "absorption", 255.0, 18.0, (225.0, 235.0), (285.0, 300.0),
                  "Aromatic carbon, PAH-like compounds, nucleobase-like molecules, kerogen/humic analogues.", "tab:purple"),
    TracerFeature("Organic", "Amino-acid/nucleobase UV band", "absorption", 280.0, 12.0, (250.0, 260.0), (300.0, 315.0),
                  "Screening region for amino-acid and nucleobase analogues; matrix effects are strong.", "tab:purple"),
    TracerFeature("Organic", "UV organic/mineral shoulder", "absorption", 330.0, 28.0, (285.0, 300.0), (370.0, 390.0),
                  "Broad UV shoulder from organic coatings, radiation-processed carbon, ferric phases, sulfates, or altered silicates.", "tab:purple"),
    TracerFeature("Organic", "UV darkening/slope", "slope", 375.0, 45.0, (300.0, 325.0), (430.0, 455.0),
                  "UV continuum slope caused by organics, nanophase iron, glasses, and space-weathering mixtures.", "tab:gray"),

    # ---------------- UV/VIS lunar and mineral context ----------------
    TracerFeature("Lunar/Mineral", "Ti/Fe charge-transfer UV-blue", "absorption", 410.0, 35.0, (350.0, 370.0), (455.0, 480.0),
                  "Blue/near-UV charge-transfer and maturity-sensitive region in basaltic or ilmenite-rich material.", "tab:gray"),
    TracerFeature("Lunar/Mineral", "Ferric oxide visible band", "absorption", 535.0, 35.0, (470.0, 495.0), (590.0, 620.0),
                  "Ferric iron/oxide or alteration colour feature; useful for terrestrial analogue discrimination.", "tab:brown"),
    TracerFeature("Lunar/Mineral", "npFe0 red slope/maturity", "slope", 720.0, 90.0, (500.0, 560.0), (820.0, 880.0),
                  "Continuum reddening/darkening from nanophase iron, glass abundance, grain size, and space weathering.", "tab:gray"),
    TracerFeature("Lunar/Mineral", "Fe2+ 1 µm band shoulder", "absorption", 890.0, 45.0, (740.0, 780.0), (930.0, 970.0),
                  "Short-wavelength shoulder of olivine/pyroxene Fe²⁺ crystal-field absorption; full band extends beyond 900 nm.", "tab:olive"),

    # ---------------- Pigment / biosignature analogue controls ----------------
    TracerFeature("Bio-analogue", "Carotenoid blue band", "absorption", 450.0, 25.0, (395.0, 415.0), (495.0, 520.0),
                  "Carotenoid-like pigment absorption; biological analogue control, not expected as exposed lunar biology.", "tab:orange"),
    TracerFeature("Bio-analogue", "Chlorophyll/Soret band", "absorption", 430.0, 18.0, (390.0, 405.0), (460.0, 475.0),
                  "Chlorophyll-like Soret absorption for instrument validation with terrestrial biological end-members.", "tab:green"),
    TracerFeature("Bio-analogue", "Chlorophyll red band", "absorption", 665.0, 16.0, (620.0, 635.0), (690.0, 705.0),
                  "Chlorophyll-a red absorption; useful biosignature analogue and calibration/control feature.", "tab:green"),
    TracerFeature("Bio-analogue", "Vegetation red edge", "edge", 725.0, 35.0, (670.0, 690.0), (760.0, 800.0),
                  "Sharp reflectance rise near 700–750 nm in vegetation/microbial-mat analogues.", "tab:green"),

    # ---------------- UV/VIS: H2O/OH and CO2 indirect tracers ----------------
    TracerFeature("H2O/OH", "OH A-X band", "emission", 308.5, 2.5, (300.0, 305.0), (312.0, 317.0),
                  "Indirect H2O/OH tracer: OH from water photodissociation or hydroxyl-bearing material.", "tab:blue"),
    TracerFeature("H2O/OH", "OH+ band", "emission", 335.0, 3.0, (326.0, 331.0), (339.0, 344.0),
                  "Ionized water-chemistry tracer in near-UV gas/plasma-like tests.", "tab:cyan"),
    TracerFeature("H2O/OH", "H2O near-UV absorption", "absorption", 363.0, 8.0, (345.0, 355.0), (372.0, 382.0),
                  "Weak/broad near-UV H2O/OH region; mainly a screening flag.", "tab:blue"),
    TracerFeature("H2O/OH/CO2", "[O I] green", "forbidden", 557.7, 1.5, (552.0, 555.0), (560.0, 563.0),
                  "Oxygen forbidden line; indirect H2O/OH, CO2, CO or photochemistry tracer.", "tab:green"),
    TracerFeature("H2O/OH/CO2", "[O I] red 6300", "forbidden", 630.0, 1.5, (624.0, 627.0), (633.0, 636.0),
                  "Oxygen forbidden line; can trace H2O/OH, CO2, or CO photochemistry.", "tab:red"),
    TracerFeature("H2O/OH/CO2", "[O I] red 6364", "forbidden", 636.4, 1.5, (631.0, 634.0), (640.0, 643.0),
                  "Oxygen forbidden companion line.", "tab:pink"),
    TracerFeature("CO2/Carbon", "CO Cameron band", "band", 240.0, 40.0, (196.0, 205.0), (272.0, 280.0),
                  "CO Cameron bands, often linked to CO2/CO photochemistry.", "tab:gray"),
    TracerFeature("CO2/Carbon", "C I 247.9", "emission", 247.9, 1.5, (242.0, 245.0), (251.0, 254.0),
                  "Atomic carbon line; indirect carbon-bearing gas tracer.", "tab:olive"),
    TracerFeature("CO2/Carbon", "CO2+ UV doublet 1", "emission", 288.3, 1.2, (284.0, 286.5), (290.5, 293.0),
                  "CO2+ near-UV ion tracer.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2+ UV doublet 2", "emission", 289.6, 1.2, (285.0, 287.0), (292.0, 294.0),
                  "Second CO2+ UV doublet component.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2+ FDB band", "band", 325.0, 15.0, (300.0, 308.0), (342.0, 350.0),
                  "Fox-Duffendack-Barker CO2+ band system, broadly 310–340 nm.", "tab:brown"),
    TracerFeature("CO2/Carbon", "C I 872.7", "emission", 872.7, 2.0, (865.0, 869.0), (876.0, 880.0),
                  "Red/near-IR atomic carbon line.", "tab:olive"),

    # ---------------- SWIR: H2O/OH and hydrated minerals ----------------
    TracerFeature("H2O/OH", "H2O 940 nm band", "absorption", 940.0, 18.0, (900.0, 915.0), (970.0, 985.0),
                  "Water absorption/overtone near 940 nm; also atmospheric contamination check.", "tab:blue"),
    TracerFeature("H2O/OH", "H2O/OH 970 nm band", "absorption", 970.0, 18.0, (930.0, 945.0), (1000.0, 1015.0),
                  "Water/OH overtone band near 970 nm.", "tab:blue"),
    TracerFeature("H2O/OH", "H2O 1130 nm band", "absorption", 1130.0, 30.0, (1065.0, 1090.0), (1180.0, 1210.0),
                  "Water absorption band near 1130 nm.", "tab:cyan"),
    TracerFeature("H2O/OH", "H2O 1370 nm band", "absorption", 1370.0, 45.0, (1280.0, 1310.0), (1450.0, 1480.0),
                  "Strong water absorption near 1370–1400 nm; useful but sensitive to atmosphere.", "tab:purple"),
    TracerFeature("H2O/OH", "H2O/OH 1450 nm band", "absorption", 1450.0, 45.0, (1350.0, 1380.0), (1520.0, 1550.0),
                  "Strong H2O/OH absorption near 1450 nm in hydrated minerals or water-bearing mixtures.", "tab:purple"),
    TracerFeature("H2O/OH", "H2O 1870 nm band", "absorption", 1870.0, 55.0, (1760.0, 1800.0), (1950.0, 1990.0),
                  "Strong SWIR water band near 1870–1900 nm.", "tab:blue"),
    TracerFeature("H2O/OH", "H2O 1950 nm band", "absorption", 1950.0, 60.0, (1820.0, 1860.0), (2020.0, 2060.0),
                  "Strong water absorption near 1950 nm.", "tab:blue"),
    TracerFeature("Hydrated mineral", "Al-OH 2200 nm band", "absorption", 2200.0, 28.0, (2130.0, 2160.0), (2245.0, 2275.0),
                  "Al-OH/clay/mica-like hydrated mineral band near 2.20 µm; good analogue tracer.", "tab:cyan"),
    TracerFeature("Hydrated mineral", "Mg-OH 2300 nm band", "absorption", 2300.0, 35.0, (2240.0, 2265.0), (2350.0, 2380.0),
                  "Mg-OH/serpentine/chlorite-like hydrated mineral feature.", "tab:cyan"),

    # ---------------- SWIR: CO2 / carbonates / carbon-bearing phases ----------------
    TracerFeature("CO2/Carbon", "CO2 1437 nm band", "absorption", 1437.0, 18.0, (1390.0, 1410.0), (1470.0, 1490.0),
                  "Near-IR CO2 absorption feature around 1437 nm.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2 1570 nm band", "absorption", 1570.0, 20.0, (1515.0, 1540.0), (1605.0, 1630.0),
                  "Important CO2 gas sensing band near 1570–1580 nm.", "tab:orange"),
    TracerFeature("CO2/Carbon", "CO2 1600 nm band", "absorption", 1600.0, 28.0, (1525.0, 1550.0), (1650.0, 1680.0),
                  "CO2 near-IR absorption complex around 1.6 µm.", "tab:brown"),
    TracerFeature("CO2/Carbon", "CO2 1955 nm band", "absorption", 1955.0, 22.0, (1900.0, 1925.0), (1995.0, 2020.0),
                  "CO2 near-IR absorption peak around 1955 nm.", "tab:red"),
    TracerFeature("CO2/Carbon", "CO2 2013 nm band", "absorption", 2013.0, 25.0, (1950.0, 1975.0), (2050.0, 2075.0),
                  "CO2 SWIR absorption near 2013 nm.", "tab:red"),
    TracerFeature("CO2/Carbon", "CO2 2060 nm band", "absorption", 2060.0, 30.0, (1990.0, 2015.0), (2110.0, 2140.0),
                  "CO2 band near 2.06 µm, widely used in CO2 remote sensing.", "tab:red"),
    TracerFeature("CO2/Carbon", "Carbonate 2300 nm complex", "absorption", 2330.0, 45.0, (2230.0, 2260.0), (2400.0, 2450.0),
                  "Carbonate/carbon-bearing mineral complex near 2.30–2.35 µm; overlaps organics and CO2.", "tab:brown"),
    TracerFeature("CO2/Carbon", "CO2 2350 nm band", "absorption", 2350.0, 45.0, (2250.0, 2290.0), (2420.0, 2460.0),
                  "Strong CO2 combination/overtone region near 2.35 µm.", "tab:brown"),

    # ---------------- SWIR: organic functional-group screening ----------------
    TracerFeature("Organic", "C-H overtone 1150 nm", "absorption", 1150.0, 35.0, (1080.0, 1110.0), (1210.0, 1240.0),
                  "Weak organic C-H overtone region; useful only with good reference and dry atmosphere.", "tab:purple"),
    TracerFeature("Organic", "C-H overtone 1720 nm", "absorption", 1720.0, 35.0, (1650.0, 1680.0), (1770.0, 1800.0),
                  "Organic/aliphatic C-H overtone/combination screening region.", "tab:purple"),
    TracerFeature("Organic", "C-H combination 2300 nm", "absorption", 2300.0, 45.0, (2220.0, 2250.0), (2380.0, 2410.0),
                  "Organic C-H combination region; overlaps Mg-OH and carbonate features.", "tab:purple"),

    # ---------------- SWIR: mafic lunar/planetary minerals ----------------
    TracerFeature("Lunar/Mineral", "Olivine/pyroxene 1 µm band", "absorption", 1050.0, 95.0, (850.0, 900.0), (1240.0, 1300.0),
                  "Fe²⁺ crystal-field absorption in olivine/pyroxene/basaltic lunar analogues.", "tab:olive"),
    TracerFeature("Lunar/Mineral", "Plagioclase/pyroxene 1.25 µm shoulder", "absorption", 1250.0, 55.0, (1120.0, 1160.0), (1330.0, 1380.0),
                  "Mafic/plagioclase context feature in lunar rocks and anorthositic/basaltic analogues.", "tab:olive"),
    TracerFeature("Lunar/Mineral", "Pyroxene 2 µm band", "absorption", 2000.0, 120.0, (1700.0, 1760.0), (2200.0, 2260.0),
                  "Diagnostic pyroxene Fe²⁺ band near 2 µm; key for lunar basalt/impact-melt analogues.", "tab:olive"),
]

MODE_INFO = {
    "Scope": "Raw detector counts.",
    "Scope - Dark": "Dark-subtracted counts: I - Dark. Negative values are preserved.",
    "Absorbance": "A = -log10((I-Dark)/(I0-Dark)). Requires dark and reference.",
    "Transmission": "T = 100*(I-Dark)/(I0-Dark). Requires dark and reference.",
    "Reflection": "Reflection proxy = 100*(I-Dark)/(I0-Dark). Requires reference standard.",
    "Rel Irradiance": "Counts divided by integration time. Shape only unless calibrated.",
    "Normalized": "Processed spectrum divided by maximum absolute value; keeps negative features visible.",
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


class SpectraLabDualRangeSuite:
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
        self.selected_species = tk.StringVar(value="All")
        self.selected_feature = tk.StringVar(value="All tracers")
        self.show_uvvis = tk.BooleanVar(value=True)
        self.show_swir = tk.BooleanVar(value=True)
        self.show_imported = tk.BooleanVar(value=True)

        self.x_start_nm = 196.0
        self.x_end_nm = 2500.0
        self.y_min_var = tk.StringVar(value="-0.1")
        self.y_max_var = tk.StringVar(value="1.1")
        self.avg_state = tk.StringVar(value="🟢")
        self.avg_eta = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready")
        self._last_avg_ui_update = 0.0

        self.channels: Dict[str, Channel] = {
            "UVVIS": Channel("UV/VIS 200–900", tk.StringVar(value="0"), tk.BooleanVar(value=True)),
            "SWIR": Channel("SWIR 900–2500", tk.StringVar(value="1"), tk.BooleanVar(value=True)),
        }
        self.spectra: List[Tuple[np.ndarray, np.ndarray, object, str, str]] = []
        self.measurements: List[Dict[str, object]] = []

        self.setup_ui()
        self.show_os_info()
        self.start_workers()
        self.start_plotter()

    # ---------------- UI ----------------
    def setup_ui(self):
        top_bar = ttk.Frame(self.root, height=46)
        top_bar.pack(fill="x", padx=10, pady=6)
        top_bar.pack_propagate(False)

        ttk.Label(top_bar, text="SpectraLab Dual-Range Suite", font=("Helvetica", 17, "bold"),
                  foreground="#2c3e50").pack(side="left")
        ttk.Label(top_bar, text="Organic / biosignature / mineral tracers: 196–2500 nm", foreground="gray").pack(side="left", padx=14)

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
        self._build_bottom_bar()

    def _build_left(self, parent):
        # Left column is now tabbed so Tracer Tools and file controls do not run
        # outside the visible GUI screen on smaller monitors.
        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)

        main_tab = ttk.Frame(tabs)
        tracer_tab = ttk.Frame(tabs)
        swir_tab = ttk.Frame(tabs)
        files_tab = ttk.Frame(tabs)
        diagnostics_tab = ttk.Frame(tabs)
        tabs.add(main_tab, text="Main")
        tabs.add(tracer_tab, text="UV–NIR Signatures")
        tabs.add(swir_tab, text="SWIR Signatures")
        tabs.add(files_tab, text="Files")
        tabs.add(diagnostics_tab, text="Diagnostics")

        dev = ttk.LabelFrame(main_tab, text="Spectrometers", padding=8)
        dev.pack(fill="x", pady=(0, 4))
        ttk.Button(dev, text="List Devices", command=self.list_devices).pack(fill="x", pady=1)

        for key, ch in self.channels.items():
            row = ttk.Frame(dev)
            row.pack(fill="x", pady=1)
            ttk.Checkbutton(row, text=ch.name.replace(" 200–900", "").replace(" 900–2500", ""),
                            variable=ch.enabled_var,
                            command=lambda: self.plot_q.put(("redraw",))).pack(side="left")
            ttk.Label(row, text="Idx").pack(side="left", padx=(4, 1))
            ttk.Entry(row, textvariable=ch.device_index_var, width=3).pack(side="left")
            ttk.Button(row, text="Connect", width=12, command=lambda k=key: self.connect_channel(k)).pack(side="left", padx=3)

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
        exp_row2 = ttk.Frame(exp); exp_row2.pack(fill="x", pady=1)
        ttk.Checkbutton(exp_row2, text="Normalize", variable=self.normalize_to_max,
                        command=lambda: self.plot_q.put(("redraw",))).pack(side="left")
        ttk.Button(exp_row2, text="Help", width=8, command=self.show_mode_help).pack(side="right")

        show = ttk.LabelFrame(main_tab, text="Display", padding=8)
        show.pack(fill="x", pady=(0, 4))
        d1 = ttk.Frame(show); d1.pack(fill="x")
        d2 = ttk.Frame(show); d2.pack(fill="x")
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

        trac = ttk.LabelFrame(tracer_tab, text="Tracer Tools", padding=8)
        trac.pack(fill="both", expand=True, padx=3, pady=3)
        row2 = ttk.Frame(trac)
        row2.pack(fill="x")
        ttk.Label(row2, text="Species").pack(side="left")
        species_values = ["All"] + sorted({f.species for f in TRACERS})
        sp_combo = ttk.Combobox(row2, textvariable=self.selected_species,
                                values=species_values, state="readonly", width=18)
        sp_combo.pack(side="left", padx=4)
        sp_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_feature_combo())
        self.feature_combo = ttk.Combobox(trac, textvariable=self.selected_feature, state="readonly", height=16)
        self.feature_combo.pack(fill="x", pady=6)
        self.refresh_feature_combo()
        ttk.Button(trac, text="Zoom Feature", command=self.zoom_selected_feature).pack(fill="x", pady=2)
        ttk.Button(trac, text="Measure Signature", command=self.measure_selected_feature).pack(fill="x", pady=2)
        ttk.Button(trac, text="Measure All Visible", command=self.measure_all_features).pack(fill="x", pady=2)
        ttk.Button(trac, text="Export Measurements", command=self.export_measurements).pack(fill="x", pady=2)
        ttk.Label(trac, text="Tip: choose 900–2500 or CO2/H2O SWIR range buttons above the plot for direct SWIR absorption bands.",
                  foreground="gray", wraplength=280).pack(fill="x", pady=(10, 0))

        swir_box = ttk.LabelFrame(swir_tab, text="SWIR Signature Control / Guide", padding=8)
        swir_box.pack(fill="both", expand=True, padx=3, pady=3)

        swir_buttons = ttk.Frame(swir_box)
        swir_buttons.pack(fill="x", pady=(0, 6))
        ttk.Button(swir_buttons, text="H2O/OH 0.9–2.0 µm", command=lambda: self.set_range(900, 2000)).pack(fill="x", pady=1)
        ttk.Button(swir_buttons, text="Organics 1.1–2.35 µm", command=lambda: self.set_range(1100, 2350)).pack(fill="x", pady=1)
        ttk.Button(swir_buttons, text="Carbonates/CO2 1.4–2.45 µm", command=lambda: self.set_range(1400, 2450)).pack(fill="x", pady=1)
        ttk.Button(swir_buttons, text="Mafic minerals 0.9–2.25 µm", command=lambda: self.set_range(900, 2250)).pack(fill="x", pady=1)

        ttk.Label(
            swir_box,
            text=(
                "SWIR signatures added for optional 900–2500 nm channel:\n\n"
                "• H₂O/OH: 940, 970, 1130, 1370–1450, 1870–1950 nm.\n"
                "• Hydrated minerals: Al-OH near 2200 nm, Mg-OH near 2300 nm.\n"
                "• Organics: weak C-H overtone/combination regions near 1150, 1720, and 2300 nm.\n"
                "• Carbonates/CO₂: 1437, 1570–1600, 1955–2060, 2300–2350 nm.\n"
                "• Lunar minerals: olivine/pyroxene 1 µm band, 1.25 µm shoulder, pyroxene 2 µm band.\n\n"
                "Use Reflection or Absorbance mode with dark + white reference for rock reflectance."
            ),
            foreground="gray",
            wraplength=300,
            justify="left"
        ).pack(fill="both", expand=True)

        files = ttk.LabelFrame(files_tab, text="Imported / Captured Spectra", padding=8)
        files.pack(fill="both", expand=True, padx=3, pady=3)
        ttk.Button(files, text="Import Spectrum CSV", command=self.import_spectrum_csv).pack(fill="x", pady=2)
        ttk.Button(files, text="Save Last Spectrum", command=self.save_current).pack(fill="x", pady=2)
        self.spectrum_list = tk.Listbox(files, height=12, exportselection=False)
        self.spectrum_list.pack(fill="both", expand=True, pady=5)
        ttk.Button(files, text="Remove Selected", command=self.remove_selected_spectrum).pack(fill="x", pady=2)
        ttk.Button(files, text="Change Color", command=self.change_selected_spectrum_color).pack(fill="x", pady=2)
        ttk.Button(files, text="Clear All", command=self.clear_all).pack(fill="x", pady=2)

        suite_title = ttk.Label(
            diagnostics_tab,
            text="SpectraLab Dual-Range Suite — UV/VIS + SWIR CO₂/H₂O diagnostics",
            foreground="gray",
            font=("Helvetica", 10, "bold"),
            wraplength=300,
            justify="left"
        )
        suite_title.pack(fill="x", padx=6, pady=(6, 2))

        diagnostics_box = ttk.LabelFrame(diagnostics_tab, text="Diagnostic Line / Band Guide", padding=8)
        diagnostics_box.pack(fill="both", expand=True, padx=3, pady=3)

        diagnostics_text = (
          "Deep UV to NIR, 196–900 nm:\\n"
          "• Organics: UV absorption edge 196–230 nm; aromatic/PAH/nucleobase-like bands 230–300 nm; broad UV shoulder 300–400 nm.\\n"
          "• Bio-analogue controls: chlorophyll/Soret ~430 nm, carotenoids ~450 nm, chlorophyll red ~665 nm, red edge ~700–750 nm.\\n"
          "• Lunar/mineral context: Ti/Fe UV-blue charge transfer, ferric oxide ~500–600 nm, npFe⁰ red slope/maturity, Fe²⁺ 1 µm shoulder near 850–900 nm.\\n"
          "• Volatile/gas photochemistry: OH 308 nm, OH⁺ 335 nm, [O I] 557.7/630/636.4 nm, CO Cameron, CO₂⁺, C I.\\n\\n"

          "SWIR range, 900–2500 nm:\\n"
          "• H₂O/OH: 940, 970, 1130, 1370–1450, 1870, 1950 nm.\\n"
          "• Hydrated minerals: Al-OH near 2200 nm, Mg-OH near 2300 nm.\\n"
          "• Organics: weak C-H overtone/combination regions near 1150, 1720, 2300 nm.\\n"
          "• CO₂/carbonates: 1437, 1570–1600, 1955–2060, 2300–2350 nm.\\n"
          "• Lunar mafic minerals: 1 µm olivine/pyroxene band, 1.25 µm shoulder, 2 µm pyroxene band.\\n\\n"

          "Interpretation rule: these are candidate screening signatures. Confirm organics/biosignatures "
          "with reference standards, blanks, repeated measurements, and complementary Raman/fluorescence/FTIR/MS."
        )
        ttk.Label(
            diagnostics_box,
            text=diagnostics_text,
            foreground="gray",
            wraplength=300,
            justify="left"
        ).pack(fill="both", expand=True)

        status_box = ttk.LabelFrame(main_tab, text="Status", padding=6)
        status_box.pack(fill="x", padx=3, pady=(6,3))
        ttk.Label(status_box,
                  textvariable=self.status,
                  foreground="#c0392b",
                  font=("Helvetica", 9, "bold"),
                  wraplength=280,
                  justify="left").pack(fill="x")

    def _build_right(self, parent):
        controls = ttk.Frame(parent)
        controls.pack(fill="x", pady=(0, 4))
        ttk.Label(controls, text="X nm:").pack(side="left")
        self.xstart_var = tk.StringVar(value="196")
        self.xend_var = tk.StringVar(value="2500")
        ttk.Entry(controls, textvariable=self.xstart_var, width=7).pack(side="left", padx=2)
        ttk.Label(controls, text="-").pack(side="left")
        ttk.Entry(controls, textvariable=self.xend_var, width=7).pack(side="left", padx=2)
        ttk.Button(controls, text="Set X", command=self.apply_x_range).pack(side="left", padx=3)
        ttk.Button(controls, text="196–900", command=lambda: self.set_range(196, 900)).pack(side="left", padx=1)
        ttk.Button(controls, text="900–2500", command=lambda: self.set_range(900, 2500)).pack(side="left", padx=1)
        ttk.Button(controls, text="Full", command=lambda: self.set_range(196, 2500)).pack(side="left", padx=1)
        ttk.Button(controls, text="H2O SWIR", command=lambda: self.set_range(900, 2000)).pack(side="left", padx=1)
        ttk.Button(controls, text="CO2 SWIR", command=lambda: self.set_range(1400, 2400)).pack(side="left", padx=1)
        ttk.Button(controls, text="Org SWIR", command=lambda: self.set_range(1100, 2350)).pack(side="left", padx=1)
        ttk.Button(controls, text="Mafic", command=lambda: self.set_range(850, 2250)).pack(side="left", padx=1)

        ttk.Label(controls, text="Y:").pack(side="left", padx=(8, 0))
        ttk.Entry(controls, textvariable=self.y_min_var, width=7).pack(side="left", padx=2)
        ttk.Label(controls, text="-").pack(side="left")
        ttk.Entry(controls, textvariable=self.y_max_var, width=7).pack(side="left", padx=2)
        ttk.Button(controls, text="Set Y", command=self.apply_y_range).pack(side="left", padx=3)
        ttk.Label(controls, text="Avg:").pack(side="left", padx=(8, 3))
        ttk.Label(controls, textvariable=self.avg_state).pack(side="left")
        ttk.Label(controls, textvariable=self.avg_eta, foreground="gray").pack(side="left", padx=3)

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
        widths = [65, 180, 80, 80, 95, 105, 105, 65, 220]
        for c, w in zip(cols, widths):
            self.measure_table.heading(c, text=c)
            self.measure_table.column(c, width=w, anchor="center")
        self.measure_table.pack(fill="x")

    def _build_bottom_bar(self):
        # Bottom bar intentionally left empty; diagnostic text is placed
        # inside the Diagnostics tab to keep the main screen clean.
        return

    def _init_axes(self):
        self.ax.set_title("UV/VIS/NIR + SWIR Reflectance Signatures", fontsize=14, fontweight="bold")
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
        tk.Label(self.root, text=f"OS: {osys} • SeaBreeze: {backend}", fg="gray", font=("Helvetica", 9)).pack(anchor="w", padx=20)

    # ---------------- Workers ----------------
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

    # ---------------- Device handling ----------------
    def ask_connect_password(self) -> bool:
        if self._connect_authorized:
            return True
        result = {"ok": False}
        dlg = tk.Toplevel(self.root)
        dlg.title("Authorization")
        dlg.geometry("340x145")
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text="Enter Password to Connect", font=("Helvetica", 11, "bold")).pack(pady=(16, 8))
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
            return lambda: [self.status.set(f"Connected {ch.name}: {model}"),
                            messagebox.showinfo(
                                "Connected",
                                f"{ch.name}\n{model}\nSerial: {serial}"
                            ),
                            self.start_live_thread()]
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
                        wl = ch.wavelengths if ch.wavelengths is not None else np.array(ch.spectrometer.wavelengths())
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

    # ---------------- Processing ----------------
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

    # ---------------- Capture / reference ----------------
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
                wl = ch.wavelengths if ch.wavelengths is not None else np.array(ch.spectrometer.wavelengths())
                raw = self._read_avg(ch.spectrometer)
                y, _ = self._apply_mode(wl, raw, ch)
            color = plt.cm.tab10(len(self.spectra) % 10)
            label = f"{ch.name} {datetime.now():%H:%M:%S} • {self.mode}"
            self.spectra.append((np.array(wl), np.array(y), color, label, key))
            return lambda: [self.refresh_spectrum_list(), self.plot_q.put(("redraw",)),
                            self.status.set(f"Captured: {label}")]
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

    # ---------------- Import / save / list ----------------
    def import_spectrum_csv(self):
        paths = filedialog.askopenfilenames(
            title="Import spectrum CSV file(s)",
            initialdir=os.path.expanduser("~"),
            filetypes=[("Spectrum CSV files", "*.csv"), ("All files", "*.*")],
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
                messagebox.showwarning(
                    "Import skipped",
                    f"{p}\n{e}"
                )
        self.refresh_spectrum_list()
        self.plot_q.put(("redraw",))
        self.status.set(f"Imported {len(paths)} spectrum CSV file(s)")

    def save_current(self):
        if not self.spectra:
            messagebox.showinfo("Info", "No captured/imported spectrum to save.")
            return
        wl, y, _, label, _ = self.spectra[-1]
        f = filedialog.asksaveasfilename(defaultextension=".csv",
                                         initialfile=f"spectrum_{datetime.now():%Y%m%d_%H%M%S}.csv")
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

    # ---------------- Ranges and tracers ----------------
    def apply_x_range(self):
        try:
            self.set_range(float(self.xstart_var.get()), float(self.xend_var.get()))
        except Exception:
            messagebox.showerror("Range Error", "Enter valid X range: start < end")

    def set_range(self, x0, x1):
        if x0 >= x1:
            raise ValueError
        self.x_start_nm, self.x_end_nm = float(x0), float(x1)
        self.xstart_var.set(f"{x0:.0f}")
        self.xend_var.set(f"{x1:.0f}")
        self.plot_q.put(("redraw",))

    def apply_y_range(self):
        try:
            ymin = float(self.y_min_var.get())
            ymax = float(self.y_max_var.get())
            if ymin >= ymax:
                raise ValueError
            self.ax.set_ylim(ymin, ymax)
            self.plot_q.put(("redraw",))
        except Exception:
            messagebox.showerror("Y Range Error", "Enter valid Y range. Negative values are allowed, e.g. -0.2 to 1.0")

    def visible_tracers(self):
        sp = self.selected_species.get()
        return [f for f in TRACERS if sp == "All" or f.species == sp]

    def refresh_feature_combo(self):
        sp = self.selected_species.get()
        names = ["All tracers"]
        for f in TRACERS:
            if sp == "All" or f.species == sp:
                names.append(f"{f.species}: {f.tracer} @ {f.center_nm:g} nm")
        self.feature_combo["values"] = names
        self.selected_feature.set(names[0])
        self.plot_q.put(("redraw",))

    def get_selected_feature(self) -> Optional[TracerFeature]:
        label = self.selected_feature.get()
        if label == "All tracers":
            return None
        for f in TRACERS:
            if label.startswith(f"{f.species}: {f.tracer} @"):
                return f
        return None

    def zoom_selected_feature(self):
        f = self.get_selected_feature()
        if f is None:
            messagebox.showinfo("Select feature", "Select one tracer first.")
            return
        pad = max(10.0, f.window_nm * 2.2)
        self.set_range(f.center_nm - pad, f.center_nm + pad)

    # ---------------- Measurement ----------------
    def get_active_spectrum(self) -> Optional[Tuple[np.ndarray, np.ndarray, str]]:
        if self.spectra:
            wl, y, *_rest = self.spectra[-1]
            return np.array(wl), self._normalize(y) if self.normalize_to_max.get() else np.array(y), "last stored"
        for key in ("SWIR", "UVVIS"):
            ch = self.channels[key]
            if ch.last_live is not None:
                wl, y, _ = ch.last_live
                return np.array(wl), np.array(y), ch.name
        return None

    def measure_selected_feature(self):
        f = self.get_selected_feature()
        if f is None:
            messagebox.showinfo("Select feature", "Select one tracer, or use Measure All Visible.")
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
        cont_mask = ((wl >= f.continuum_left[0]) & (wl <= f.continuum_left[1])) | \
                    ((wl >= f.continuum_right[0]) & (wl <= f.continuum_right[1]))
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
        return {"spectrum": label, "species": f.species, "tracer": f.tracer, "center_nm": f.center_nm,
                "kind": f.kind, "peak": peak_value, "integrated": strength, "equiv_width": ew,
                "snr": snr, "note": note, "x": x, "residual": residual}

    def add_measurement(self, r: Dict[str, object]):
        public = {k: v for k, v in r.items() if k not in {"x", "residual"}}
        self.measurements.append(public)
        vals = (r["species"], r["tracer"], f"{r['center_nm']:.1f}", r["kind"],
                f"{r['peak']:.4g}", f"{r['integrated']:.4g}", f"{r['equiv_width']:.4g}",
                f"{r['snr']:.2f}" if np.isfinite(r["snr"]) else "nan", r["note"])
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
            messagebox.showinfo("No measurements", "Measure signatures first.")
            return
        f = filedialog.asksaveasfilename(defaultextension=".csv",
                                         initialfile=f"co2_h2o_measurements_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if f:
            pd.DataFrame(self.measurements).to_csv(f, index=False)
            messagebox.showinfo("Saved", f"Saved: {f}")

    # ---------------- Plotting ----------------
    def _draw_tracers(self):
        if not self.show_tracers.get():
            return
        x0, x1 = self.ax.get_xlim()
        for f in self.visible_tracers():
            if not (x0 <= f.center_nm <= x1):
                continue
            if self.show_band_shading.get():
                self.ax.axvspan(f.center_nm - f.window_nm, f.center_nm + f.window_nm,
                                color=f.color, alpha=0.08)
            self.ax.axvline(f.center_nm, color=f.color, linestyle="--", lw=1.0, alpha=0.85)
            ymin, ymax = self.ax.get_ylim()
            self.ax.text(f.center_nm, ymax, f" {f.species} {f.tracer}", rotation=90,
                         va="top", ha="left", fontsize=7.5, color=f.color, clip_on=True)

    def _apply_y_axis(self):
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
                self.ax.set_title("UV/VIS/NIR + SWIR Organic, Biosignature, Mineral and Volatile Signatures", fontsize=14, fontweight="bold")
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
                    self.ax.plot(wl, y, color="black", lw=2.0, label="LIVE UV/VIS")
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
    app = SpectraLabDualRangeSuite(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
