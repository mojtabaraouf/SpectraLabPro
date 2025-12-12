import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

import numpy as np
import pandas as pd
from datetime import datetime
import logging
import os
import threading
import queue
import platform
import webbrowser
import time
from typing import Optional

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Spectrometer
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

# --- Spectral reference lines (nm) ---
REF_LINES = [
    ("Ca II K", 393.366),
    ("Ca II H", 396.847),
    ("Hδ", 410.174),
    ("Hγ", 434.047),
    ("Hβ", 486.133),
    ("Hα", 656.281),
]

# --- Mode descriptions ---
MODE_INFO = {
    "Scope": (
        "Scope: Default live view.\n"
        "Displays raw detector output (Intensity in counts).\n"
        "Use this to adjust integration time and ensure the signal is on scale."
    ),
    "Scope - Dark": (
        "Scope - Dark: Live view with dark/background subtraction.\n"
        "Shows (I - Dark) to correct detector bias/stray light before processing."
    ),
    "Absorbance": (
        "Absorbance: Measures absorbed light by a sample.\n"
        "A = -log10(T) = -log10(I / I0)\n"
        "Requires Reference (I0) and Dark for accurate baseline."
    ),
    "Transmission": (
        "Transmission (Transmittance): Measures fraction of light transmitted.\n"
        "T = I / I0 (often shown as %T)\n"
        "Requires Reference (I0) and Dark for accurate calculation."
    ),
    "Reflection": (
        "Reflection: Measures reflected light from a sample surface.\n"
        "Typically requires reflection probe + high-reflectivity standard (reference).\n"
        "Dark is also needed for best results."
    ),
    "Rel Irradiance": (
        "Rel Irradiance (Relative Irradiance): Corrects spectrum for wavelength response\n"
        "using a known incandescent lamp (NIST-traceable source).\n"
        "Gives accurate spectral shape for comparing irradiance across wavelengths.\n"
        "Absolute irradiance is possible with full calibration."
    ),
}


def ask_password_modal(parent, correct_password="SpectTek") -> bool:
    """
    Modal password dialog.
    Returns True if password is correct, False if user cancels/closes.
    """
    result = {"ok": False}

    dlg = tk.Toplevel(parent)
    dlg.title("SpectraLab Pro — Authorization Required")
    dlg.geometry("380x170")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()

    ttk.Label(dlg, text="Enter Password to Connect", font=("Helvetica", 12, "bold")).pack(pady=(18, 10))

    pw_var = tk.StringVar()
    entry = ttk.Entry(dlg, textvariable=pw_var, show="*", width=28)
    entry.pack()
    entry.focus_set()

    status = ttk.Label(dlg, text="", foreground="red")
    status.pack(pady=(8, 0))

    def ok(event=None):
        if pw_var.get() == correct_password:
            result["ok"] = True
            dlg.destroy()
        else:
            status.config(text="Incorrect password")

    def cancel(event=None):
        result["ok"] = False
        dlg.destroy()

    btns = ttk.Frame(dlg)
    btns.pack(pady=15)
    ttk.Button(btns, text="OK", width=10, command=ok).pack(side="left", padx=6)
    ttk.Button(btns, text="Cancel", width=10, command=cancel).pack(side="left", padx=6)

    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", cancel)
    dlg.protocol("WM_DELETE_WINDOW", cancel)

    parent.wait_window(dlg)
    return result["ok"]


