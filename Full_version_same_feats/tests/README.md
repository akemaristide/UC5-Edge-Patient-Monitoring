# 🧪 IoT Gateway Testing Suite

This directory contains comprehensive testing scripts for the patient monitoring system running on IoT gateway hardware with P4 programmable data plane.

## 📋 Test Overview

| Test Type | Script | Duration | Purpose |
|-----------|---------|----------|---------|
| **Latency** | `latency_test.py` | 15-20 min | Measures end-to-end processing latency |
| **Performance** | `performance_test.py` | 25-30 min | Tests system throughput with gateway monitoring |
| **Scalability** | `scalability_test.py` | 30-40 min | Finds maximum concurrent patient capacity |
| **Timeout** | `timeout_test.py` | 15-20 min | Validates partial sensor data handling |

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
pip3 install scapy psutil matplotlib pandas numpy

# Install SSH tools for gateway monitoring
sudo apt-get install sshpass openssh-client

# Ensure network interfaces are up
sudo ip link set enx0c37965f8a0a up
sudo ip link set enx0c37965f8a10 up

# Test connectivity to gateway
ping 192.168.1.12

# Verify SSH access to gateway
ssh ubuntu@192.168.1.12 "echo 'Gateway accessible'"
```

### Gateway Prerequisites
```bash
# On the gateway, ensure these are installed:
pip3 install psutil  # For system monitoring
# BMv2 simple_switch should be running
# Controller should be sending heartbeats every 15 seconds
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
# Clear registers as shown above, then:

sudo python3 latency_test.py
sudo python3 performance_test.py  # Will prompt for gateway SSH password
sudo python3 scalability_test.py
sudo python3 timeout_test.py

# Generate plots from results
python3 plot_results.py [test_type]
```

### Complete Test Suite
```bash
# Run all tests automatically (includes register clearing)
chmod +x run_all_tests.sh
./run_all_tests.sh
```

### SSH Authentication Setup (Recommended)
```bash
# Set up passwordless SSH for automated testing
ssh-keygen -t rsa -b 2048 -f ~/.ssh/gateway_key

# Copy public key to gateway (will ask for password once)
ssh-copy-id -i ~/.ssh/gateway_key.pub ubuntu@192.168.1.12

# Test passwordless login
ssh -i ~/.ssh/gateway_key ubuntu@192.168.1.12 "echo 'SSH key works!'"

# Update performance_test.py to use key instead of password
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

### Scalability Test
- `scalability_results_TIMESTAMP.csv`
  - Fields: num_patients, success_rate_percent, alerts_per_second, active_patients
  - Analysis: Maximum sustainable concurrent patient load

### Timeout Test
- `timeout_results_TIMESTAMP.csv`
  - Fields: scenario, sensors_sent, missing_sensors, response_time_ms, predictions
  - Analysis: System behavior with missing sensor data and heartbeat-triggered timeouts

## 📈 Plotting and Analysis

```bash
# Generate all plots
python3 plot_results.py

# Generate specific plot
python3 plot_results.py latency
python3 plot_results.py performance  
python3 plot_results.py scalability
python3 plot_results.py timeout
python3 plot_results.py summary

# Plots generated:
# - latency_analysis.png (with ML prediction analysis)
# - performance_analysis.png (with gateway monitoring)
# - scalability_analysis.png
# - timeout_analysis.png  
# - combined_summary.png
```

## 🔍 Test Details

