# SpectraLab Dual-Range Volatile Tracer Suite

**SpectraLab Dual-Range Volatile Tracer Suite** is a Python/Tkinter GUI for connecting one or two SeaBreeze-compatible spectrometers and visualizing spectral signatures of **H₂O** and **CO₂** over a combined **UV/VIS + SWIR wavelength range**.

The software is designed for:

- UV/VIS spectrometers, for example **200–900 nm**
- SWIR spectrometers, for example **900–2500 nm**
- simultaneous display of both spectrometers
- external spectrum CSV import
- dark-frame subtraction
- reference-based transmission, reflection, and absorbance modes
- normalized spectrum comparison
- manual X/Y axis range control
- CO₂ and H₂O tracer-line and band visualization
- local feature measurement and export

---

## Copyright

Copyright © 2026 **SpectTek Co.**  
All rights reserved.

This software, GUI design, analysis workflow, and spectral tracer tools belong to **SpectTek Co.** Unauthorized copying, redistribution, modification, reverse engineering, or commercial use without written permission is prohibited.

SpectTek Co. profile: <https://www.linkedin.com/in/specttek/>

---

## Scientific Purpose

The code is intended to help users detect, inspect, and measure spectral features associated with **water vapor / water-related chemistry** and **carbon dioxide / carbon-bearing gas chemistry**.

The software separates the diagnostics into two main wavelength regimes:

### 1. UV/VIS range: 200–900 nm

In this range, H₂O and CO₂ are mostly detected through **indirect tracers**, because their strongest direct molecular bands are usually outside the optical range.

Important UV/VIS tracers included in the GUI:

| Species | Tracer | Approximate wavelength |
|---|---|---:|
| H₂O | OH A-X band | 308–309 nm |
| H₂O | OH⁺ band | ~335 nm |
| H₂O | weak UV absorption | ~363 nm |
| H₂O / CO₂ | [O I] green line | 557.7 nm |
| H₂O / CO₂ | [O I] red lines | 630.0, 636.4 nm |
| CO₂ | CO Cameron bands | 200–280 nm |
| CO₂ | CO₂⁺ UV doublet | 288.3, 289.6 nm |
| CO₂ | CO₂⁺ FDB band | 310–340 nm |
| CO₂ | C I line | 247.9 nm |
| CO₂ | C I line | 872.7 nm |

### 2. SWIR range: 900–2500 nm

In the SWIR range, H₂O and CO₂ have stronger **direct absorption bands**, making this region especially useful for gas detection.

Important SWIR tracers included in the GUI:

| Species | Band | Approximate wavelength |
|---|---|---:|
| H₂O | water absorption | 940 nm |
| H₂O | water absorption | 970 nm |
| H₂O | water absorption | 1130 nm |
| H₂O | water absorption | 1370–1450 nm |
| H₂O | water absorption | 1870–1950 nm |
| CO₂ | CO₂ absorption | 1437 nm |
| CO₂ | CO₂ absorption | 1570–1600 nm |
| CO₂ | CO₂ absorption | 1955–2060 nm |
| CO₂ | CO₂ absorption | ~2350 nm |

---

## Main Features

### Dual Spectrometer Support

The GUI supports two spectrometer channels:

- **UV/VIS channel:** typically 200–900 nm
- **SWIR channel:** typically 900–2500 nm

Each channel has its own:

- device index
- connection button
- dark frame
- reference spectrum
- live spectrum
- capture button

Both spectra can be displayed at the same time.

---

### Live Spectrum Display

The main plot displays:

- live UV/VIS spectrum
- live SWIR spectrum
- imported spectra
- captured spectra
- tracer-line overlays
- shaded diagnostic bands

The user can enable or disable:

- UV/VIS live spectrum
- SWIR live spectrum
- stored/imported spectra
- tracer lines
- tracer-band shading

---

### Manual Axis Control

The GUI includes manual controls for:

- X-axis wavelength range
- Y-axis intensity range

This is important because some processing modes, such as dark subtraction or residual analysis, may produce **negative values**.

Example Y ranges:

```text
-0.2 to 1.0
-100 to 5000
0 to 1.2
```

Quick wavelength buttons are included for:

- 200–900 nm
- 900–2500 nm
- full 200–2500 nm
- H₂O SWIR region
- CO₂ SWIR region

---

## Processing Modes

The GUI provides several processing modes.

