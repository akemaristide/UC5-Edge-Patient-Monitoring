# 🧪 IoT Gateway Testing Suite

This directory contains comprehensive testing scripts for the patient monitoring system running on IoT gateway hardware with P4 programmable data plane.

## 📁 Current Test Files

The following test scripts are available in this directory:

### Core Test Scripts
- `accuracy_test_heart_failure.py` - ML model accuracy validation for heart failure detection
- `accuracy_test_sepsis.py` - ML model accuracy validation for sepsis detection  
- `concurrency_test.py` - Tests concurrent patient processing (100-50k patients tested)
- `latency_test_mixed.py` - Measures latency across different patient conditions
- `performance_client.py` - Client component for system throughput testing
- `performance_server.py` - Server component for gateway performance monitoring
- `timeout_test_mixed.py` - Validates timeout behavior with mixed patient conditions
- `twenty4_hour_test.py` - Comprehensive 24-hour system stability test

### Documentation
- `README.md` - This comprehensive testing guide

**Note**: This is a streamlined version of the test suite. Some automated plotting and batch execution scripts have been removed to focus on the core testing functionality. Manual analysis methods are provided instead.

## 📋 Test Overview

| Test Type | Script | Duration | Purpose |
|-----------|---------|----------|---------|
| **Mixed Latency** | `latency_test_mixed.py` | 15-20 min | Measures latency across different patient conditions |
| **Performance** | `performance_client.py` + `performance_server.py` | 25-30 min | Client-server architecture for system throughput testing |
| **Concurrency** | `concurrency_test.py` | 30-40 min | Tests concurrent patient processing (100-50k patients) |
| **Mixed Timeout** | `timeout_test_mixed.py` | 15-20 min | Validates timeout behavior with mixed patient conditions |
| **Accuracy** | `accuracy_test_sepsis.py` + `accuracy_test_heart_failure.py` | 10-15 min each | ML model accuracy validation for sepsis and heart failure |
| **24-Hour Stress** | `twenty4_hour_test.py` | 24 hours | Comprehensive long-term system stability test |

## 🔧 Prerequisites

### Hardware Setup
```
[Monitoring Host] (Windows/Linux)
    ├── enx0c37965f8a0a ←→ Gateway Port 1 (monitoring/alert port)
    └── enx0c37965f8a10 ←→ Gateway Port 2 (sensor port)
            ↓
    [IoT Gateway] (192.168.1.12)
    └── BMv2 P4 Switch + Controller
```

### Software Requirements
```bash
# Install Python dependencies
pip3 install scapy psutil matplotlib pandas numpy seaborn scikit-learn

# Install SSH tools for gateway monitoring (for performance tests)
sudo apt-get install sshpass openssh-client

# Ensure network interfaces are up
sudo ip link set enx0c37965f8a0a up
sudo ip link set enx0c37965f8a10 up

# Test connectivity to gateway
ping 192.168.1.12

# Verify SSH access to gateway (for performance tests)
ssh ubuntu@192.168.1.12 "echo 'Gateway accessible'"
```

### Gateway Prerequisites
```bash
# On the gateway, ensure these are installed:
pip3 install psutil  # For system monitoring
# BMv2 simple_switch should be running
# Controller should be sending heartbeats every 60 seconds
```

## 🔧 Packet Structure

### Sensor Packets (EtherType 0x1235)
```
Ethernet Header + Sensor Header:
├── patient_id (32-bit)
├── sensor_id (32-bit)  
├── timestamp (48-bit)
└── feature_value (16-bit)
```

### Alert Packets (EtherType 0x1236)
```
Ethernet Header + Alert Header:
├── patient_id (32-bit)
├── timestamp (48-bit)
├── sepPrediction (32-bit)
├── news2Score (8-bit)
├── news2Alert (8-bit)
└── hfPrediction (32-bit)
```

## 🚀 Running Tests

### ⚠️ **IMPORTANT: Clear P4 Registers Between Tests**
```bash
# In the CLI, clear all registers as such:
register_reset reg_temperature

# Or restart the P4 switch completely:
```

**Why this is critical:**
- Previous test patient data may remain in registers
- Can cause false positives/negatives in subsequent tests
- Affects latency measurements and prediction accuracy
- Essential for reliable, repeatable test results

### Individual Tests
```bash
# Mixed Latency Test - complete vs partial windows across conditions
sudo python3 latency_test_mixed.py

# Performance Test - requires gateway monitoring
# First, start the performance server on the gateway:
# ssh ubuntu@192.168.1.12 "cd /path/to/tests && python3 performance_server.py"
# Then run the client:
sudo python3 performance_client.py

# Concurrency Test - 100 to 10,000 concurrent patients  
sudo python3 concurrency_test.py

# Mixed Timeout Test - timeout behavior across patient conditions
sudo python3 timeout_test_mixed.py

# Accuracy Tests - ML model validation
sudo python3 accuracy_test_sepsis.py
sudo python3 accuracy_test_heart_failure.py

# 24-Hour Stress Test - comprehensive system validation
sudo python3 twenty4_hour_test.py
```


