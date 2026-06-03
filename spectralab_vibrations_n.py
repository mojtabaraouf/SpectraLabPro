#!/usr/bin/env python3
"""
SpectraLab Vibrations
=====================

A real-time spectrometer GUI for monitoring vibration-induced optical signals
on solid metal surfaces. Designed for feasibility studies in non-contact defect
monitoring using Ocean Optics / SeaBreeze spectrometers.

Author/Organization: SpectTek
Passkey for hardware connection: SpectTek

Main capabilities
-----------------
- Live spectral acquisition from Ocean Optics spectrometers through SeaBreeze.
- User-defined monitoring wavelength(s).
- Time-domain oscillation tracking.
- Live FFT analysis for dominant vibration frequency and amplitude.
- Primary defect indicators based on optical oscillation amplitude, frequency
  deviation, drift, and signal stability.
- CSV export for spectra, time-domain signal, and FFT results.

Install example
---------------
pip install numpy scipy pandas matplotlib seabreeze

Run
---
python spectralab_vibrations.py
"""

import os
import csv
import time
import queue
import webbrowser
import threading
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import numpy as np
import pandas as pd

from scipy.fft import fft, fftfreq

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ==========================================================
# SEABREEZE IMPORT
# ==========================================================
try:
    import seabreeze.spectrometers as sb
except ImportError:
    try:
        import seabreeze
        seabreeze.use("pyseabreeze")
        import seabreeze.spectrometers as sb
    except Exception:
        sb = None


# ==========================================================
# CONSTANTS
# ==========================================================
APP_NAME = "SpectraLab Vibrations"
COMPANY_NAME = "SpectTek Co."
LINKEDIN_URL = "https://www.linkedin.com/in/specttek/"
PASSKEY = "SpectTek"

DATA_DIR = "spectralab_vibrations_data"
os.makedirs(DATA_DIR, exist_ok=True)


