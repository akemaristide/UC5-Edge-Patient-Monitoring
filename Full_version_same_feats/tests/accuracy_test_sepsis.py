#!/usr/bin/env python3
# filepath: Full_version_same_feats/src/accuracy_test_sepsis.py

import time
import random
import threading
import pandas as pd
import numpy as np
import struct
from collections import defaultdict
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from scapy.all import Ether, sendp, get_if_list, Packet, IntField, BitField, ShortField, ByteField, bind_layers, sniff

class Sensor(Packet):
    name = "Sensor"
    fields_desc = [
        IntField("patient_id", 0),
        IntField("sensor_id", 0),
        BitField("timestamp", 0, 48),
        ShortField("feature_value", 0)
    ]

class Alert(Packet):
    name = "Alert"
    fields_desc = [
        IntField("patient_id", 0),
        BitField("timestamp", 0, 48),
        IntField("sepPrediction", 0),
        ByteField("news2Score", 0),
        ByteField("news2Alert", 0),
        IntField("hfPrediction", 0)
    ]

SENSOR_ETHERTYPE = 0x1235
ALERT_ETHERTYPE = 0x1236
bind_layers(Ether, Sensor, type=SENSOR_ETHERTYPE)
bind_layers(Ether, Alert, type=ALERT_ETHERTYPE)