## 📊 Output Files

Each test generates CSV files with timestamps for analysis:

### Latency Test
- `latency_results_TIMESTAMP.csv`
  - Fields: patient_id, window_type, latency_ms, timestamp, sepsis_prediction, news2_score, hf_prediction
  - Analysis: Distribution of processing times for complete vs partial windows with ML predictions

### Performance Test  
- `performance_summary_TIMESTAMP.csv` - Overall results by rate with gateway metrics
- `performance_rate_N_TIMESTAMP.csv` - Detailed data for each rate tested
  - Analysis: Throughput limits, gateway CPU/memory usage, BMv2 process monitoring

### Concurrency Test
- `concurrency_results_TIMESTAMP.csv`
  - Fields: num_patients, success_rate_percent, alerts_per_second, active_patients
  - Analysis: Maximum sustainable concurrent patient load

### Timeout Test
- `timeout_results_TIMESTAMP.csv`
  - Fields: scenario, sensors_sent, missing_sensors, response_time_ms, predictions
  - Analysis: System behavior with missing sensor data and heartbeat-triggered timeouts

### Accuracy Tests
- `accuracy_sepsis_results_TIMESTAMP.csv`
  - Fields: patient_id, condition, missing_sensors, predicted_sepsis, expected_sepsis, correct
  - Analysis: ML model accuracy for sepsis detection with missing sensor simulation

- `accuracy_hf_results_TIMESTAMP.csv` 
  - Fields: patient_id, condition, missing_sensors, predicted_hf, expected_hf, correct
  - Analysis: ML model accuracy for heart failure detection with missing sensor simulation

### 24-Hour Test
- `twenty4_hour_results_TIMESTAMP.csv`
  - Fields: hour, active_patients, alerts_generated, cpu_usage, memory_usage, response_time
  - Analysis: Long-term system stability and performance trends


## 🔍 Test Details

### Mixed Latency Test
- **Complete Windows**: Sends all 10 sensors, measures immediate P4 inference latency
- **Partial Windows**: Sends 4-8 sensors, measures timeout latency (relies on controller's 60s heartbeat)
- **Mixed Conditions**: Tests normal, sepsis, and heart failure patient scenarios
- **Expected Results**: 
  - Complete: 5-100ms (direct P4 processing)
  - Partial: 60,000-75,000ms (60s timeout + heartbeat trigger)
- **Metrics**: Average, median, 95th percentile, ML prediction analysis

### Performance Test
- **Load Testing**: Tests 10, 20, 50, 100, 200+ patients/minute
- **Gateway Monitoring**: SSH-based monitoring of CPU, memory, BMv2 process, P4 switch responsiveness
- **Realistic Mix**: 90% complete windows, 10% partial windows
- **Real-time Metrics**: Gateway system load, network utilization, P4 switch health

### Concurrency Test
- **Concurrent Patients**: Tests 100 to 10,000 concurrent patients in steps of 500
- **Realistic Simulation**: Random intervals (30-300s), mixed conditions (normal/sepsis/HF)
- **Success Metrics**: Percentage of patients generating alerts, alerts per second
- **Duration**: 4-5 minutes per patient count level
- **Safety**: Uses safe patient ID management to avoid collisions

### Timeout Test
- **Missing Sensor Patterns**: Tests 10 different incomplete data scenarios
- **Heartbeat Dependency**: Relies on controller's 60-second heartbeat schedule
- **Clinical Scenarios**: Missing critical vs non-critical sensors
- **Imputation Validation**: Verifies ML predictions work with partial data

### Accuracy Tests
- **Sepsis Detection**: Tests ML model accuracy with normal vs sepsis patient data
- **Heart Failure Detection**: Tests ML model accuracy with normal vs heart failure data
- **Missing Sensor Simulation**: Randomly removes 1-3 sensors to test robustness
- **Alert Validation**: Compares P4 predictions with expected clinical outcomes
- **Statistical Analysis**: Calculates accuracy, precision, recall, and F1-score metrics

### 24-Hour Stress Test
- **Hospital Simulation**: Realistic patient admission/discharge patterns
- **Shift Scheduling**: Simulates day/night patient load variations
- **System Monitoring**: Continuous tracking of gateway performance metrics
- **Long-term Stability**: Tests for memory leaks, performance degradation


## 📚 References

- **P4 Programming**: [P4.org Documentation](https://p4.org/)
- **BMv2 Switch**: [BMv2 GitHub](https://github.com/p4lang/behavioral-model)
- **Scapy Documentation**: [Scapy Docs](https://scapy.readthedocs.io/)

---

**Note**: This testing suite is designed for the UC5 Edge Patient Monitoring system with P4 programmable data plane. Adjust interface names, IP addresses, and credentials according to your specific deployment.