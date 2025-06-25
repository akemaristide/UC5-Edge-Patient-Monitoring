#!/usr/bin/env python3
import time
import random
import threading
import pandas as pd
from scapy.all import Ether, sendp, get_if_list, Packet, IntField, BitField, ShortField, bind_layers

# Define Sensor packet structure
class Sensor(Packet):
    name = "Sensor"
    fields_desc = [
        IntField("patient_id", 0),
        IntField("sensor_id", 0),
        BitField("timestamp", 0, 48),
        ShortField("feature_value", 0)
    ]

# Use EtherType 0x1235 for sensor packets
SENSOR_ETHERTYPE = 0x1235
bind_layers(Ether, Sensor, type=SENSOR_ETHERTYPE)

# Validate sending interface
send_iface = 's1-eth2'
if send_iface not in get_if_list():
    print(f"Error: Interface {send_iface} not found. Available: {get_if_list()}")
    exit(1)

# Load data from CSV
data_file = './data/val_data_sample_many_alerts.csv'
#data_file = './data/val_data_normal_vs_sepsis.csv'
try:
    Test_Data = pd.read_csv(data_file)
except Exception as e:
    print(f"Error loading CSV file: {str(e)}")
    exit(1)

# Multiply temperature by 10 (to avoid decimals)
Test_Data['temperature'] = Test_Data['temperature'] * 10
Test_Data = Test_Data.sample(frac=1).reset_index(drop=True)

# Define sensor columns in order
sensor_columns = ['temperature', 'oxygen_saturation', 'pulse_rate', 'systolic_bp', 
                  'respiratory_rate', 'avpu', 'supplemental_oxygen', 'referral_source', 
                  'age', 'sex']

# Function that sends one sensor packet
def send_sensor_packet(patient_id, sensor_id, timestamp_val, feature_value):
    pkt = Ether(dst='00:04:00:00:00:00', type=SENSOR_ETHERTYPE) / Sensor(
        patient_id = patient_id,
        sensor_id  = sensor_id,
        timestamp  = timestamp_val,
        feature_value = feature_value
    )
    # pkt.show()  # Print packet details for debugging
    sendp(pkt, iface=send_iface, verbose=False)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sent sensor packet: patient_id={patient_id}, sensor_id={sensor_id}, value={feature_value}")

# For each row of data (each window)
# In some of windows, some sensors do not send their data as expected
for idx, row in Test_Data.iterrows():
    patient_id = int(row['patient_id'])
    timestamp_val = int(row['timestamp'])
    print(f"\nStarting window {idx+1} for patient {patient_id}")
    window_start = time.time()

    # Decide if this window will have late arrivals for sensors
    late_window = (random.random() < 0.5)  # 50% chance of late arrivals
    if late_window:
        print("This window will have missing values for 1-5 sensors.")
    else:
        print("All sensors will be on time in this window.")

    threads = []
    # For each sensor column, schedule sending a packet with randomized delay.
    for sensor_id, col in enumerate(sensor_columns):
        # Get the feature value as an int.
        # Temperature (sensor id 0) is already multiplied by 10.
        feature_value = int(row[col])
        # Determine delay:
        if sensor_id in [5, 6, 7, 8, 9]:
            # age, sex, avpu, referral, supp oxygen: delay uniformly between 0 and 60 seconds (on time)
            delay = random.uniform(0, 59)
        else:
            # Other sensors: if late_window, skip packet; otherwise between 0 and 60 sec.
            if late_window:
                delay = random.uniform(60, 80)
            else:
                delay = random.uniform(0, 59)
        # Use a thread to sleep and then send the packet
        def send_after_delay(delay=delay, sensor_id=sensor_id, feature_value=feature_value):
            if delay <= 60:
                time.sleep(delay)
                send_sensor_packet(patient_id, sensor_id, timestamp_val, feature_value)
            else:
                print(f"Sensor {sensor_id} for patient {patient_id} did not send a packet.")
        t = threading.Thread(target=send_after_delay)
        t.start()
        threads.append(t)

    # Wait for all sensor packets in this window to be sent (max delay is 90 sec)
    for t in threads:
        t.join()

    # Wait until the full window+quiet time (90 secs) has elapsed before starting next window.
    # Since packet sending took some time already, wait the remainder.
    window_total = 90 # seconds per window
    elapsed = time.time() - window_start
    wait_time = max(0, window_total - elapsed)
    print(f"Window {idx+1} completed. Waiting {wait_time:.2f} seconds before next window...")
    time.sleep(wait_time)

print("All windows processed.")