class AccuracyTester:
    def __init__(self, data_file, send_interface='enx0c37965f8a10', receive_interface='enx0c37965f8a0a'):
        self.data_file = data_file
        self.send_iface = send_interface
        self.receive_iface = receive_interface
        self.results = {}
        self.expected_results = {}
        self.received_alerts = defaultdict(list)
        self.test_complete = False
        
        # Load and prepare data
        self.load_data()
        
    def load_data(self):
        """Load test data and prepare expected results"""
        try:
            self.test_data = pd.read_csv(self.data_file)
            print(f"Loaded {len(self.test_data)} sepsis test samples")
            
            # Check available conditions
            unique_conditions = self.test_data['condition'].unique()
            print(f"Available conditions in dataset: {unique_conditions}")
            
            # Filter for sepsis (condition=1) and normal (condition=0) cases
            self.test_data = self.test_data[self.test_data['condition'].isin([0, 1])]
            print(f"Filtered to {len(self.test_data)} samples (normal + sepsis)")
            
            # Multiply temperature by 10 for P4 compatibility
            self.test_data['temperature'] = self.test_data['temperature'] * 10
            
            # Store expected results (ground truth)
            for idx, row in self.test_data.iterrows():
                patient_id = int(row['patient_id'])
                window_id = f"{patient_id}_{idx}"
                condition = int(row['condition'])
                
                self.expected_results[window_id] = {
                    'sepsis': 1 if condition == 1 else 0,
                    'patient_id': patient_id,
                    'window_idx': idx,
                    'original_condition': condition
                }
                
        except Exception as e:
            print(f"Error loading sepsis data: {e}")
            exit(1)
    
    def send_sensor_packet(self, patient_id, sensor_id, timestamp_val, feature_value):
        """Send a single sensor packet"""
        try:
            pkt = Ether(dst='00:04:00:00:00:00', type=SENSOR_ETHERTYPE) / Sensor(
                patient_id=patient_id,
                sensor_id=sensor_id,
                timestamp=timestamp_val,
                feature_value=feature_value
            )
            sendp(pkt, iface=self.send_iface, verbose=False)
        except Exception as e:
            print(f"Error sending sensor packet: {e}")
    
    def send_heartbeat(self, patient_id, timestamp_val):
        """Send heartbeat packet to trigger inference"""
        try:
            pkt = Ether(dst='00:04:00:00:00:00', type=SENSOR_ETHERTYPE) / Sensor(
                patient_id=patient_id,
                sensor_id=999,  # Heartbeat sensor ID
                timestamp=timestamp_val,
                feature_value=0
            )
            sendp(pkt, iface=self.send_iface, verbose=False)
        except Exception as e:
            print(f"Error sending heartbeat packet: {e}")
    
    def process_patient_window_fast(self, patient_id, row, window_idx):
        """Process a single patient window with fast sending and missing sensors"""
        sensor_columns = ['temperature', 'oxygen_saturation', 'pulse_rate', 'systolic_bp', 
                         'respiratory_rate', 'avpu', 'supplemental_oxygen', 'referral_source', 
                         'age', 'sex']
        
        timestamp_val = int(row['timestamp'])
        window_id = f"{patient_id}_{window_idx}"
        
        # Determine which sensors to skip (10% chance of missing sensors)
        sensors_to_skip = set()
        if random.random() < 0.1:  # 10% chance of missing sensors
            num_to_skip = random.randint(1, 3)
            available_sensors = list(range(len(sensor_columns)))
            sensors_to_skip = set(random.sample(available_sensors, min(num_to_skip, len(available_sensors))))
            print(f"Patient {patient_id}: Skipping sensors {sensors_to_skip}")
        
        # Send sensor packets as fast as possible
        sensors_sent = 0
        for sensor_id, col in enumerate(sensor_columns):
            if sensor_id in sensors_to_skip:
                continue
                
            if col in row and pd.notna(row[col]):
                feature_value = int(row[col])
                self.send_sensor_packet(patient_id, sensor_id, timestamp_val, feature_value)
                sensors_sent += 1
                # Small delay to avoid overwhelming the system
                time.sleep(0.001)
        
        # Send heartbeat after a short delay if we have incomplete data
        if sensors_sent < len(sensor_columns):
            time.sleep(0.01)
            self.send_heartbeat(patient_id, timestamp_val)
        
        print(f"Patient {patient_id}: Sent {sensors_sent}/{len(sensor_columns)} sensors")
        return window_id
    
    def packet_handler(self, packet):
        """Handle received alert packets with robust parsing"""
        if not self.test_complete and packet.haslayer(Ether) and packet[Ether].type == ALERT_ETHERTYPE:
            try:
                # Parse the Alert header properly
                if packet.haslayer(Alert):
                    alert = packet[Alert]
                    patient_id = alert.patient_id
                    sep_prediction = alert.sepPrediction
                    hf_prediction = alert.hfPrediction
                    news2_score = alert.news2Score
                    news2_alert = alert.news2Alert
                else:
                    # Fallback: manual parsing if Scapy parsing fails
                    payload_bytes = bytes(packet.payload)
                    if len(payload_bytes) >= 20:  # Alert header size
                        patient_id = struct.unpack('!I', payload_bytes[0:4])[0]
                        # Skip timestamp (6 bytes)
                        sep_prediction = struct.unpack('!I', payload_bytes[10:14])[0]
                        news2_score = payload_bytes[14]
                        news2_alert = payload_bytes[15]
                        hf_prediction = struct.unpack('!I', payload_bytes[16:20])[0]
                    else:
                        return
                
                if patient_id > 0:
                    self.received_alerts[patient_id].append({
                        'timestamp': time.time(),
                        'sepsis_prediction': sep_prediction,
                        'heart_failure_prediction': hf_prediction,
                        'news2_score': news2_score,
                        'news2_alert': news2_alert
                    })
                    
                    print(f"📨 Alert - Patient {patient_id}: Sepsis={sep_prediction}, HF={hf_prediction}, NEWS2={news2_score}")
                    
            except Exception as e:
                print(f"Error processing sepsis alert: {e}")
    
    def start_packet_capture(self):
        """Start capturing alert packets in a separate thread"""
        def capture():
            try:
                print(f"Starting packet capture on {self.receive_iface}...")
                sniff(iface=self.receive_iface, 
                      filter=f"ether proto {ALERT_ETHERTYPE}", 
                      prn=self.packet_handler,
                      stop_filter=lambda x: self.test_complete)
            except Exception as e:
                print(f"Packet capture error: {e}")
        
        capture_thread = threading.Thread(target=capture)
        capture_thread.daemon = True
        capture_thread.start()
        return capture_thread
    
    def run_test(self):
        """Run the complete sepsis accuracy test"""
        print("=" * 60)
        print("SEPSIS ACCURACY TEST")
        print("=" * 60)
        print(f"Data file: {self.data_file}")
        print(f"Send interface: {self.send_iface}")
        print(f"Receive interface: {self.receive_iface}")
        print(f"Total samples: {len(self.test_data)}")
        
        # Start packet capture
        capture_thread = self.start_packet_capture()
        time.sleep(2)  # Give capture time to start
        
        processed_windows = []
        
        # Process all test data
        print(f"\nProcessing {len(self.test_data)} patient windows...")
        for idx, row in self.test_data.iterrows():
            patient_id = int(row['patient_id'])
            window_id = self.process_patient_window_fast(patient_id, row, idx)
            processed_windows.append(window_id)
            
            # Brief pause between windows
            time.sleep(0.1)
            
            if (idx + 1) % 50 == 0:
                print(f"Progress: {idx + 1}/{len(self.test_data)} windows processed...")
        
        # Wait for all responses
        print(f"\nWaiting for all sepsis predictions...")
        max_wait_time = max(30, len(self.test_data) * 0.1)  # At least 30 seconds
        
        for remaining in range(int(max_wait_time), 0, -5):
            time.sleep(5)
            total_alerts = sum(len(alerts) for alerts in self.received_alerts.values())
            print(f"  {remaining}s remaining... Received {total_alerts} alerts from {len(self.received_alerts)} patients")
        
        # Stop packet capture
        self.test_complete = True
        time.sleep(2)
        
        return self.analyze_results(processed_windows)
    
    def analyze_results(self, processed_windows):
        """Analyze sepsis prediction results"""
        print("\n" + "=" * 60)
        print("SEPSIS RESULTS ANALYSIS")
        print("=" * 60)
        
        y_true = []
        y_pred = []
        matched_results = 0
        detailed_results = []
        
        # Match received alerts with expected results
        for window_id in processed_windows:
            if window_id in self.expected_results:
                expected = self.expected_results[window_id]
                patient_id = expected['patient_id']
                
                # Find corresponding received alert (latest for this patient)
                if patient_id in self.received_alerts and self.received_alerts[patient_id]:
                    latest_alert = self.received_alerts[patient_id][-1]
                    
                    expected_sepsis = expected['sepsis']
                    predicted_sepsis = 1 if latest_alert['sepsis_prediction'] > 0 else 0
                    
                    y_true.append(expected_sepsis)
                    y_pred.append(predicted_sepsis)
                    matched_results += 1
                    
                    detailed_results.append({
                        'patient_id': patient_id,
                        'expected_sepsis': expected_sepsis,
                        'predicted_sepsis': predicted_sepsis,
                        'sepsis_prediction_value': latest_alert['sepsis_prediction'],
                        'heart_failure_prediction': latest_alert['heart_failure_prediction'],
                        'news2_score': latest_alert['news2_score'],
                        'original_condition': expected['original_condition']
                    })
        
        print(f"Matched {matched_results} out of {len(processed_windows)} windows")
        print(f"Match rate: {matched_results/len(processed_windows)*100:.1f}%")
        
        if len(y_true) > 0:
            # Calculate metrics
            accuracy = accuracy_score(y_true, y_pred)
            
            # Count by class
            true_normal = sum(1 for x in y_true if x == 0)
            true_sepsis = sum(1 for x in y_true if x == 1)
            pred_normal = sum(1 for x in y_pred if x == 0)
            pred_sepsis = sum(1 for x in y_pred if x == 1)
            
            print(f"\nClass Distribution:")
            print(f"  True Normal: {true_normal}, True Sepsis: {true_sepsis}")
            print(f"  Predicted Normal: {pred_normal}, Predicted Sepsis: {pred_sepsis}")
            
            print(f"\nSepsis Prediction Accuracy: {accuracy:.4f}")
            
            # Classification report
            print("\nClassification Report:")
            try:
                report = classification_report(y_true, y_pred, 
                                             target_names=['Normal', 'Sepsis'],
                                             digits=4, zero_division=0)
                print(report)
            except Exception as e:
                print(f"Error generating classification report: {e}")
            
            # Confusion matrix
            print("\nConfusion Matrix:")
            cm = confusion_matrix(y_true, y_pred)
            print("           Predicted")
            print("         Normal  Sepsis")
            print(f"Normal    {cm[0,0]:6}  {cm[0,1]:6}")
            print(f"Sepsis    {cm[1,0]:6}  {cm[1,1]:6}")
            
            # Save detailed results
            self.save_detailed_results(detailed_results)
            
            return {
                'accuracy': accuracy,
                'y_true': y_true,
                'y_pred': y_pred,
                'classification_report': classification_report(y_true, y_pred, output_dict=True, zero_division=0),
                'confusion_matrix': cm,
                'detailed_results': detailed_results
            }
        else:
            print("❌ No sepsis results to analyze!")
            print("Possible issues:")
            print("- No alert packets received")
            print("- Alert parsing failed") 
            print("- P4 program not generating sepsis predictions")
            return None
    
    def save_detailed_results(self, detailed_results):
        """Save detailed results to CSV"""
        if detailed_results:
            filename = f'sepsis_accuracy_detailed_{int(time.time())}.csv'
            df = pd.DataFrame(detailed_results)
            df.to_csv(filename, index=False)
            print(f"\n💾 Detailed results saved to {filename}")

