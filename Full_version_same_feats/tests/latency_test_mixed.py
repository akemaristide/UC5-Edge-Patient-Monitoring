#!/usr/bin/env python3
import time
import threading
import csv
from scapy.all import *
import numpy as np
import struct
import random

# Define Sensor header structure to match your P4 code
class Sensor(Packet):
    name = "Sensor"
    fields_desc = [
        IntField("patient_id", 0),      # bit<32>
        IntField("sensor_id", 0),       # bit<32>
        BitField("timestamp", 0, 48),   # bit<48>
        ShortField("feature_value", 0)  # bit<16>
    ]

# Define Alert header structure to match your P4 code exactly
class Alert(Packet):
    name = "Alert"
    fields_desc = [
        IntField("patient_id", 0),          # bit<32>
        BitField("timestamp", 0, 48),       # bit<48>
        IntField("sepPrediction", 0),       # bit<32>
        ByteField("news2Score", 0),         # bit<8>
        ByteField("news2Alert", 0),         # bit<8>
        IntField("hfPrediction", 0)         # bit<32>
    ]

# Bind the packet types to EtherTypes
bind_layers(Ether, Sensor, type=0x1235)
bind_layers(Ether, Alert, type=0x1236)

class LatencyTester:
    def __init__(self):
        self.sensor_iface = 'enx0c37965f8a10'      # Your actual sensor interface
        self.monitor_iface = 'enx0c37965f8a0a'     # Your actual monitor interface
        self.sent_times = {}            # patient_id -> send_info
        self.latency_data = []          # List of latency measurements
        self.monitoring_active = True
        
        # Sample data from the CSV files for different conditions
        self.sample_data = {
            'normal': [
                # From normal patients - condition 0
                [361, 95, 70, 126, 15, 0, 1, 3, 78, 0],  # Patient 377, NEWS2: 3
                [367, 94, 77, 105, 17, 0, 1, 2, 42, 0],  # Patient 332, NEWS2: 4
                [361, 97, 67, 93, 18, 0, 1, 1, 30, 0],   # Patient 306, NEWS2: 4
                [369, 95, 67, 113, 21, 0, 1, 2, 55, 0],  # Patient 264, NEWS2: 4
                [360, 99, 99, 113, 17, 0, 0, 3, 60, 0],  # Patient 232, NEWS2: 2
                [361, 95, 70, 126, 15, 0, 1, 3, 76, 0],  # Patient 129, NEWS2: 3
                [370, 97, 67, 113, 21, 0, 1, 2, 52, 0],  # Patient 150, NEWS2: 4
                [364, 94, 79, 122, 13, 0, 1, 1, 24, 0],  # Patient 204, NEWS2: 3
                [361, 94, 86, 124, 14, 0, 0, 3, 72, 0],  # Patient 213, NEWS2: 1
                [382, 86, 64, 83, 26, 0, 1, 0, 62, 0],   # Patient 124, NEWS2: 12
            ],
            'sepsis': [
                # From sepsis patients - condition 1
                [359, 94, 78, 109, 16, 0, 1, 3, 86, 1],  # Patient 29, NEWS2: 5
                [380, 94, 110, 90, 22, 1, 1, 2, 65, 1],  # Patient 280, NEWS2: 16
                [368, 92, 72, 137, 18, 0, 1, 3, 71, 1],  # Patient 230, NEWS2: 4
                [368, 96, 89, 136, 14, 0, 0, 3, 72, 1],  # Patient 223, NEWS2: 0
                [369, 91, 70, 95, 22, 0, 0, 3, 71, 1],   # Patient 266, NEWS2: 7
                [369, 97, 71, 114, 19, 0, 1, 3, 76, 1],  # Patient 188, NEWS2: 2
                [364, 95, 70, 126, 15, 0, 1, 3, 78, 1],  # Patient 330, NEWS2: 3
                [374, 92, 104, 93, 31, 0, 0, 0, 68, 1],  # Patient 259, NEWS2: 8
                [392, 91, 77, 100, 28, 0, 1, 0, 49, 1],  # Patient 276, NEWS2: 12
                [373, 94, 104, 105, 21, 0, 1, 2, 19, 1], # Patient 280 (early), NEWS2: 7
            ],
            'heart_failure': [
                # From heart failure patients - condition 2
                [377, 91, 84, 103, 21, 0, 0, 0, 48, 0],  # Patient 321, NEWS2: 6
                [369, 94, 77, 105, 17, 0, 1, 2, 42, 0],  # Patient 332, NEWS2: 4
                [370, 97, 67, 93, 18, 0, 1, 1, 30, 1],   # Patient 306, NEWS2: 4
                [377, 98, 68, 92, 18, 0, 0, 2, 55, 0],   # Patient 264, NEWS2: 2
                [361, 94, 86, 124, 14, 0, 0, 3, 69, 0],  # Patient 344, NEWS2: 1
                [370, 98, 67, 113, 21, 0, 1, 2, 52, 0],  # Patient 370, NEWS2: 4
                [361, 96, 88, 135, 16, 0, 0, 3, 76, 0],  # Patient 129 (HF symptoms), NEWS2: 0
                [368, 97, 67, 93, 18, 0, 1, 1, 30, 1],   # Patient 306 (HF variant), NEWS2: 4
                [374, 94, 95, 122, 25, 0, 0, 0, 49, 1],  # Patient 276 (HF), NEWS2: 5
                [369, 94, 104, 105, 21, 0, 1, 2, 19, 1], # Patient 280 (HF), NEWS2: 7
            ]
        }
        
    def get_sample_data(self, condition):
        """Get sample sensor data for the given condition"""
        condition_map = {0: 'normal', 1: 'sepsis', 2: 'heart_failure'}
        condition_name = condition_map.get(condition, 'normal')
        
        # Return a random sample from the condition
        samples = self.sample_data[condition_name]
        return random.choice(samples)
        
    def send_complete_window(self, patient_id, condition=0):
        """Send complete 10-sensor window for specified condition"""
        start_time = time.time()
        self.sent_times[patient_id] = {
            'start_time': start_time,
            'type': 'complete',
            'condition': condition
        }
        
        base_timestamp = int(start_time * 1000)
        sensor_values = self.get_sample_data(condition)
        
        condition_names = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}
        
        for sensor_id in range(10):
            pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                patient_id=patient_id,
                sensor_id=sensor_id,
                timestamp=base_timestamp + sensor_id * 100,
                feature_value=sensor_values[sensor_id]
            )
            sendp(pkt, iface=self.sensor_iface, verbose=False)
            time.sleep(0.01)
            
        print(f"Sent complete window for patient {patient_id} ({condition_names[condition]})")
        return start_time
    
    def send_partial_window(self, patient_id, condition=0, num_sensors=6):
        """Send partial window - will wait for controller's heartbeat to trigger timeout"""
        start_time = time.time()
        self.sent_times[patient_id] = {
            'start_time': start_time,
            'type': 'partial',
            'condition': condition
        }
        
        base_timestamp = int(start_time * 1000)
        sensor_values = self.get_sample_data(condition)
        
        condition_names = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}
        
        # Send only first num_sensors
        for sensor_id in range(num_sensors):
            pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                patient_id=patient_id,
                sensor_id=sensor_id,
                timestamp=base_timestamp + sensor_id * 100,
                feature_value=sensor_values[sensor_id]
            )
            sendp(pkt, iface=self.sensor_iface, verbose=False)
            time.sleep(0.01)
            
        print(f"Sent partial window for patient {patient_id} ({condition_names[condition]}, {num_sensors} sensors)")
        return start_time
    
    def monitor_alerts(self):
        """Monitor for alert packets with proper Alert header parsing"""
        def alert_handler(pkt):
            if not self.monitoring_active:
                return
                
            if pkt.haslayer(Ether) and pkt[Ether].type == 0x1236:
                receive_time = time.time()
                
                try:
                    # Parse the Alert header properly
                    if pkt.haslayer(Alert):
                        alert = pkt[Alert]
                        patient_id = alert.patient_id
                        sep_pred = alert.sepPrediction
                        news2_score = alert.news2Score
                        news2_alert = alert.news2Alert
                        hf_pred = alert.hfPrediction
                        alert_timestamp = alert.timestamp
                        
                        print(f"DEBUG: Parsed Alert - Patient: {patient_id}, Sepsis: {sep_pred}, NEWS2: {news2_score}, HF: {hf_pred}")
                        
                    else:
                        # Fallback: manual parsing if Scapy parsing fails
                        payload_bytes = bytes(pkt.payload)
                        if len(payload_bytes) >= 18:  # Minimum Alert header size (4+6+4+1+1+4 = 20 bytes)
                            # Manual parsing according to Alert header structure
                            patient_id = struct.unpack('!I', payload_bytes[0:4])[0]  # bit<32>
                            timestamp = struct.unpack('!Q', b'\x00\x00' + payload_bytes[4:10])[0]  # bit<48> padded to 64-bit
                            sep_pred = struct.unpack('!I', payload_bytes[10:14])[0]  # bit<32>
                            news2_score = payload_bytes[14]  # bit<8>
                            news2_alert = payload_bytes[15]  # bit<8>
                            hf_pred = struct.unpack('!I', payload_bytes[16:20])[0]  # bit<32>
                            
                            print(f"DEBUG: Manual parsed Alert - Patient: {patient_id}, Sepsis: {sep_pred}, NEWS2: {news2_score}, HF: {hf_pred}")
                        else:
                            print(f"DEBUG: Alert packet too short: {len(payload_bytes)} bytes")
                            print(f"DEBUG: Raw payload: {payload_bytes.hex()}")
                            return
                    
                    if patient_id and patient_id in self.sent_times:
                        send_info = self.sent_times[patient_id]
                        latency_ms = (receive_time - send_info['start_time']) * 1000
                        
                        condition_names = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}
                        condition_name = condition_names[send_info['condition']]
                        
                        self.latency_data.append({
                            'patient_id': patient_id,
                            'window_type': send_info['type'],
                            'condition': send_info['condition'],
                            'condition_name': condition_name,
                            'latency_ms': latency_ms,
                            'timestamp': receive_time,
                            'sepsis_prediction': sep_pred,
                            'news2_score': news2_score,
                            'news2_alert': news2_alert,
                            'hf_prediction': hf_pred
                        })
                        
                        print(f"✓ Patient {patient_id} ({condition_name}, {send_info['type']}): {latency_ms:.2f} ms, "
                              f"Sepsis: {sep_pred}, NEWS2: {news2_score}, HF: {hf_pred}")
                        del self.sent_times[patient_id]
                    else:
                        if patient_id:
                            print(f"DEBUG: Received alert for unknown patient {patient_id}")
                        
                except Exception as e:
                    print(f"Error processing alert: {e}")
                    # Debug: print raw packet info
                    print(f"DEBUG: Packet length: {len(pkt)}")
                    print(f"DEBUG: EtherType: 0x{pkt[Ether].type:04x}")
                    if hasattr(pkt, 'payload'):
                        print(f"DEBUG: Payload length: {len(pkt.payload)}")
                        print(f"DEBUG: Payload bytes: {bytes(pkt.payload)[:20].hex()}")
        
        print(f"Starting to monitor alerts on {self.monitor_iface}...")
        sniff(iface=self.monitor_iface, prn=alert_handler, 
              filter="ether proto 0x1236", store=0)
    
    def run_mixed_latency_test(self, samples_per_condition=10, partial_samples_per_condition=5, spacing_seconds=2):
        """Run comprehensive latency test with balanced condition samples"""
        total_complete = samples_per_condition * 3  # Normal, Sepsis, Heart Failure
        total_partial = partial_samples_per_condition * 3
        
        print(f"=== Mixed Condition Latency Test ===")
        print(f"Complete windows: {samples_per_condition} each of Normal, Sepsis, Heart Failure ({total_complete} total)")
        print(f"Partial windows: {partial_samples_per_condition} each of Normal, Sepsis, Heart Failure ({total_partial} total)")
        print("Note: Partial windows rely on controller's 15-second heartbeat schedule")
        print("Expected partial window latency: 60-75 seconds (60s timeout + next heartbeat)")
        print(f"Monitoring on: {self.monitor_iface}")
        print(f"Sending on: {self.sensor_iface}")
        
        # Start monitoring
        monitor_thread = threading.Thread(target=self.monitor_alerts)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Give monitor thread time to start
        time.sleep(2)
        
        patient_id = 1000
        
        # Create shuffled list of conditions for complete windows
        complete_conditions = []
        for condition in [0, 1, 2]:  # Normal, Sepsis, Heart Failure
            complete_conditions.extend([condition] * samples_per_condition)
        random.shuffle(complete_conditions)
        
        # Send complete windows
        print(f"\nSending {total_complete} complete windows (mixed conditions)...")
        for i, condition in enumerate(complete_conditions):
            self.send_complete_window(patient_id, condition)
            patient_id += 1
            time.sleep(spacing_seconds)
        
        print(f"Completed sending {total_complete} complete windows")
        
        # Create shuffled list of conditions for partial windows
        partial_conditions = []
        for condition in [0, 1, 2]:  # Normal, Sepsis, Heart Failure
            partial_conditions.extend([condition] * partial_samples_per_condition)
        random.shuffle(partial_conditions)
        
        # Send partial windows
        print(f"\nSending {total_partial} partial windows (mixed conditions)...")
        for i, condition in enumerate(partial_conditions):
            num_sensors = 4 + (i % 5)  # Vary 4-8 sensors
            self.send_partial_window(patient_id, condition, num_sensors)
            patient_id += 1
            time.sleep(spacing_seconds)
        
        print(f"Completed sending {total_partial} partial windows")
        
        # Calculate wait time based on controller heartbeat schedule
        max_expected_latency = 60 + 15 + 5  # 80 seconds
        total_wait_time = max_expected_latency + 30  # Add 30s buffer
        
        print(f"\nWaiting {total_wait_time} seconds for all responses...")
        print("(Partial windows need to wait for controller's scheduled heartbeats)")
        
        # Progress indicator for long wait
        for remaining in range(total_wait_time, 0, -10):
            time.sleep(10)
            complete_received = len([d for d in self.latency_data if d['window_type'] == 'complete'])
            partial_received = len([d for d in self.latency_data if d['window_type'] == 'partial'])
            print(f"  {remaining}s remaining... Received: {complete_received}/{total_complete} complete, {partial_received}/{total_partial} partial")
        
        self.monitoring_active = False
        
        # Final check
        print(f"\nFinal results: {len(self.latency_data)} total alerts received")
        complete_final = len([d for d in self.latency_data if d['window_type'] == 'complete'])
        partial_final = len([d for d in self.latency_data if d['window_type'] == 'partial'])
        print(f"Complete: {complete_final}/{total_complete}, Partial: {partial_final}/{total_partial}")
        
        self.save_results()
        return self.analyze_mixed_results()
    
    def save_results(self):
        """Save results to CSV for plotting"""
        timestamp = int(time.time())
        filename = f'latency_results_mixed_{timestamp}.csv'
        
        if self.latency_data:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.latency_data[0].keys())
                writer.writeheader()
                writer.writerows(self.latency_data)
        
        print(f"Results saved to {filename}")
        return filename
    
    def analyze_mixed_results(self):
        """Analyze and print results with condition breakdown"""
        if not self.latency_data:
            print("\n❌ No latency data collected!")
            print("Possible issues:")
            print("- Alert packets not being received on", self.monitor_iface)
            print("- Alert header parsing failing")
            print("- P4 program not generating alerts")
            print("- Controller heartbeat mechanism not working for partial windows")
            return
        
        # Group results by condition and window type
        results_by_condition = {}
        for condition in [0, 1, 2]:
            condition_name = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}[condition]
            results_by_condition[condition_name] = {
                'complete': [d['latency_ms'] for d in self.latency_data 
                           if d['condition'] == condition and d['window_type'] == 'complete'],
                'partial': [d['latency_ms'] for d in self.latency_data 
                          if d['condition'] == condition and d['window_type'] == 'partial']
            }
        
        print("\n" + "="*80)
        print("MIXED CONDITION LATENCY TEST RESULTS")
        print("="*80)
        
        # Overall statistics
        complete_latencies = [d['latency_ms'] for d in self.latency_data if d['window_type'] == 'complete']
        partial_latencies = [d['latency_ms'] for d in self.latency_data if d['window_type'] == 'partial']
        
        if complete_latencies:
            print("✅ Overall Complete Windows (Direct Inference):")
            print(f"  Count: {len(complete_latencies)}")
            print(f"  Average: {np.mean(complete_latencies):.2f} ms")
            print(f"  Median: {np.median(complete_latencies):.2f} ms")
            print(f"  95th percentile: {np.percentile(complete_latencies, 95):.2f} ms")
        
        if partial_latencies:
            print(f"\n✅ Overall Partial Windows (Controller Heartbeat-Triggered):")
            print(f"  Count: {len(partial_latencies)}")
            print(f"  Average: {np.mean(partial_latencies)/1000:.1f} seconds")
            print(f"  Median: {np.median(partial_latencies)/1000:.1f} seconds")
        
        # Condition-specific breakdown
        print(f"\n📊 Results by Condition:")
        print("-" * 80)
        
        for condition_name, data in results_by_condition.items():
            print(f"\n{condition_name}:")
            
            if data['complete']:
                complete_avg = np.mean(data['complete'])
                print(f"  Complete windows: {len(data['complete'])} samples, avg {complete_avg:.2f} ms")
            else:
                print(f"  Complete windows: 0 samples")
            
            if data['partial']:
                partial_avg = np.mean(data['partial']) / 1000
                print(f"  Partial windows: {len(data['partial'])} samples, avg {partial_avg:.1f} seconds")
            else:
                print(f"  Partial windows: 0 samples")
        
        # Prediction accuracy analysis
        print(f"\n🎯 Prediction Analysis by Condition:")
        print("-" * 80)
        
        for condition in [0, 1, 2]:
            condition_name = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}[condition]
            condition_data = [d for d in self.latency_data if d['condition'] == condition]
            
            if condition_data:
                sepsis_predictions = sum(1 for d in condition_data if d.get('sepsis_prediction', 0) > 0)
                hf_predictions = sum(1 for d in condition_data if d.get('hf_prediction', 0) > 0)
                high_news2 = sum(1 for d in condition_data if d.get('news2_score', 0) >= 7)
                
                print(f"\n{condition_name} ({len(condition_data)} total samples):")
                print(f"  Sepsis alerts: {sepsis_predictions} ({sepsis_predictions/len(condition_data)*100:.1f}%)")
                print(f"  Heart failure alerts: {hf_predictions} ({hf_predictions/len(condition_data)*100:.1f}%)")
                print(f"  High NEWS2 scores (≥7): {high_news2} ({high_news2/len(condition_data)*100:.1f}%)")
                
                # Expected vs actual for each condition
                if condition == 0:  # Normal
                    print(f"  Expected: Low alerts across all metrics")
                elif condition == 1:  # Sepsis
                    print(f"  Expected: High sepsis alerts, moderate NEWS2")
                elif condition == 2:  # Heart Failure
                    print(f"  Expected: High heart failure alerts, moderate NEWS2")
        
        print("="*80)
        
        # Still waiting for responses
        if self.sent_times:
            print(f"\n⏳ Still waiting for {len(self.sent_times)} responses:")
            for pid, info in self.sent_times.items():
                elapsed = time.time() - info['start_time']
                condition_name = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}[info['condition']]
                print(f"  Patient {pid} ({condition_name}, {info['type']}): {elapsed:.1f}s elapsed")

if __name__ == "__main__":
    print("=== IoT Gateway Mixed Condition Latency Test ===")
    print("Testing with balanced samples from Normal, Sepsis, and Heart Failure patients")
    print("Monitoring interfaces:")
    print(f"  Sensor interface: enx0c37965f8a10")
    print(f"  Monitor interface: enx0c37965f8a0a")
    print()
    print("Conditions tested:")
    print("  0 = Normal patients")
    print("  1 = Sepsis patients") 
    print("  2 = Heart failure patients")
    print()
    print("Alert header structure:")
    print("  patient_id (32-bit) + timestamp (48-bit) + sepPrediction (32-bit) +")
    print("  news2Score (8-bit) + news2Alert (8-bit) + hfPrediction (32-bit)")
    print()
    
    tester = LatencyTester()
    # Test with 10 samples of each condition for complete windows
    # and 5 samples of each condition for partial windows
    tester.run_mixed_latency_test(
        samples_per_condition=10, 
        partial_samples_per_condition=5, 
        spacing_seconds=2
    )