### Scope

Raw detector counts.

Use this mode to check signal level, saturation, lamp alignment, and basic spectrometer response.

### Scope - Dark

Dark-subtracted spectrum:

```text
I_corrected = I_sample - I_dark
```

This mode preserves negative values, which is useful for diagnostics and baseline correction.

### Absorbance

Absorbance is calculated as:

```text
A = -log10((I - Dark) / (I0 - Dark))
```

where:

- `I` is the sample spectrum
- `I0` is the reference spectrum
- `Dark` is the dark frame

This mode is recommended for gas absorption measurements.

### Transmission

Transmission is calculated as:

```text
T = 100 × (I - Dark) / (I0 - Dark)
```

The result is shown as percent transmission.

### Reflection

Reflection mode uses the same reference-ratio logic as transmission but is intended for reflected-light measurements using a reflection standard.

### Relative Irradiance

Relative irradiance is calculated by dividing counts by integration time:

```text
Relative irradiance = counts / integration_time_ms
```

This gives relative spectral shape, not absolute calibrated irradiance unless an irradiance calibration file is applied externally.

### Normalized

The normalized mode divides the processed spectrum by its maximum absolute value:

```text
I_norm = I / max(|I|)
```

This is useful for comparing spectral shapes from different channels or exposures.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

#### Windows

```bash
venv\Scripts\activate
```

