#!/usr/bin/env python3

import time
import random
import threading
import pandas as pd
import argparse
from scapy.all import Ether, sendp, get_if_list, Packet, IntField, BitField, ShortField, bind_layers

# Add argument parser
parser = argparse.ArgumentParser(description='Sensor simulator for sepsis monitoring')
parser.add_argument('-n', '--num_patients', type=int, default=1,
                    help='Number of patients to simulate simultaneously (default: 1)')
args = parser.parse_args()

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

# Load and merge datasets
sepsis_file = './data/val_data_normal_vs_sepsis.csv'
heart_failure_file = './data/val_normal_vs_heart_failure.csv'

try:
    # Load sepsis dataset (contains normal rows with condition=0 and sepsis rows with condition=1)
    sepsis_data = pd.read_csv(sepsis_file)
    
    # Load heart failure dataset 
    heart_failure_data = pd.read_csv(heart_failure_file)
    
    # Filter heart failure dataset to only include heart failure cases (condition=2)
    heart_failure_cases = heart_failure_data[heart_failure_data['condition'] == 2]
    
    # Merge sepsis data (normal + sepsis) with heart failure cases only
    Test_Data = pd.concat([sepsis_data, heart_failure_cases], ignore_index=True)
    
except Exception as e:
    print(f"Error loading CSV files: {str(e)}")
    exit(1)

# Multiply temperature by 10 (to avoid decimals)
Test_Data['temperature'] = Test_Data['temperature'] * 10

# Shuffle the combined dataset
Test_Data = Test_Data.sample(frac=1).reset_index(drop=True)

# Define sensor columns in order
sensor_columns = ['temperature', 'oxygen_saturation', 'pulse_rate', 'systolic_bp', 
                 'respiratory_rate', 'avpu', 'supplemental_oxygen', 'referral_source', 
                 'age', 'sex']

def send_sensor_packet(patient_id, sensor_id, timestamp_val, feature_value):
    pkt = Ether(dst='00:04:00:00:00:00', type=SENSOR_ETHERTYPE) / Sensor(
        patient_id=patient_id,
        sensor_id=sensor_id,
        timestamp=timestamp_val,
        feature_value=feature_value
    )
    sendp(pkt, iface=send_iface, verbose=False)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sent sensor packet: patient_id={patient_id}, sensor_id={sensor_id}, value={feature_value}")

def process_patient_window(patient_id, row, window_idx):
    timestamp_val = int(row['timestamp'])
    print(f"\nStarting window {window_idx+1} for patient {patient_id}")
    window_start = time.time()
    # Decide if this window will have late arrivals
    late_window = (random.random() < 0.4)
    if late_window:
        print(f"Patient {patient_id}: This window will have missing values for some sensors.")
    else:
        print(f"Patient {patient_id}: All sensors will be on time in this window.")

    threads = []
    for sensor_id, col in enumerate(sensor_columns):
        feature_value = int(row[col])
        
        # Determine delay based on sensor type and window status
        if sensor_id in [5, 6, 7, 8, 9]:
            delay = random.uniform(0, 59)
        else:
            delay = random.uniform(75, 85) if late_window else random.uniform(0, 59)

        def send_after_delay(delay=delay, sensor_id=sensor_id, feature_value=feature_value):
            if delay <= 60:
                time.sleep(delay)
                send_sensor_packet(patient_id, sensor_id, timestamp_val, feature_value)
            else:
                print(f"Patient {patient_id}: Sensor {sensor_id} failed to send a value on time.")        
        t = threading.Thread(target=send_after_delay)
        t.start()
        threads.append(t)

    # Wait for all sensor packets in this window
    for t in threads:
        t.join()

    # Wait remainder of window time
    window_total = 90  # seconds per window
    elapsed = time.time() - window_start
    wait_time = max(0, window_total - elapsed)
    print(f"Window {window_idx+1} completed. Waiting {wait_time:.2f} seconds before next window...")
    time.sleep(wait_time)

def process_patient(patient_data, patient_id):
    for idx, row in patient_data.iterrows():
        process_patient_window(patient_id, row, idx)

def main():
    # Group the test data by patient_id
    patient_groups = Test_Data.groupby('patient_id')
    patient_ids = list(patient_groups.groups.keys())
    num_patients = min(args.num_patients, len(patient_ids))

    print(f"Starting simulation with {num_patients} simultaneous patients")

    # Process patients in batches of size num_patients
    while patient_ids:
        current_batch = patient_ids[:num_patients]
        patient_ids = patient_ids[num_patients:]
        
        print(f"\nStarting new batch with patients: {current_batch}")
        threads = []

        # Create a thread for each patient in the batch
        for patient_id in current_batch:
            patient_data = patient_groups.get_group(patient_id).reset_index(drop=True)
            thread = threading.Thread(
                target=process_patient,
                args=(patient_data, patient_id)
            )
            thread.start()
            threads.append(thread)

        # Wait for all patients in this batch to complete
        for t in threads:
            t.join()

    print("All patients processed.")

if __name__ == "__main__":
    main()