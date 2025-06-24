# UC5-Edge-Patient-Monitoring

## 🎯 Overview
This repository demonstrates **in-network edge computing** for **remote patient monitoring** using **P4-programmable switches**. It showcases how an IoMT gateway can:
- Aggregate patient sensor data,
- Perform **on-switch machine learning inference**, and
- Dispatch alerts for abnormal conditions.

The goal is to enable **low‑latency, intelligent patient monitoring** by offloading data processing and inference from the cloud to the **edge**.

---

## 🗂️ Repository Structure
```
patient_monitoring.p4 # Main P4 program
topology.json # Mininet topology configuration (2 hosts + switch)
s1-runtime.json # Runtime settings for switch s1
Makefile # Main Makefile

src/
├─ controller.py # Control program for table entry, heartbeat, and alert handling
├─ monitoring.py # Listens for alerts on the switch egress port
├─ sensors_simulator.py # Simulates sensor traffic for 1 patient at a time
├─ sensors_simulator_batch.py # Simulates sensor traffic for N patients

data/
├─ val_data_normal_vs_sepsis.csv # validation data 
├─ val_data_sample_many_alerts.csv # samller sample of dataset with guaranteed alerts

scripts/
├─ run_controller.sh # Loads table entries and starts the controller

tables/
├─ s1-commands.txt # Table entries for switch s1

```

---

## 🚀 Getting Started

### Prerequisites
- [P4 Behavioral Model v2](https://github.com/p4lang/behavioral-model) (`bmv2`) and `p4c` installed
- P4 Tutorials utils
- Mininet installed
- Python 3

---

### ⚡️ Build and Run
1. Compile the P4 program and launch the mininet topology:
    ```
    make
    ```
3. In another terminal, load the table entries and run the controller:
    ```
    bash ./scripts/run_controller.sh
    ```
    This will:
    - Push entries from `tables/s-commands.txt`
    - Launch the controller (`controller.py`) to listen for alerts and send heartbeat packets.
---

### 👥 Simulate Sensor Traffic
Run a sensor stream for 1 patient at a time:
```
sudo python3 ./src/sensors_simulator.py
```

OR

Run a sensor stream for a specific number of patients:
```
sudo python3 ./src/sensors_simulator_batch.py -n 10
```
*(Example: simulates data from 10 patients.)*

### 📡 Monitor Alerts
Check for alerts triggered by patient data:
```
sudo python3 ./src/monitoring.py
```

---