#### macOS / Linux

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install numpy pandas matplotlib seabreeze
```

For Ocean Optics / SeaBreeze devices, you may need:

```bash
pip install seabreeze[cse]
```

If the C backend does not work on your system, the code tries to fall back to `pyseabreeze`.

---

## Required Python Packages

The code uses:

```text
numpy
pandas
matplotlib
tkinter
seabreeze
threading
queue
platform
webbrowser
```

`tkinter` is included with most Python installations, but on some Linux systems it may need to be installed separately.

For Ubuntu/Debian:

```bash
sudo apt-get install python3-tk
```

---

## Running the GUI

Run:

```bash
python spectrolab_dual_range.py
```

or replace the filename with the actual Python file name in your repository.

---

## Spectrometer Setup

### Step 1: Connect devices

Connect one or two SeaBreeze-compatible spectrometers to the computer.

Typical configuration:

| Channel | Device index | Wavelength range |
|---|---:|---:|
| UV/VIS | 0 | 200–900 nm |
| SWIR | 1 | 900–2500 nm |

The device index may change depending on USB order.

Click:

```text
List Devices
```

The software will show all available spectrometers with their index, model, and serial number.

### Step 2: Assign device indices

Enter the correct index for each channel:

```text
UV/VIS index: 0
SWIR index: 1
```

### Step 3: Connect channels

Click either:

```text
Connect
```

for each channel, or:

```text
Connect Both
```

The software asks for a password before connecting.

Default password:

```text
email to specttec@gmail.com
```

---

<<<<<<< HEAD
## Measurement Workflow

### 1. Set exposure

Enter:

- integration time in milliseconds
- number of scans to average

Then click:

```text
Apply Exposure
```

Longer integration time increases signal but may saturate the detector.

### 2. Capture dark frame

Cover the detector or block the light path.

Click:

```text
Dark UV
```

or:

```text
Dark SWIR
```

Dark subtraction is recommended for all serious measurements.

### 3. Capture reference spectrum

Measure the reference light path without the absorbing gas/sample.

Click:

```text
Cap UV
```

or:

```text
Cap SWIR
```

Then click:

```text
Ref UV
```

or:

```text
Ref SWIR
```

This stores the last captured spectrum as the reference.

### 4. Measure sample spectrum

Place the gas/sample in the optical path and capture the spectrum again.

Use one of the following modes:

- Scope - Dark
- Absorbance
- Transmission
- Reflection
- Normalized

For gas absorption work, **Absorbance** is usually preferred.
=======
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
>>>>>>> ad847ebd71969937432d3ec8991d01dfcf18b030

---

## Importing External Spectrum CSV Files

The GUI can import external spectrum files from the hard drive.

Click:

```text
Import Spectrum CSV
```

The CSV file should contain either:

```text
wavelength_nm,intensity
```

or two columns where:

- column 1 = wavelength in nm
- column 2 = intensity

Example:

```csv
wavelength_nm,intensity
900,0.98
901,0.97
902,0.96
```

Imported spectra are automatically assigned to:

- UV/VIS if maximum wavelength is ≤ 900 nm
- SWIR if maximum wavelength is > 900 nm

---

## Exporting Data

### Save last spectrum

Click:

```text
Save Last Spectrum
```

The output CSV contains:

```text
wavelength_nm,intensity
```

### Export measurements

After measuring tracer features, click:

```text
Export Measurements
```

The output file contains:

- spectrum label
- species
- tracer name
- central wavelength
- feature type
- peak strength
- integrated strength
- equivalent width
- SNR
- detection note

---

## Tracer Measurement Method

The code measures each selected feature by:

1. selecting a feature window around the tracer wavelength
2. selecting left and right continuum regions
3. fitting a local linear continuum
4. subtracting the continuum
5. calculating residual feature strength
6. estimating peak/trough signal
7. estimating integrated band strength
8. estimating equivalent width
9. estimating SNR from continuum residual noise

For absorption bands, the code treats negative residuals as absorption strength.

For emission lines, the code measures positive residual peaks.

---

## Tabs in the GUI

### Main Tab

Contains:

- spectrometer connection controls
- device index selection
- dark capture
- spectrum capture
- reference setting
- exposure settings
- processing mode
- live display options
- status box

### Tracers Tab

Contains:

- species selection
- tracer selection
- zoom-to-feature button
- measure selected feature button
- measure all visible features button
- export measurements button

### Files Tab

Contains:

- import spectrum CSV
- save last spectrum
- list of captured/imported spectra
- remove selected spectrum
- change spectrum color
- clear all spectra

### Diagnostics Tab

Contains a summary of the diagnostic H₂O and CO₂ lines/bands used in the software.

---

## Important Notes About Interpretation

A single optical line is not always unique to one molecule.

For example:

- [O I] 630.0 nm can be produced by H₂O, CO₂, or CO photochemistry.
- CO Cameron bands may be related to CO or CO₂.
- OH 308–309 nm is a strong H₂O tracer but still depends on photochemistry.

For stronger molecular identification, use:

- multiple bands
- UV/VIS + SWIR comparison
- line ratios
- dark/reference correction
- wavelength calibration
- repeated measurements
- laboratory or atmospheric calibration standards

---

## Troubleshooting

### No spectrometer found

Check:

- USB cable
- spectrometer power
- SeaBreeze installation
- device permissions
- correct backend

Try:

```bash
pip install seabreeze[cse]
```

### Tkinter is missing

On Linux:

```bash
sudo apt-get install python3-tk
```

### Wrong device assigned to UV/VIS or SWIR

Click:

```text
List Devices
```

Then update the device index boxes.

### Plot looks flat

Try:

- increasing integration time
- checking light source
- disabling normalization
- adjusting manual Y range
- verifying the selected wavelength range

### Negative values appear

This is normal in:

- dark-subtracted mode
- absorbance mode
- residual analysis
- baseline-subtracted measurements

Use the manual Y range to view them properly.

### CSV import fails

Make sure the file contains numeric data and either:

```text
wavelength_nm,intensity
```

or two numeric columns.

---

## Recommended Repository Structure

```text
SpectraLab-Dual-Range/
│
├── README.md
├── spectrolab_dual_range.py
├── requirements.txt
├── spectra_data/
│   └── example_spectrum.csv
├── docs/
│   └── tracer_table.md
└── examples/
    ├── uvvis_example.csv
    └── swir_example.csv
```

---

## Example `requirements.txt`

```text
numpy
pandas
matplotlib
seabreeze
```

Optional:

```text
seabreeze[cse]
```

---

## Future Improvements

Planned or possible extensions:

- wavelength calibration module
- Gaussian/Lorentzian line fitting
- multi-band abundance estimation
- HITRAN-based model comparison
- automatic baseline correction
- atmospheric correction for SWIR
- absolute irradiance calibration
- simultaneous saving of UV/VIS and SWIR spectra
- real-time gas concentration estimation
- support for non-SeaBreeze spectrometers

---

## Citation / Acknowledgment

If this software is used in research, reports, or demonstrations, please acknowledge:

```text
SpectraLab Dual-Range Volatile Tracer Suite, SpectTek Co., 2026.
```

---

## Contact

**SpectTek Co.**  
LinkedIn: <https://www.linkedin.com/in/specttek/>