def main():
    print("🩺 Sepsis Accuracy Test")
    print("=" * 50)
    
    # Adjust the data file path as needed
    data_file = input("Enter sepsis data file path [../data/val_data_normal_vs_sepsis.csv]: ").strip()
    if not data_file:
        data_file = '../data/val_data_normal_vs_sepsis.csv'
    
    try:
        # Test sepsis prediction
        sepsis_tester = AccuracyTester(data_file)
        sepsis_results = sepsis_tester.run_test()
        
        if sepsis_results:
            print("\n" + "=" * 60)
            print("🎯 SEPSIS PREDICTION TEST COMPLETE")
            print("=" * 60)
            print(f"Final Accuracy: {sepsis_results['accuracy']:.4f}")
            
            # Summary stats
            cm = sepsis_results['confusion_matrix']
            if cm.shape == (2, 2):
                tn, fp, fn, tp = cm.ravel()
                sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
                specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
                
                print(f"Sensitivity (Recall): {sensitivity:.4f}")
                print(f"Specificity: {specificity:.4f}")
        else:
            print("\n❌ Test failed - no results obtained")
            
    except FileNotFoundError:
        print(f"❌ Data file not found: {data_file}")
    except Exception as e:
        print(f"❌ Test error: {e}")

if __name__ == "__main__":
    main()