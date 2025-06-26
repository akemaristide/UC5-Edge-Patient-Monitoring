# Edge Patient Monitoring with P4-Programmable IoMT Gateways

## 🎯 Overview
This repository demonstrates **in-network edge computing** for **remote patient monitoring** using **P4-programmable switches**. It showcases how an IoMT gateway can:
- Aggregate patient sensor data,
- Perform **parallel machine learning inference** for multiple conditions (sepsis and heart failure),
- Dispatch unified alerts for abnormal conditions.

The system implements **XGBoost decision trees directly in P4** to enable **low‑latency, intelligent patient monitoring** by offloading data processing and inference from the cloud to the **network edge**.

---

## 🗂️ Repository Structure
```
PatientMonitoring.p4    # Main P4 program with dual sepsis/heart failure inference
topology.json           # Mininet topology configuration (2 hosts + switch)
s1-runtime.json        # Runtime settings for switch s1
Makefile               # Build automation

src/
├─ controller.py                    # Control program for table entries, heartbeat, and alert handling
├─ monitoring.py                    # Listens for alerts on the switch egress port
├─ sensors_simulator.py             # Simulates sensor traffic for 1 patient at a time
└─ sensors_simulator_batch.py       # Simulates sensor traffic for N patients

data/
├─ val_data_normal_vs_sepsis.csv        # Sepsis validation dataset
├─ val_data_sample_many_alerts.csv      # Sample dataset with guaranteed alerts
└─ val_normal_vs_heart_failure.csv      # Heart failure validation dataset

scripts/
└─ run_controller.sh                # Loads table entries and starts the controller

tables/
├─ news2-commands.txt               # NEWS2 scoring table entries
├─ s1-commands-sep.txt              # Sepsis detection table entries
└─ s1-commands-hf.txt               # Heart failure detection table entries
```

---

## 🚀 Getting Started

### Prerequisites
- [P4 Behavioral Model v2](https://github.com/p4lang/behavioral-model) (`bmv2`) 
- `p4c` compiler
- Mininet
- P4 Tutorials utils folder
- Python 3.7+

---

### ⚡️ Build and Run
1. **Compile the P4 program and launch the mininet topology:**
    ```bash
    make
    ```

2. **In another terminal, load the table entries and run the controller:**
    ```bash
    bash ./scripts/run_controller.sh
    ```
    This will:
    - Push table entries for NEWS2 scoring, sepsis detection, and heart failure detection
    - Launch the controller (`controller.py`) to listen for alerts and send heartbeat packets
---

### 👥 Simulate Sensor Traffic
**Run a sensor stream for 1 patient at a time:**
```bash
sudo python3 ./src/sensors_simulator.py
```

**OR run a sensor stream for multiple patients:**
```bash
sudo python3 ./src/sensors_simulator_batch.py -n 10
```
*(Example: simulates data from 10 patients simultaneously)*

### 📡 Monitor Alerts
**Check for alerts triggered by patient data:**
```bash
sudo python3 ./src/monitoring.py
```

The system will output alerts for both sepsis and heart failure conditions as they are detected by the in-network inference pipelines.

---

## 🔬 Technical Details

### Machine Learning Models
- **Sepsis Detection**: XGBoost classifier trained on vital signs to detect early sepsis indicators
- **Heart Failure Detection**: XGBoost classifier for identifying heart failure risk patterns
- **NEWS2 Scoring**: National Early Warning Score 2 implementation for general patient deterioration

### P4 Implementation
- **Parallel Inference**: Both sepsis and heart failure models run simultaneously on each packet
- **Optimized Tables**: XGBoost decision trees converted to P4 match-action tables
- **Unified Output**: Combined alert system for all monitoring conditions
- **Low Latency**: Sub-millisecond inference directly in the data plane

### Data Processing Pipeline
1. **Sensor Data Ingestion**: Vital signs collected from IoMT devices
2. **Feature Extraction**: Raw sensor data processed into ML features  
3. **Parallel Inference**: Simultaneous sepsis and heart failure classification
4. **Alert Generation**: Immediate notifications for high-risk conditions
5. **Controller Integration**: Python control plane for alert handling and table management

---