class SpectraLabPro:
    def __init__(self, root):
        self.root = root
        self.root.title("SpectraLab Pro — Professional Spectrometer Suite")
        self.root.geometry("1450x900")
        self.root.minsize(1200, 700)

        # auth for connect
        self._connect_authorized = False

        # Device state
        self.spectrometer = None
        self.running = False

        # Data
        self.dark = None
        self.reference = None  # (wl, ints)
        self.spectra = []      # (wl, intensity, color, label)

        # Settings
        self.int_time_ms = 100.0
        self.scans_to_avg = 1
        self.mode = "Scope"

        # Plot & background infra
        self.plot_q = queue.Queue()
        self.task_q = queue.Queue()

        # Locks
        self.spec_lock = threading.RLock()
        self.settings_lock = threading.Lock()

        self.wl_cache = None

        # Pending device apply (prevents GUI blocking)
        self.pending_int_time_us = None
        self.pending_apply_event = threading.Event()

        # Range & scaling
        self.x_start_nm = 350.0
        self.x_end_nm = 1050.0
        self.autoscale_y = True

        # Averaging indicator
        self.avg_state = tk.StringVar(value="🟢")
        self.avg_eta = tk.StringVar(value="")
        self._last_avg_ui_update = 0.0

        self.setup_ui()
        self.show_os_info()
        self.start_workers()
        self.start_plotter()

    # ---------------- UI ----------------
    def setup_ui(self):
        top_bar = ttk.Frame(self.root, height=50)
        top_bar.pack(fill="x", padx=12, pady=8)
        top_bar.pack_propagate(False)

        ttk.Label(top_bar, text="SpectraLab Pro", font=("Helvetica", 18, "bold"),
                  foreground="#2c3e50").pack(side="left")

        try:
            logo_raw = tk.PhotoImage(file="logo.png")
            logo = logo_raw.subsample(10, 10)
            logo_label = tk.Label(top_bar, image=logo, cursor="hand2")
            logo_label.image = logo
            logo_label.pack(side="right", padx=15)
            logo_label.bind("<Button-1>", lambda e: webbrowser.open(
                "https://www.linkedin.com/company/specttek-company-58a804381/"))
        except Exception:
            pass

        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        # Left controls
        left = ttk.LabelFrame(main, text=" Controls", padding=20)
        main.add(left, weight=1)

        ttk.Label(left, text="Integration Time (ms)  |  Scans Avg:").pack(anchor="w", pady=(10, 5))
        row = ttk.Frame(left)
        row.pack(anchor="w", fill="x", pady=5)

        self.int_var = tk.StringVar(value="100")
        ttk.Entry(row, textvariable=self.int_var, width=10).pack(side="left", padx=(0, 8))

        self.scans_var = tk.StringVar(value="1")
        ttk.Entry(row, textvariable=self.scans_var, width=6).pack(side="left")

        ttk.Button(left, text="Apply", command=self.apply_int_and_scans, width=22).pack(pady=8)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=20)

        ttk.Button(left, text="Connect Spectrometer", command=self.connect, width=28).pack(pady=8)
        ttk.Button(left, text="Capture Dark Frame", command=self.start_dark_capture, width=28).pack(pady=8)
        ttk.Button(left, text="Capture Spectrum", command=self.start_spectrum_capture, width=28).pack(pady=15)

        ttk.Button(left, text="Load Spectra (CSV)", command=self.load_csv, width=28).pack(pady=8)
        ttk.Button(left, text="Save Current", command=self.save_current, width=28).pack(pady=8)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=20)

        ttk.Button(left, text="Clear Last", command=self.clear_last, width=28).pack(pady=5)
        ttk.Button(left, text="Clear All", command=self.clear_all, width=28).pack(pady=5)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(left, textvariable=self.status, foreground="#c0392b",
                  font=("Helvetica", 11, "bold")).pack(pady=30)

        # Right plot panel
        right = ttk.Frame(main)
        main.add(right, weight=4)

        # Top controls
        plot_top = ttk.Frame(right)
        plot_top.pack(fill="x", padx=5, pady=(0, 6))

        ttk.Label(plot_top, text="Range (nm):").pack(side="left", padx=(0, 6))
        self.xstart_var = tk.StringVar(value=str(int(self.x_start_nm)))
        self.xend_var = tk.StringVar(value=str(int(self.x_end_nm)))
        ttk.Entry(plot_top, textvariable=self.xstart_var, width=7).pack(side="left")
        ttk.Label(plot_top, text="to").pack(side="left", padx=4)
        ttk.Entry(plot_top, textvariable=self.xend_var, width=7).pack(side="left")

        ttk.Button(plot_top, text="Apply Range", command=self.apply_range).pack(side="left", padx=8)

        self.autoy_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(plot_top, text="Auto Y (fill height)", variable=self.autoy_var,
                        command=self.toggle_autoy).pack(side="left", padx=8)

        ttk.Button(plot_top, text="Fit to Data", command=self.fit_to_data).pack(side="left", padx=6)

        ttk.Label(plot_top, text="Avg:").pack(side="left", padx=(12, 4))
        ttk.Label(plot_top, textvariable=self.avg_state, font=("Helvetica", 12, "bold")).pack(side="left")
        ttk.Label(plot_top, textvariable=self.avg_eta, foreground="gray").pack(side="left", padx=(6, 0))

        # Mode row
        modes_row = ttk.Frame(right)
        modes_row.pack(fill="x", padx=5, pady=(0, 6))

        ttk.Label(modes_row, text="Mode:").pack(side="left", padx=(0, 6))
        self._mode_buttons = {}
        for m in ["Scope", "Scope - Dark", "Absorbance", "Transmission", "Reflection", "Rel Irradiance"]:
            b = ttk.Button(modes_row, text=m, width=14, command=lambda mm=m: self.set_mode(mm))
            b.pack(side="left", padx=2)
            self._mode_buttons[m] = b

        ttk.Button(modes_row, text="Set Ref (last)", width=12, command=self.set_reference_from_last).pack(side="right")

        # Figure
        self.fig = Figure(figsize=(11, 8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self._init_axes_style()

        self.canvas = FigureCanvasTkAgg(self.fig, right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Bottom bar
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", pady=10, padx=15)
        ttk.Button(bottom, text="Copy All Spectra to Clipboard",
                   command=self.copy_all_to_clipboard, width=40).pack(side="left")
        ttk.Label(bottom, text="Paste with Ctrl+V in Excel/Google Sheets",
                  foreground="gray").pack(side="right")

    def _init_axes_style(self):
        self.ax.set_title("Live & Loaded Spectra", fontsize=16, fontweight="bold")
        self.ax.set_xlabel("Wavelength (nm)", fontsize=13)
        self.ax.set_ylabel("Intensity (counts)", fontsize=13)
        self.ax.grid(True, alpha=0.3, linestyle="--")
        self.ax.set_xlim(self.x_start_nm, self.x_end_nm)

    def show_os_info(self):
        osys = platform.system()
        if osys == "Windows":
            osys += f" {platform.release()}"
        elif osys == "Darwin":
            osys = "macOS"
        backend = "cseabreeze" if sb and "c" in str(getattr(sb, "__backend__", "")) else "pyseabreeze"
        info = f"OS: {osys} • SeaBreeze: {backend if sb else 'Not installed'}"
        tk.Label(self.root, text=info, fg="gray", font=("Helvetica", 9)).pack(anchor="w", padx=20)

    # ---------------- Worker thread ----------------
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
                    self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.task_q.task_done()

        threading.Thread(target=worker, daemon=True).start()

    def queue_task(self, func, *args):
        self.task_q.put((func, args))

    # ---------------- Averaging UI (throttled) ----------------
    def _set_avg_ui(self, working: bool, seconds_left: Optional[float] = None):
        now = time.time()
        if working and (now - self._last_avg_ui_update) < 0.10:
            return
        self._last_avg_ui_update = now

        def _apply():
            self.avg_state.set("🔴" if working else "🟢")
            if working and seconds_left is not None:
                self.avg_eta.set(f"{max(0.0, seconds_left):.2f} s")
            else:
                self.avg_eta.set("")
        self.root.after(0, _apply)

    def _estimate_avg_time(self, scans: int, int_ms: float) -> float:
        return scans * (max(1.0, int_ms) / 1000.0) + 0.010

    # ---------------- Controls ----------------
    def apply_int_and_scans(self):
        try:
            t = float(self.int_var.get())
            if not (1 <= t <= 1e6):
                raise ValueError
            n = int(float(self.scans_var.get()))
            if n < 1 or n > 10000:
                raise ValueError

            with self.settings_lock:
                self.int_time_ms = t
                self.scans_to_avg = n
                self.pending_int_time_us = int(t * 1000.0)
                self.pending_apply_event.set()

            est = self._estimate_avg_time(n, t)
            self.status.set(f"Applied • Time: {t:.0f} ms • Avg: {n} (≈ {est:.2f}s/frame)")
        except Exception:
            messagebox.showerror("Error", "Integration: 1–1,000,000 ms | Scans Avg: integer >= 1")

    def apply_range(self):
        try:
            x0 = float(self.xstart_var.get())
            x1 = float(self.xend_var.get())
            if x0 >= x1:
                raise ValueError
            self.x_start_nm, self.x_end_nm = x0, x1
            self.status.set(f"Range: {x0:.0f}–{x1:.0f} nm")
        except Exception:
            messagebox.showerror("Error", "Enter valid range: start < end (nm)")

    def toggle_autoy(self):
        self.autoscale_y = bool(self.autoy_var.get())

    def fit_to_data(self):
        if not self.spectra:
            messagebox.showinfo("Info", "No captured/loaded spectra to fit.")
            return
        xs = []
        for (wl, *_rest) in self.spectra:
            xs.extend([np.nanmin(wl), np.nanmax(wl)])
        self.x_start_nm = float(min(xs))
        self.x_end_nm = float(max(xs))
        self.xstart_var.set(f"{self.x_start_nm:.0f}")
        self.xend_var.set(f"{self.x_end_nm:.0f}")
        self.status.set("Fit to data applied (X).")

    def set_mode(self, mode):
        self.mode = mode
        self.status.set(f"Mode: {mode}")
        messagebox.showinfo("Mode Info", MODE_INFO.get(mode, mode))

        if mode == "Scope - Dark" and self.dark is None:
            messagebox.showwarning("Missing Dark", "Dark spectrum is not captured yet.\nCapture Dark Frame for correct subtraction.")
        if mode in ("Absorbance", "Transmission", "Reflection"):
            missing = []
            if self.dark is None:
                missing.append("Dark")
            if self.reference is None:
                missing.append("Reference (I0)")
            if missing:
                messagebox.showwarning(
                    "Missing Requirement",
                    "For accurate results you should capture/store:\n- " + "\n- ".join(missing) +
                    "\n\nUse 'Capture Dark Frame' and 'Set Ref (last)'."
                )

    def set_reference_from_last(self):
        if not self.spectra:
            messagebox.showinfo("Info", "Capture a spectrum first, then Set Ref.")
            return
        wl, ints, *_ = self.spectra[-1]
        self.reference = (np.array(wl, copy=True), np.array(ints, copy=True))
        self.status.set("Reference set from last spectrum.")

    # ---------------- Spectrometer connect/read ----------------
    def connect(self):
        # Ask password ONLY when connecting
        if not self._connect_authorized:
            ok = ask_password_modal(self.root, correct_password="SpectTek")
            if not ok:
                self.status.set("Connect canceled (unauthorized)")
                return
            self._connect_authorized = True

        if not sb:
            messagebox.showerror("Error", "Install: pip install seabreeze[cse]")
            return

        def connect_task():
            devs = sb.list_devices()
            if not devs:
                return lambda: messagebox.showinfo("No Device", "No spectrometer found")

            if self.spectrometer:
                try:
                    self.spectrometer.close()
                except Exception:
                    pass

            self.spectrometer = sb.Spectrometer(devs[0])

            with self.settings_lock:
                int_us = int(self.int_time_ms * 1000.0)

            with self.spec_lock:
                self.spectrometer.integration_time_micros(int_us)
                self.wl_cache = self.spectrometer.wavelengths()

            self.running = True
            model = devs[0].model
            serial = devs[0].serial_number

            return lambda: [
                self.status.set(f"Connected: {model}"),
                messagebox.showinfo("Success", f"{model}\nSerial: {serial}"),
                self.start_live_thread()
            ]

        self.queue_task(connect_task)

    def start_live_thread(self):
        if hasattr(self, "live_thread") and self.live_thread.is_alive():
            return
        self.live_thread = threading.Thread(target=self.live_loop, daemon=True)
        self.live_thread.start()

    def _apply_pending_device_settings_locked(self):
        if not self.pending_apply_event.is_set():
            return
        with self.settings_lock:
            int_us = self.pending_int_time_us
        if int_us is not None and self.spectrometer is not None:
            self.spectrometer.integration_time_micros(int(int_us))
        self.pending_apply_event.clear()

    def _read_avg_intensities_locked(self):
        with self.settings_lock:
            n = max(1, int(self.scans_to_avg))
            int_ms = float(self.int_time_ms)

        total_est = self._estimate_avg_time(n, int_ms)
        t0 = time.time()
        self._set_avg_ui(True, total_est)

        acc = None
        for _ in range(n):
            v = self.spectrometer.intensities()
            if acc is None:
                acc = np.array(v, dtype=float)
            else:
                acc += v
            left = total_est - (time.time() - t0)
            self._set_avg_ui(True, left)

        out = acc / float(n)
        self._set_avg_ui(False, 0.0)
        return out

    def _apply_mode(self, wl, raw):
        eps = 1e-12

        if self.mode == "Scope":
            return raw, "Intensity (counts)"

        if self.mode == "Scope - Dark":
            if self.dark is None:
                return raw, "Intensity (counts)"
            return np.maximum(raw - self.dark, 0), "Intensity (counts)"

        if self.mode in ("Absorbance", "Transmission", "Reflection"):
            if self.reference is None:
                return raw, "Intensity (counts) — (Set Ref required)"

            wref, iref = self.reference
            iref_i = np.interp(wl, wref, iref, left=np.nan, right=np.nan)

            if self.dark is not None:
                I = np.maximum(raw - self.dark, 0)
                I0 = np.maximum(iref_i - self.dark, 0)
            else:
                I = raw
                I0 = iref_i

            ratio = (I + eps) / (I0 + eps)

            if self.mode == "Absorbance":
                return -np.log10(ratio), "Absorbance (A)"
            if self.mode == "Transmission":
                return 100.0 * ratio, "Transmission (%)"
            if self.mode == "Reflection":
                return 100.0 * ratio, "Reflection (%)"

        if self.mode == "Rel Irradiance":
            with self.settings_lock:
                t_ms = max(1.0, float(self.int_time_ms))
            return raw / max(t_ms, eps), "Relative Irradiance (counts/ms)"

        return raw, "Intensity (counts)"

    def live_loop(self):
        while self.running and self.spectrometer:
            try:
                with self.spec_lock:
                    self._apply_pending_device_settings_locked()
                    wl = self.wl_cache if self.wl_cache is not None else self.spectrometer.wavelengths()
                    raw = self._read_avg_intensities_locked()

                proc, ylabel = self._apply_mode(wl, raw)
                self.plot_q.put(("live", wl, proc, ylabel))
            except Exception:
                break

    # ---------------- Captures ----------------
    def start_dark_capture(self):
        if not self.spectrometer:
            messagebox.showwarning("Warning", "Connect first")
            return
        if not messagebox.askyesno("Dark Frame", "Cover sensor completely and click Yes"):
            return

        def capture():
            with self.spec_lock:
                self._apply_pending_device_settings_locked()
                raw = self._read_avg_intensities_locked()
            self.dark = raw
            return lambda: [
                messagebox.showinfo("Success", "Dark frame captured"),
                self.status.set("Dark active")
            ]

        self.queue_task(capture)

    def start_spectrum_capture(self):
        if not self.spectrometer:
            messagebox.showwarning("Warning", "Connect first")
            return

        def capture():
            with self.spec_lock:
                self._apply_pending_device_settings_locked()
                wl = self.wl_cache if self.wl_cache is not None else self.spectrometer.wavelengths()
                raw = self._read_avg_intensities_locked()

            proc, _ylabel = self._apply_mode(wl, raw)
            colors = plt.cm.tab10(np.linspace(0, 1, 10))
            color = colors[len(self.spectra) % 10]
            label = datetime.now().strftime("%H:%M:%S") + f" • {self.mode}"

            self.spectra.append((wl, proc, color, label))
            self.plot_q.put(("add", wl, proc, color, label))

            return lambda: self.status.set(f"Captured • Total: {len(self.spectra)}")

        self.queue_task(capture)

    # ---------------- CSV / Save / Clear / Clipboard ----------------
    def load_csv(self):
        paths = filedialog.askopenfilenames(initialdir=DATA_DIR, filetypes=[("CSV", "*.csv")])
        if not paths:
            return
        colors = plt.cm.tab20(np.linspace(0, 1, 20))
        for i, p in enumerate(paths):
            try:
                df = pd.read_csv(p)
                if not {"wavelength_nm", "intensity"}.issubset(df.columns):
                    continue
                wl = df["wavelength_nm"].values
                ints = df["intensity"].values
                color = colors[(len(self.spectra) + i) % 20]
                name = os.path.basename(p).removesuffix(".csv")
                self.spectra.append((wl, ints, color, name))
                self.plot_q.put(("add", wl, ints, color, name))
            except Exception:
                pass
        self.status.set(f"Loaded {len(paths)} • Total: {len(self.spectra)}")

    def save_current(self):
        if not self.spectra:
            messagebox.showinfo("Info", "No spectrum")
            return
        wl, ints, _, _ = self.spectra[-1]
        f = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"spectrum_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )
        if f:
            pd.DataFrame({"wavelength_nm": wl, "intensity": ints}).to_csv(f, index=False)
            messagebox.showinfo("Saved", "Done")

    def clear_last(self):
        if self.spectra:
            self.spectra.pop()
            self.plot_q.put(("redraw",))

    def clear_all(self):
        self.spectra.clear()
        self.plot_q.put(("redraw",))

    def copy_all_to_clipboard(self):
        if not self.spectra:
            messagebox.showinfo("Info", "No spectra")
            return

        all_wl = [s[0] for s in self.spectra]
        wl_min, wl_max = max(w[0] for w in all_wl), min(w[-1] for w in all_wl)
        wl_common = np.arange(wl_min, wl_max + 1, 1.0)

        data = {"Wavelength_nm": wl_common}
        for idx, (wl, ints, _, label) in enumerate(self.spectra):
            interp = np.interp(wl_common, wl, ints, left=0, right=0)
            data[f"Spectrum_{idx + 1}_{label}"] = interp

        pd.DataFrame(data).to_clipboard(index=False, excel=True)
        messagebox.showinfo("Copied!", f"{len(self.spectra)} spectra copied!\nPaste in Excel/Sheets")

    # ---------------- Plot helpers ----------------
    def _draw_reference_lines(self):
        x0, x1 = self.ax.get_xlim()
        for _name, x_nm in REF_LINES:
            if x0 <= x_nm <= x1:
                self.ax.axvline(x=x_nm, linestyle="--", linewidth=1.2, alpha=0.75, color="gray")

    def _apply_top_axis_labels(self):
        try:
            top = self.ax.secondary_xaxis("top")
            ticks, labels = [], []
            x0, x1 = self.ax.get_xlim()
            for name, x_nm in REF_LINES:
                if x0 <= x_nm <= x1:
                    ticks.append(x_nm)
                    labels.append(name)
            top.set_xticks(ticks)
            top.set_xticklabels(labels, fontsize=10)
            top.set_xlabel("")
        except Exception:
            pass

    # ---------------- Plotter ----------------
    def start_plotter(self):
        def plot():
            try:
                updated = False
                last_live = None

                while not self.plot_q.empty():
                    msg = self.plot_q.get_nowait()
                    if msg[0] == "live":
                        last_live = msg
                        updated = True
                    else:
                        updated = True

                if last_live is not None:
                    _, wl, ints, ylabel = last_live
                    self.ax.cla()
                    self.ax.grid(True, alpha=0.3)
                    self.ax.set_title("Live & Loaded Spectra", fontsize=16, fontweight="bold")
                    self.ax.set_xlabel("Wavelength (nm)")
                    self.ax.set_ylabel(ylabel)

                    for w, i, c, l in self.spectra:
                        self.ax.plot(w, i, color=c, label=l, lw=1.6)

                    self.ax.plot(wl, ints, "k", lw=3.0, label="LIVE")
                    self.ax.legend(fontsize=9.0, loc="upper right")
                    self.ax.set_xlim(self.x_start_nm, self.x_end_nm)

                    if self.autoscale_y:
                        self.ax.relim()
                        self.ax.autoscale_view(scalex=False, scaley=True)

                    self._draw_reference_lines()
                    self._apply_top_axis_labels()
                    self.canvas.draw()

                elif updated:
                    self.ax.cla()
                    self.ax.grid(True, alpha=0.3)
                    self.ax.set_title("Live & Loaded Spectra", fontsize=16, fontweight="bold")
                    self.ax.set_xlabel("Wavelength (nm)")
                    self.ax.set_ylabel("Intensity / Mode units")

                    for w, i, c, l in self.spectra:
                        self.ax.plot(w, i, color=c, label=l, lw=1.6)

                    if self.spectra:
                        self.ax.legend(fontsize=9.0, loc="upper right")

                    self.ax.set_xlim(self.x_start_nm, self.x_end_nm)
                    if self.autoscale_y:
                        self.ax.relim()
                        self.ax.autoscale_view(scalex=False, scaley=True)

                    self._draw_reference_lines()
                    self._apply_top_axis_labels()
                    self.canvas.draw()

            except queue.Empty:
                pass

            self.root.after(80, plot)

        self.root.after(80, plot)

    # ---------------- Close ----------------
    def on_close(self):
        self.running = False
        self.task_q.put(None)
        if self.spectrometer:
            try:
                with self.spec_lock:
                    self.spectrometer.close()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SpectraLabPro(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
