<h1 align="center">Polar H10 to LSL Streamer</h1>
A Kivy-based GUI application for streaming Polar H10 sensor data (ECG, HR, RR-interval, and 3-axis accelerometer) to Lab Streaming Layer (LSL) with AEON lab compatibility modifications.

## Overview

This application creates a unified LSL outlet with six channels from Polar H10 data:
- **Channel 0**: ECG (µV) at 130 Hz
- **Channel 1**: Heart Rate (bpm) - event-driven
- **Channel 2**: RR-interval (ms) - event-driven  
- **Channel 3**: Accelerometer X (mG) at 52 Hz
- **Channel 4**: Accelerometer Y (mG) at 52 Hz
- **Channel 5**: Accelerometer Z (mG) at 52 Hz

## Version History

### AEON Lab Modifications
- **PolarGUIv3_AEON_MR&LA.py**: Latest version with both Luis Alarcon's modifications and compatibility fixes for AEON lab's Realtime LSL Dashboard by Md Mijanur Rahman
- **PolarGUIv2_AEON_LA.py**: Modified by Luis Alarcon of AEON lab for internal LSL compatibility

### Original Version
- **Polar GUI_Original.py**: Original version by [markspan](https://github.com/markspan/PolarBand2lsl/) from the [PolarBand2lsl](https://github.com/markspan/PolarBand2lsl/) repository
- 
## Key Features

- **Real-time Data Streaming**: Streams multiple data types simultaneously through a single LSL outlet
- **BLE Connectivity**: Automatically discovers and connects to Polar H10 devices
- **User-friendly GUI**: Simple interface for device scanning and connection management
- **AEON Dashboard Compatibility**: Modified channel labeling and data handling for seamless integration with AEON lab's realtime monitoring dashboard

## Compatibility Fixes

The latest version (v3) includes several important compatibility improvements:

1. **Channel Labeling**: Uses 'label' instead of 'name' for LSL channel metadata to ensure compatibility with AEON's dashboard
2. **NaN Handling**: Replaces NaN values with zeros to prevent dashboard display issues
3. **Consistent Sampling**: Uses ECG rate (130 Hz) as nominal rate for all channels
4. **Default Values**: Initializes with reasonable defaults to maintain data stream continuity

## Requirements

- Python 3.7+
- Kivy
- Bleak (BLE library)
- pylsl (Lab Streaming Layer)
- Polar H10 Heart Rate Sensor

## Installation

```bash
pip install kivy bleak pylsl
