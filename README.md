# Lateral Line System

## Project Hierarchy

```text
Lateral-Line-System/
├── Differential Sensor/
│   ├── src/
│   │   └── main.cpp              # ESP32 firmware and sensor acquisition
│   ├── Data/                     # Exported pressure CSV files and plots
│   └── capture.py                # Live plotting and data-export program
├── Documentation/
│   ├── Photos/                   # Hardware and experimental setup images
│   ├── Weekly Reporting/         # Weekly project progress reports
│   └── Differential Sensor Documentation.pdf
└── README.md                     # Project overview and instructions
```

## Differential Sensor

### ESP32 Firmware Setup and Programming

#### Communication Outline

1. Program the ESP32 firmware using PlatformIO.
2. The ESP32 reads data from the eight pressure sensors.
3. The ESP32 sends the timestamp and pressure data to the computer through serial communication.
4. The `capture.py` script reads the serial port, processes the data, and generates the requested output.

#### Setup

Use Visual Studio Code with the PlatformIO extension to program the ESP32.

After uploading the firmware, close the PlatformIO Serial Monitor so that `capture.py` can access the serial port.

Set the configuration variables in `capture.py` based on the desired data-collection mode.

Install the required Python libraries:

```bash
pip install pyserial matplotlib numpy
```

Run the script:

```bash
python capture.py
```