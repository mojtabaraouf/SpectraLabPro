# SpectraLab Pro

## Professional Spectrometer Control & Analysis GUI

**SpectraLab Pro** is a Python-based graphical application designed for controlling SeaBreeze-compatible spectrometers and performing common optical spectroscopy measurements. It offers a responsive live display, various analysis modes, and a streamlined workflow suitable for laboratory, educational, and field use.

---

## Features
- Live spectrum display (Scope mode)
- Dark subtraction (Scope − Dark)
- Absorbance, Transmission, and Reflection measurements
- Relative Irradiance (spectral shape correction)
- Adjustable integration time and scans-to-average
- Noise reduction via scan averaging with progress indicator
- Wavelength range control and auto-scaling
- Fixed spectral reference lines (Hα, Hβ, Hγ, Hδ, Ca II H & K)
- CSV import/export
- One-click copy to Excel / Google Sheets
- Password-protected spectrometer connection
- Stable, non-blocking GUI (safe for long integrations)

---

## Supported Hardware
- Ocean Optics / Ocean Insight spectrometers
- Any device supported by SeaBreeze  
**Recommended backend:** cseabreeze

---

## Requirements
- Python 3.8+
- Windows, macOS, or Linux
- SeaBreeze-compatible spectrometer

---

## Installation
```bash
git clone https://github.com/mojtabaraouf/SpectraLabPro.git
cd SpectraLabPro
pip install -r requirements.txt
```

---

## Running the Application
```bash
python SpectraLabPro.py
```
The GUI will open immediately.

---

## Connecting the Spectrometer
1. Click **Connect Spectrometer**
2. Enter the password: `email to specttek@gmail.com`
3. Upon successful authentication, the device connects and live acquisition starts.  
   *Note: The password is requested only during connection, not at startup.*

---

## Basic Workflow
1. **Scope** – Adjust integration time and averaging, check signal level
2. **Capture Dark** – Block light and capture background
3. **Capture Reference** – Measure blank, then click **Set Ref** (last)
4. **Select measurement mode:**
   - Scope − Dark
   - Absorbance
   - Transmission
   - Reflection
   - Relative Irradiance
<img width="1433" height="796" alt="6" src="https://github.com/user-attachments/assets/b4e22c3d-d399-49dd-a180-51a63cfb6107" />

---

## Scan Averaging
- Multiple consecutive scans are averaged to reduce noise.
- **Status indicators:**
  - 🔴 Red: averaging in progress
  - 🟢 Green: averaging complete
- ETA displays remaining acquisition time.

---

## Data Export
- **Save Current** → CSV file
- **Copy All Spectra** → paste directly into Excel or Google Sheets

---

## Documentation
- Quick Start Guide (PDF)
- Developer Documentation
- Example screenshots  
*(See docs/ directory)*

---

## License
Intended for research, educational, and laboratory use.  
SpectTek Co. 

---

## Acknowledgements
- SeaBreeze (Ocean Optics / Ocean Insight)
- NumPy, Matplotlib, Pandas
