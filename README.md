# SpectraLabPro
Professional Spectrometer Control &amp; Analysis GUI

SpectraLab Pro is a Python-based graphical application for controlling SeaBreeze-compatible spectrometers and performing common optical spectroscopy measurements. It provides a responsive live display, multiple analysis modes, and a clean workflow suitable for laboratory, educational, and field use.

Features
   •  Live spectrum display (Scope mode)
   •  Dark subtraction (Scope − Dark)
   •  Absorbance, Transmission, Reflection measurements
   •  Relative Irradiance (spectral shape correction)
   •  Adjustable integration time and scans-to-average
   •  Noise reduction via scan averaging with progress indicator
   •  Wavelength range control and auto-scaling
   •  Fixed spectral reference lines (Hα, Hβ, Hγ, Hδ, Ca II H & K)
   •  CSV import/export
   •  One-click copy to Excel / Google Sheets
   •  Password-protected spectrometer connection
   •  Stable, non-blocking GUI (safe for long integrations)

Supported Hardware
   •  Ocean Optics / Ocean Insight spectrometers
   •  Any device supported by SeaBreeze
Recommended backend: cseabreeze

Requirements
   •  Python 3.8+
   •  Windows, macOS, or Linux
   •  SeaBreeze-compatible spectrometer

Installation
git clone https://github.com/your-username/SpectraLabPro.git
cd SpectraLabPro
pip install -r requirements.txt

Running the Application
python SpectraLabPro.py
The GUI opens immediately.

Connecting the Spectrometer
   1  Click Connect Spectrometer
   2  Enter the password:
SpectTek
   3  Upon successful authentication, the device connects and live acquisition starts.
The password is requested only when connecting, not at startup.

Basic Workflow
   1  Scope – Adjust integration time and averaging, check signal level
   2  Capture Dark – Block light and capture background
   3  Capture Reference – Measure blank, then click Set Ref (last)
   4  Select measurement mode:
   ◦  Scope − Dark
   ◦  Absorbance
   ◦  Transmission
   ◦  Reflection
   ◦  Relative Irradiance

Scan Averaging
   •  Multiple consecutive scans are averaged to reduce noise
   •  Status indicator:
   ◦  🔴 Red: averaging in progress
   ◦  🟢 Green: averaging complete
   •  ETA shows remaining acquisition time

Data Export
   •  Save Current → CSV file
   •  Copy All Spectra → paste directly into Excel or Google Sheets

Documentation
   •  Quick Start Guide (PDF)
   •  Developer Documentation
   •  Example screenshots
(See docs/ directory)

License
Intended for research, educational, and laboratory use. Add your preferred license information here.

Acknowledgements
   •  SeaBreeze (Ocean Optics / Ocean Insight)
   •  NumPy, Matplotlib, Pandas