### Latency Test
- **Complete Windows**: Sends all 10 sensors, measures immediate P4 inference latency
- **Partial Windows**: Sends 4-8 sensors, measures timeout latency (relies on controller's 15s heartbeat)
- **Expected Results**: 
  - Complete: 5-100ms (direct P4 processing)
  - Partial: 60,000-75,000ms (60s timeout + heartbeat trigger)
- **Metrics**: Average, median, 95th percentile, ML prediction analysis

### Performance Test
- **Load Testing**: Tests 10, 20, 50, 100, 200+ patients/minute
- **Gateway Monitoring**: SSH-based monitoring of CPU, memory, BMv2 process, P4 switch responsiveness
- **Realistic Mix**: 90% complete windows, 10% partial windows
- **Real-time Metrics**: Gateway system load, network utilization, P4 switch health

### Scalability Test
- **Concurrent Patients**: Tests 10, 20, 50, 100, 200+ concurrent patients
- **Realistic Simulation**: Random intervals (30-300s), mixed conditions (normal/sepsis/HF)
- **Success Metrics**: Percentage of patients generating alerts, alerts per second
- **Duration**: 4-5 minutes per patient count level

### Timeout Test
- **Missing Sensor Patterns**: Tests 10 different incomplete data scenarios
- **Heartbeat Dependency**: Relies on controller's 15-second heartbeat schedule
- **Clinical Scenarios**: Missing critical vs non-critical sensors
- **Imputation Validation**: Verifies ML predictions work with partial data

## 🎯 Expected Results

### Typical Performance Benchmarks
- **Complete Window Latency**: 5-100ms (P4 hardware processing)
- **Partial Window Latency**: 60-75 seconds (timeout + heartbeat processing)
- **Throughput**: 50-500 patients/minute depending on gateway hardware
- **Scalability**: 100-1000 concurrent patients depending on configuration
- **Timeout Handling**: 95%+ success rate with partial sensor data

### Gateway Resource Usage
- **CPU Usage**: <80% under normal load, <95% at peak
- **Memory Usage**: <2GB for BMv2 process, <4GB system total
- **P4 Switch Responsiveness**: >95% under normal load
- **Network**: No packet drops on sensor/monitoring interfaces

### ML Prediction Accuracy
- **Sepsis Detection**: Should trigger for high-risk sensor values
- **Heart Failure**: Should detect cardiovascular indicators
- **NEWS2 Scoring**: Should correlate with clinical severity
- **Partial Data**: Predictions should work with 4+ sensors

## 🐛 Troubleshooting

### Common Issues
```bash
# Permission denied for packet capture
sudo python3 test_script.py

# Interface not found - check actual USB-Ethernet adapter names
ip link show  
# Look for enx... interfaces, update scripts accordingly

# BMv2 not responding
ssh ubuntu@192.168.1.12 "pgrep -f simple_switch"
# Check if P4 program is loaded and running

# No alerts received
sudo tcpdump -i enx0c37965f8a0a ether proto 0x1236
# Check if alert packets are being sent from gateway

# SSH connection failed (performance test)
ssh ubuntu@192.168.1.12 "echo test"
# Verify gateway IP, username, and password/key

# Controller heartbeat not working
ssh ubuntu@192.168.1.12 "journalctl -f | grep heartbeat"
# Check if controller is sending heartbeats every 15 seconds
```

### Network Configuration Issues
```bash
# Check interface status
ip addr show enx0c37965f8a0a
ip addr show enx0c37965f8a10

# Check routing (if needed)
ip route show

# Test low-level connectivity
sudo tcpdump -i enx0c37965f8a10 -n
# Send test packet, verify it's received

# Check P4 table entries
ssh ubuntu@192.168.1.12 "simple_switch_CLI --thrift-port 9090"
# In CLI: table_dump <table_name>
```

### Performance Issues
```bash
# Monitor gateway resources during test
ssh ubuntu@192.168.1.12 "htop"

# Check for packet drops
ip -s link show enx0c37965f8a0a

# Monitor P4 switch performance  
ssh ubuntu@192.168.1.12 "sudo iotop -p $(pgrep simple_switch)"

# Check system logs for errors
ssh ubuntu@192.168.1.12 "dmesg | tail -20"
```

## 📝 Customization

### Adjusting Test Parameters

```python
# In latency_test.py
tester = LatencyTester()
# Update interface names if different
tester.sensor_iface = 'your_sensor_interface'
tester.monitor_iface = 'your_monitor_interface'

tester.run_latency_test(
    num_complete=50,     # Number of complete windows
    num_partial=20,      # Number of partial windows  
    spacing_seconds=2    # Time between patients
)

# In performance_test.py
tester = PerformanceTester(
    gateway_ip='192.168.1.12',      # Your gateway IP
    gateway_user='ubuntu',          # SSH username
    ssh_password='your_password'    # Or set up SSH keys
)
tester.run_performance_test(
    target_rates=[10, 20, 50, 100, 200],  # Patients/minute to test
    duration_per_rate=180                  # Seconds per rate
)

# In scalability_test.py
tester.run_scalability_test(
    max_patients=500,        # Maximum patients to test
    step=25,                 # Patient count increment
    duration_per_step=300    # Seconds per patient count
)
```

### Custom Sensor Values
```python
# Modify sensor values for different conditions
normal_values = [370, 98, 80, 120, 16, 0, 0, 1, 45, 1]      # Normal patient
sepsis_values = [390, 94, 110, 90, 22, 1, 1, 2, 65, 1]      # Sepsis indicators  
hf_values = [365, 95, 95, 140, 18, 0, 1, 1, 75, 0]          # Heart failure
```

### Adding Custom Analysis
```python
# In plot_results.py, add custom metrics
def analyze_custom_metrics(df):
    # Add your custom analysis here
    sepsis_rate = (df['sepsis_prediction'] > 0).mean()
    hf_rate = (df['hf_prediction'] > 0).mean()
    high_news2_rate = (df['news2_score'] >= 7).mean()
    
    return {
        'sepsis_detection_rate': sepsis_rate,
        'hf_detection_rate': hf_rate, 
        'high_risk_rate': high_news2_rate
    }
```

## 🔬 Advanced Testing

### Custom Test Scenarios
```python
# Create custom patient scenarios
def create_custom_scenario(patient_id, condition_type):
    if condition_type == 'covid':
        # COVID-19 indicators
        return [385, 92, 105, 130, 24, 1, 1, 2, 55, 1]
    elif condition_type == 'stroke':
        # Stroke indicators  
        return [375, 96, 85, 150, 20, 0, 1, 3, 70, 0]
    # Add more conditions as needed
```

### Integration with External Systems
```python
# Add hooks for external monitoring systems
def send_to_monitoring_system(test_results):
    # Send results to external dashboard/database
    pass

# Add database logging
def log_to_database(test_data):
    # Store results in database for historical analysis
    pass
```

## 📚 References

- **P4 Programming**: [P4.org Documentation](https://p4.org/)
- **BMv2 Switch**: [BMv2 GitHub](https://github.com/p4lang/behavioral-model)
- **Scapy Documentation**: [Scapy Docs](https://scapy.readthedocs.io/)
- **Patient Monitoring Standards**: HL7 FHIR, IEEE 11073

---

**Note**: This testing suite is designed for the UC5 Edge Patient Monitoring system with P4 programmable data plane. Adjust interface names, IP addresses, and credentials according to your specific deployment.