class SpectraLabVibrations:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1700x950")
        self.root.minsize(1450, 850)

        # Spectrometer
        self.spectrometer = None
        self.wavelengths = None
        self.dark = None
        self.reference = None

        # Acquisition settings
        self.integration_time_ms = 50.0
        self.scans_to_average = 3

        # Monitoring
        self.running = False
        self.monitor_wavelengths = [650.0, 780.0]
        self.known_frequency = 0.0
        self.monitor_start_time = None

        # Data buffers
        self.buffer_max = 1000
        self.time_buffer = []
        self.signal_buffer = []
        self.selected_wavelength_buffer = []

        # Latest spectrum
        self.latest_wavelengths = None
        self.latest_intensity = None

        # Recording
        self.recording = False
        self.record_file = None
        self.record_writer = None
        self.record_path = None

        # Queues
        self.plot_queue = queue.Queue()
        self.log_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.quick_queue = queue.Queue()

        self.build_gui()
        self.start_threads()

    # ======================================================
    # GUI
    # ======================================================
    def build_gui(self):
        self.build_header()

        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill="both", expand=True, padx=8, pady=8)

        self.left_panel = ttk.Frame(main)
        main.add(self.left_panel, weight=1)

        self.right_panel = ttk.Frame(main)
        main.add(self.right_panel, weight=4)

        self.build_control_tabs()
        self.build_plots()
        self.build_bottom_area()

    def build_header(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=10, pady=(8, 0))

        title = ttk.Label(
            header,
            text="SpectraLab Vibrations\nReal-Time Spectral Acquisition & Vibration Analysis",
            font=("Segoe UI", 16, "bold"),
            justify="left"
        )
        title.pack(side="left")

        company = tk.Label(
            header,
            text=COMPANY_NAME,
            fg="blue",
            cursor="hand2",
            font=("Segoe UI", 11, "bold", "underline")
        )
        company.pack(side="right", padx=10)
        company.bind("<Button-1>", self.open_linkedin)

    def open_linkedin(self, event=None):
        webbrowser.open_new(LINKEDIN_URL)

    def build_control_tabs(self):
        self.tabs = ttk.Notebook(self.left_panel)
        self.tabs.pack(fill="both", expand=True)

        self.tab_spectrometer = ttk.Frame(self.tabs)
        self.tab_vibration = ttk.Frame(self.tabs)
        self.tab_export = ttk.Frame(self.tabs)

        self.tabs.add(self.tab_spectrometer, text="Spectrometer Settings")
        self.tabs.add(self.tab_vibration, text="Vibrations Monitoring")
        self.tabs.add(self.tab_export, text="Export Data")

        self.build_spectrometer_tab()
        self.build_vibration_tab()
        self.build_export_tab()

    # ======================================================
    # TAB 1: SPECTROMETER SETTINGS
    # ======================================================
    def build_spectrometer_tab(self):
        frame = ttk.LabelFrame(
            self.tab_spectrometer,
            text="Ocean Optics / SeaBreeze Spectrometer",
            padding=10
        )
        frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame, text="Integration Time (ms):").pack(anchor="w")
        self.integration_var = tk.StringVar(value="50")
        ttk.Entry(frame, textvariable=self.integration_var).pack(fill="x", pady=4)

        ttk.Label(frame, text="Scans to Average:").pack(anchor="w")
        self.average_var = tk.StringVar(value="3")
        ttk.Entry(frame, textvariable=self.average_var).pack(fill="x", pady=4)

        ttk.Button(
            frame,
            text="Apply Settings",
            command=self.apply_settings
        ).pack(fill="x", pady=6)

        ttk.Separator(frame).pack(fill="x", pady=8)

        ttk.Button(
            frame,
            text="Connect Spectrometer",
            command=self.connect_spectrometer
        ).pack(fill="x", pady=4)

        ttk.Button(
            frame,
            text="Capture Dark Spectrum",
            command=self.capture_dark
        ).pack(fill="x", pady=4)

        ttk.Button(
            frame,
            text="Set Reference Spectrum",
            command=self.set_reference
        ).pack(fill="x", pady=4)

        self.status_var = tk.StringVar(value="Status: Not connected")
        ttk.Label(
            frame,
            textvariable=self.status_var,
            foreground="blue",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=12)

        info = (
            "Passkey is required before hardware connection.\n"
            "Default passkey: Ask specttek@gmail.com"
        )
        ttk.Label(frame, text=info, foreground="gray").pack(anchor="w", pady=8)

    # ======================================================
    # TAB 2: VIBRATION MONITORING
    # ======================================================
    def build_vibration_tab(self):
        frame = ttk.LabelFrame(
            self.tab_vibration,
            text="Monitoring Configuration",
            padding=10
        )
        frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame, text="Monitor Wavelengths (nm):").pack(anchor="w")
        self.monitor_wl_var = tk.StringVar(value="650.0, 780.0")
        ttk.Entry(frame, textvariable=self.monitor_wl_var).pack(fill="x", pady=4)

        ttk.Button(
            frame,
            text="Update Wavelengths",
            command=self.update_monitor_wavelengths
        ).pack(fill="x", pady=4)

        ttk.Label(frame, text="Known Metal/Shaker Frequency (Hz):").pack(anchor="w", pady=(10, 0))
        self.known_freq_var = tk.StringVar(value="0")
        ttk.Entry(frame, textvariable=self.known_freq_var).pack(fill="x", pady=4)

        ttk.Button(
            frame,
            text="Set Known Frequency",
            command=self.set_known_frequency
        ).pack(fill="x", pady=4)

        self.monitor_button = tk.Button(
            frame,
            text="Start Monitoring",
            bg="#2e8b57",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self.toggle_monitoring
        )
        self.monitor_button.pack(fill="x", pady=12)

        quick_frame = ttk.LabelFrame(
            self.tab_vibration,
            text="Quick Vibration Quantities",
            padding=8
        )
        quick_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.quick_text = tk.Text(
            quick_frame,
            height=16,
            wrap="word",
            font=("Consolas", 10)
        )
        self.quick_text.pack(fill="both", expand=True)

    # ======================================================
    # TAB 3: EXPORT DATA
    # ======================================================
    def build_export_tab(self):
        frame = ttk.LabelFrame(
            self.tab_export,
            text="Manual Export",
            padding=10
        )
        frame.pack(fill="x", padx=8, pady=8)

        ttk.Button(
            frame,
            text="Export Current Spectrum",
            command=self.export_current_spectrum
        ).pack(fill="x", pady=4)

        ttk.Button(
            frame,
            text="Export Time-Domain Data",
            command=self.export_time_domain
        ).pack(fill="x", pady=4)

        ttk.Button(
            frame,
            text="Export FFT Data",
            command=self.export_fft
        ).pack(fill="x", pady=4)

        record_frame = ttk.LabelFrame(
            self.tab_export,
            text="Live Spectral Recording",
            padding=10
        )
        record_frame.pack(fill="x", padx=8, pady=8)

        self.record_button = tk.Button(
            record_frame,
            text="Start Recording Live Spectra",
            bg="#2e8b57",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self.toggle_recording
        )
        self.record_button.pack(fill="x", pady=6)

        self.record_status_var = tk.StringVar(value="Recording: OFF")
        ttk.Label(
            record_frame,
            textvariable=self.record_status_var,
            foreground="blue",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=6)

        note = (
            "Live recording saves every acquired spectrum into CSV format.\n"
            "Each row contains timestamp, elapsed time, wavelength, and intensity."
        )
        ttk.Label(record_frame, text=note, foreground="gray").pack(anchor="w")

    # ======================================================
    # PLOTS
    # ======================================================
    def build_plots(self):
        plot_pane = ttk.PanedWindow(self.right_panel, orient=tk.HORIZONTAL)
        plot_pane.pack(fill="both", expand=True)

        spec_frame = ttk.LabelFrame(plot_pane, text="Live Spectrum", padding=8)
        plot_pane.add(spec_frame, weight=2)

        self.fig_spec = Figure(figsize=(7, 5), dpi=100)
        self.ax_spec = self.fig_spec.add_subplot(111)
        self.canvas_spec = FigureCanvasTkAgg(self.fig_spec, spec_frame)
        self.canvas_spec.get_tk_widget().pack(fill="both", expand=True)

        vib_frame = ttk.LabelFrame(plot_pane, text="Time Signal + FFT", padding=8)
        plot_pane.add(vib_frame, weight=2)

        self.fig_vib = Figure(figsize=(7, 5), dpi=100)
        self.ax_time = self.fig_vib.add_subplot(211)
        self.ax_fft = self.fig_vib.add_subplot(212)
        self.canvas_vib = FigureCanvasTkAgg(self.fig_vib, vib_frame)
        self.canvas_vib.get_tk_widget().pack(fill="both", expand=True)

    # ======================================================
    # BOTTOM AREA
    # ======================================================
    def build_bottom_area(self):
        bottom = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        bottom.pack(fill="x", padx=8, pady=(0, 8))

        result_frame = ttk.LabelFrame(
            bottom,
            text="Primary Results & Defect Indicators",
            padding=8
        )
        bottom.add(result_frame, weight=2)

        self.result_text = tk.Text(
            result_frame,
            height=10,
            wrap="word",
            font=("Consolas", 10)
        )
        self.result_text.pack(fill="both", expand=True)

        log_frame = ttk.LabelFrame(
            bottom,
            text="Event Log",
            padding=8
        )
        bottom.add(log_frame, weight=2)

        self.log_text = tk.Text(
            log_frame,
            height=10,
            wrap="word",
            font=("Consolas", 10)
        )
        self.log_text.pack(fill="both", expand=True)

    # ======================================================
    # SETTINGS
    # ======================================================
    def apply_settings(self):
        try:
            self.integration_time_ms = float(self.integration_var.get())
            self.scans_to_average = int(self.average_var.get())

            if self.spectrometer is not None:
                self.spectrometer.integration_time_micros(
                    int(self.integration_time_ms * 1000)
                )

            self.log("Spectrometer settings applied.")

        except Exception as e:
            messagebox.showerror("Settings Error", str(e))

    def update_monitor_wavelengths(self):
        try:
            values = self.monitor_wl_var.get().split(",")
            self.monitor_wavelengths = [float(v.strip()) for v in values]
            self.log(f"Monitoring wavelengths updated: {self.monitor_wavelengths}")

        except Exception:
            messagebox.showerror(
                "Wavelength Error",
                "Use comma-separated values, e.g. 650.0, 780.0"
            )

    def set_known_frequency(self):
        try:
            self.known_frequency = float(self.known_freq_var.get())
            self.log(f"Known metal/shaker frequency set to {self.known_frequency:.3f} Hz")

        except Exception:
            messagebox.showerror("Frequency Error", "Enter a valid frequency in Hz.")

    # ======================================================
    # SPECTROMETER
    # ======================================================
    def connect_spectrometer(self):
        key = simpledialog.askstring(
            "SpectTek Passkey",
            "Enter SpectTek passkey:",
            show="*"
        )

        if key != PASSKEY:
            messagebox.showerror("Access Denied", "Incorrect passkey.")
            self.log("Spectrometer connection blocked: incorrect passkey.")
            return

        if sb is None:
            messagebox.showerror(
                "SeaBreeze Missing",
                "SeaBreeze is not installed.\nInstall with: pip install seabreeze"
            )
            return

        try:
            devices = sb.list_devices()

            if not devices:
                messagebox.showinfo("No Device", "No spectrometer found.")
                self.log("No spectrometer detected.")
                return

            self.spectrometer = sb.Spectrometer(devices[0])
            self.spectrometer.integration_time_micros(
                int(self.integration_time_ms * 1000)
            )

            self.wavelengths = self.spectrometer.wavelengths()

            self.status_var.set(f"Connected: {devices[0]}")
            self.log(f"Connected to spectrometer: {devices[0]}")

        except Exception as e:
            messagebox.showerror("Connection Failed", str(e))
            self.log(f"Connection failed: {e}")

    def capture_dark(self):
        if self.spectrometer is None:
            messagebox.showwarning("No Spectrometer", "Connect the spectrometer first.")
            return

        if messagebox.askyesno(
            "Capture Dark",
            "Cover the probe completely, then press Yes."
        ):
            self.dark = self.get_averaged_spectrum()
            self.log("Dark spectrum captured.")

    def set_reference(self):
        if self.spectrometer is None:
            messagebox.showwarning("No Spectrometer", "Connect the spectrometer first.")
            return

        self.reference = self.get_averaged_spectrum()
        self.log("Reference spectrum captured.")

    def get_averaged_spectrum(self):
        spectra = []

        for _ in range(max(1, self.scans_to_average)):
            spectra.append(self.spectrometer.intensities())
            time.sleep(0.01)

        return np.mean(np.array(spectra), axis=0)

    # ======================================================
    # MONITORING
    # ======================================================
    def toggle_monitoring(self):
        self.running = not self.running

        if self.running:
            self.monitor_start_time = time.time()
            self.time_buffer.clear()
            self.signal_buffer.clear()
            self.selected_wavelength_buffer.clear()

            self.monitor_button.config(
                text="Stop Monitoring",
                bg="#b22222"
            )
            self.log("Monitoring started.")

        else:
            self.monitor_button.config(
                text="Start Monitoring",
                bg="#2e8b57"
            )
            self.log("Monitoring stopped.")

    def acquisition_loop(self):
        while True:
            if self.running and self.spectrometer is not None:
                try:
                    raw = self.get_averaged_spectrum()

                    if self.dark is not None:
                        raw = np.maximum(raw - self.dark, 0)

                    if self.reference is not None:
                        denom = np.maximum(self.reference - self.dark, 1) if self.dark is not None else np.maximum(self.reference, 1)
                        raw = raw / denom

                    self.latest_wavelengths = self.wavelengths.copy()
                    self.latest_intensity = raw.copy()

                    elapsed = time.time() - self.monitor_start_time

                    selected_values = []

                    for wl_target in self.monitor_wavelengths:
                        idx = int(np.argmin(np.abs(self.wavelengths - wl_target)))
                        selected_values.append(float(raw[idx]))

                    selected_mean = float(np.mean(selected_values))

                    self.time_buffer.append(elapsed)
                    self.signal_buffer.append(selected_mean)
                    self.selected_wavelength_buffer.append(selected_values)

                    if len(self.time_buffer) > self.buffer_max:
                        self.time_buffer.pop(0)
                        self.signal_buffer.pop(0)
                        self.selected_wavelength_buffer.pop(0)

                    self.plot_queue.put(("spectrum", self.latest_wavelengths, self.latest_intensity))
                    self.plot_queue.put(("vibration", list(self.time_buffer), list(self.signal_buffer)))

                    self.compute_results()

                    if self.recording:
                        self.write_live_spectrum(elapsed, self.latest_wavelengths, self.latest_intensity)

                except Exception as e:
                    self.log(f"Acquisition error: {e}")

            time.sleep(0.08)

    # ======================================================
    # ANALYSIS
    # ======================================================
    def compute_results(self):
        if len(self.signal_buffer) < 60:
            return

        t = np.array(self.time_buffer)
        y = np.array(self.signal_buffer)

        if t[-1] <= t[0]:
            return

        y_detrended = y - np.mean(y)

        n = len(y_detrended)
        dt = (t[-1] - t[0]) / n

        yf = fft(y_detrended)
        xf = fftfreq(n, d=dt)[:n // 2]
        amp = 2.0 / n * np.abs(yf[:n // 2])

        if len(amp) < 3:
            return

        peak_index = int(np.argmax(amp[1:]) + 1)

        dominant_frequency = float(xf[peak_index])
        dominant_amplitude = float(amp[peak_index])
        signal_std = float(np.std(y))
        signal_ptp = float(np.ptp(y))
        signal_mean = float(np.mean(y))

        result = []
        result.append("=== PRIMARY RESULTS ===")
        result.append(f"Time: {datetime.now():%H:%M:%S}")
        result.append("")
        result.append(f"Selected wavelengths: {self.monitor_wavelengths}")
        result.append(f"Dominant FFT frequency: {dominant_frequency:.3f} Hz")
        result.append(f"FFT amplitude: {dominant_amplitude:.6f}")
        result.append(f"Mean signal: {signal_mean:.6f}")
        result.append(f"Standard deviation: {signal_std:.6f}")
        result.append(f"Peak-to-peak variation: {signal_ptp:.6f}")

        quick = []
        quick.append("=== QUICK LIVE QUANTITIES ===")
        quick.append(f"Dominant frequency: {dominant_frequency:.3f} Hz")
        quick.append(f"Amplitude: {dominant_amplitude:.6f}")
        quick.append(f"Signal variation STD: {signal_std:.6f}")
        quick.append(f"Peak-to-peak: {signal_ptp:.6f}")

        if self.known_frequency > 0:
            freq_error = abs(dominant_frequency - self.known_frequency)
            percent_error = 100.0 * freq_error / self.known_frequency

            result.append("")
            result.append("=== KNOWN METAL/SHAKER FREQUENCY COMPARISON ===")
            result.append(f"Known frequency: {self.known_frequency:.3f} Hz")
            result.append(f"Frequency error: {freq_error:.3f} Hz")
            result.append(f"Frequency drift: {percent_error:.2f}%")

            quick.append(f"Known frequency: {self.known_frequency:.3f} Hz")
            quick.append(f"Frequency drift: {percent_error:.2f}%")

            if percent_error < 2:
                status = "Normal dynamic response"
            elif percent_error < 10:
                status = "Moderate stiffness variation"
            else:
                status = "Possible defect, crack growth, or stiffness loss"

            result.append(f"Status: {status}")
            quick.append(f"Status: {status}")

        result.append("")
        result.append("=== DEFECT INDICATORS ===")
        result.append("High optical oscillation amplitude may indicate a loose or cracked region.")
        result.append("Frequency drift may indicate stiffness change or defect formation.")
        result.append("Increased peak-to-peak variation may indicate unstable surface response.")

        self.result_queue.put("\n".join(result))
        self.quick_queue.put("\n".join(quick))

    # ======================================================
    # RECORDING
    # ======================================================
    def toggle_recording(self):
        if not self.recording:
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile=f"live_spectra_{datetime.now():%Y%m%d_%H%M%S}.csv",
                filetypes=[("CSV files", "*.csv")]
            )

            if not path:
                return

            self.record_path = path
            self.record_file = open(path, "w", newline="")
            self.record_writer = csv.writer(self.record_file)

            self.record_writer.writerow([
                "timestamp",
                "elapsed_time_s",
                "wavelength_nm",
                "intensity"
            ])

            self.recording = True

            self.record_button.config(
                text="Stop Recording Live Spectra",
                bg="#b22222"
            )
            self.record_status_var.set(f"Recording: ON\n{path}")
            self.log(f"Live spectral recording started: {path}")

        else:
            self.stop_recording()

    def stop_recording(self):
        self.recording = False

        if self.record_file:
            self.record_file.close()

        self.record_file = None
        self.record_writer = None

        self.record_button.config(
            text="Start Recording Live Spectra",
            bg="#2e8b57"
        )
        self.record_status_var.set("Recording: OFF")
        self.log("Live spectral recording stopped.")

    def write_live_spectrum(self, elapsed, wavelengths, intensities):
        if self.record_writer is None:
            return

        timestamp = datetime.now().isoformat()

        for wl, intensity in zip(wavelengths, intensities):
            self.record_writer.writerow([
                timestamp,
                elapsed,
                float(wl),
                float(intensity)
            ])

        self.record_file.flush()

    # ======================================================
    # EXPORT
    # ======================================================
    def export_current_spectrum(self):
        if self.latest_wavelengths is None or self.latest_intensity is None:
            messagebox.showwarning("No Data", "No spectrum is available yet.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"current_spectrum_{datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV files", "*.csv")]
        )

        if not path:
            return

        df = pd.DataFrame({
            "wavelength_nm": self.latest_wavelengths,
            "intensity": self.latest_intensity
        })

        df.to_csv(path, index=False)
        self.log(f"Current spectrum exported: {path}")

    def export_time_domain(self):
        if len(self.time_buffer) < 5:
            messagebox.showwarning("No Data", "Not enough time-domain data.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"time_domain_{datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV files", "*.csv")]
        )

        if not path:
            return

        df = pd.DataFrame({
            "time_s": self.time_buffer,
            "mean_selected_intensity": self.signal_buffer
        })

        df.to_csv(path, index=False)
        self.log(f"Time-domain data exported: {path}")

    def export_fft(self):
        if len(self.signal_buffer) < 60:
            messagebox.showwarning("No Data", "Not enough data for FFT export.")
            return

        t = np.array(self.time_buffer)
        y = np.array(self.signal_buffer)
        y = y - np.mean(y)

        n = len(y)
        dt = (t[-1] - t[0]) / n

        yf = fft(y)
        xf = fftfreq(n, d=dt)[:n // 2]
        amp = 2.0 / n * np.abs(yf[:n // 2])

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"fft_{datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV files", "*.csv")]
        )

        if not path:
            return

        df = pd.DataFrame({
            "frequency_hz": xf,
            "amplitude": amp
        })

        df.to_csv(path, index=False)
        self.log(f"FFT data exported: {path}")

    # ======================================================
    # PLOT UPDATES
    # ======================================================
    def update_spectrum_plot(self, wavelengths, intensity):
        self.ax_spec.clear()
        self.ax_spec.plot(wavelengths, intensity, linewidth=1.3)

        for wl in self.monitor_wavelengths:
            self.ax_spec.axvline(wl, linestyle="--", alpha=0.7)

        self.ax_spec.set_title("Live Spectrum")
        self.ax_spec.set_xlabel("Wavelength (nm)")
        self.ax_spec.set_ylabel("Intensity / Reflectance")
        self.ax_spec.grid(True, alpha=0.3)

        self.canvas_spec.draw_idle()

    def update_vibration_plot(self, t, signal):
        self.ax_time.clear()
        self.ax_fft.clear()

        self.ax_time.plot(np.array(t), np.array(signal), linewidth=1.3)
        self.ax_time.set_title("Selected-Wavelength Optical Oscillation")
        self.ax_time.set_xlabel("Time (s)")
        self.ax_time.set_ylabel("Mean intensity")
        self.ax_time.grid(True, alpha=0.3)

        if len(signal) >= 60:
            t_arr = np.array(t)
            y = np.array(signal)
            y = y - np.mean(y)

            n = len(y)
            dt = (t_arr[-1] - t_arr[0]) / n

            yf = fft(y)
            xf = fftfreq(n, d=dt)[:n // 2]
            amp = 2.0 / n * np.abs(yf[:n // 2])

            self.ax_fft.plot(xf, amp, linewidth=1.3)
            self.ax_fft.set_xlim(0, 120)

            if self.known_frequency > 0:
                self.ax_fft.axvline(
                    self.known_frequency,
                    linestyle="--",
                    linewidth=1.5,
                    label=f"Known {self.known_frequency:.2f} Hz"
                )
                self.ax_fft.legend()

        self.ax_fft.set_title("FFT Vibration Spectrum")
        self.ax_fft.set_xlabel("Frequency (Hz)")
        self.ax_fft.set_ylabel("Amplitude")
        self.ax_fft.grid(True, alpha=0.3)

        self.fig_vib.tight_layout()
        self.canvas_vib.draw_idle()

    # ======================================================
    # THREADS AND UI QUEUES
    # ======================================================
    def start_threads(self):
        threading.Thread(target=self.acquisition_loop, daemon=True).start()
        self.root.after(100, self.process_queues)

    def process_queues(self):
        try:
            while True:
                msg = self.plot_queue.get_nowait()

                if msg[0] == "spectrum":
                    self.update_spectrum_plot(msg[1], msg[2])

                elif msg[0] == "vibration":
                    self.update_vibration_plot(msg[1], msg[2])

        except queue.Empty:
            pass

        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")

        except queue.Empty:
            pass

        try:
            while True:
                msg = self.result_queue.get_nowait()
                self.result_text.delete("1.0", "end")
                self.result_text.insert("end", msg)

        except queue.Empty:
            pass

        try:
            while True:
                msg = self.quick_queue.get_nowait()
                self.quick_text.delete("1.0", "end")
                self.quick_text.insert("end", msg)

        except queue.Empty:
            pass

        self.root.after(100, self.process_queues)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    # ======================================================
    # CLOSE
    # ======================================================
    def on_close(self):
        self.running = False

        if self.recording:
            self.stop_recording()

        if self.spectrometer is not None:
            try:
                self.spectrometer.close()
            except Exception:
                pass

        self.root.destroy()


# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = SpectraLabVibrations(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()