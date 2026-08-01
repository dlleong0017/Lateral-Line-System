# Lateral-Line-System

## Project Hierarchy

```text
Differential Sensor/
├─ src/
│   └── main.cpp                 # ESP32 firmware and sensor acquisition
├── Data/                        # Exported pressure CSV files and plots
├── capture.py                   # Live plotting and data-export program
Documentation/
├── Photos/                      # Hardware and experimental setup images
├── Weekly Reporting/            # Weekly project progress reports
├── Differential Sensor Documentation.pdf
README.md                        # Project overview and instructions
```
## Differential Sensor

### ESP32 Firmware Setup and Programming

    Communication Outline
    Program firmware of ESP32 through PlatformIO->
    ESP32 receives data -> 
    ESP32 sends data through serial communication to your computer -> 
    capture.py script scans port and formats data

    Utilize VScode and the PlatformIO Extension to program the ESP32

    After uploading Code then the serial communication between the ESP and your serial port is done
    using the capture.py python script

    Use configuration variables in capture.py script based on desired data collection

    Install the required Python libraries:
    ```bash
    pip install pyserial matplotlib numpy
    ```

    Run the script:

    ```bash
    python capture.py
    ```