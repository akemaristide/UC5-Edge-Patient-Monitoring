#!/usr/bin/env python3
import time
import threading
import csv
from scapy.all import *
import numpy as np
import struct

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
        
    def send_complete_window(self, patient_id):
        """Send complete 10-sensor window"""
        start_time = time.time()
        self.sent_times[patient_id] = {
            'start_time': start_time,
            'type': 'complete'
        }
        
        base_timestamp = int(start_time * 1000)
        # Use values that trigger inference
        sensor_values = [380, 94, 110, 90, 22, 1, 1, 2, 65, 1]  # Sepsis-like values
        
        for sensor_id in range(10):
            pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                patient_id=patient_id,
                sensor_id=sensor_id,
                timestamp=base_timestamp + sensor_id * 100,
                feature_value=sensor_values[sensor_id]
            )
            sendp(pkt, iface=self.sensor_iface, verbose=False)
            time.sleep(0.01)
            
        print(f"Sent complete window for patient {patient_id}")
        return start_time
    
    def send_partial_window(self, patient_id, num_sensors=6):
        """Send partial window - will wait for controller's heartbeat to trigger timeout"""
        start_time = time.time()
        self.sent_times[patient_id] = {
            'start_time': start_time,
            'type': 'partial'
        }
        
        base_timestamp = int(start_time * 1000)
        sensor_values = [380, 94, 110, 90, 22, 1, 1, 2, 65, 1]
        
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
            
        print(f"Sent partial window for patient {patient_id} ({num_sensors} sensors)")
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
                        
                        self.latency_data.append({
                            'patient_id': patient_id,
                            'window_type': send_info['type'],
                            'latency_ms': latency_ms,
                            'timestamp': receive_time,
                            'sepsis_prediction': sep_pred,
                            'news2_score': news2_score,
                            'news2_alert': news2_alert,
                            'hf_prediction': hf_pred
                        })
                        
                        print(f"✓ Patient {patient_id} ({send_info['type']}): {latency_ms:.2f} ms, "
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
    
    def run_latency_test(self, num_complete=20, num_partial=10, spacing_seconds=2):
        """Run comprehensive latency test - relies on controller's heartbeats"""
        print(f"=== Latency Test: {num_complete} complete + {num_partial} partial windows ===")
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
        
        # Send complete windows
        print(f"\nSending {num_complete} complete windows...")
        for i in range(num_complete):
            self.send_complete_window(patient_id)
            patient_id += 1
            time.sleep(spacing_seconds)
        
        print(f"Completed sending {num_complete} complete windows")
        
        # Send partial windows
        print(f"\nSending {num_partial} partial windows...")
        for i in range(num_partial):
            self.send_partial_window(patient_id, num_sensors=4 + (i % 5))  # Vary 4-8 sensors
            patient_id += 1
            time.sleep(spacing_seconds)
        
        print(f"Completed sending {num_partial} partial windows")
        
        # Calculate wait time based on controller heartbeat schedule
        # Worst case: 60s timeout + up to 15s for next heartbeat + processing time
        max_expected_latency = 60 + 15 + 5  # 80 seconds
        total_wait_time = max_expected_latency + 30  # Add 30s buffer
        
        print(f"\nWaiting {total_wait_time} seconds for all responses...")
        print("(Partial windows need to wait for controller's scheduled heartbeats)")
        
        # Progress indicator for long wait
        for remaining in range(total_wait_time, 0, -10):
            time.sleep(10)
            complete_received = len([d for d in self.latency_data if d['window_type'] == 'complete'])
            partial_received = len([d for d in self.latency_data if d['window_type'] == 'partial'])
            print(f"  {remaining}s remaining... Received: {complete_received}/{num_complete} complete, {partial_received}/{num_partial} partial")
        
        self.monitoring_active = False
        
        # Final check
        print(f"\nFinal results: {len(self.latency_data)} total alerts received")
        complete_final = len([d for d in self.latency_data if d['window_type'] == 'complete'])
        partial_final = len([d for d in self.latency_data if d['window_type'] == 'partial'])
        print(f"Complete: {complete_final}/{num_complete}, Partial: {partial_final}/{num_partial}")
        
        self.save_results()
        return self.analyze_results()
    
    def save_results(self):
        """Save results to CSV for plotting"""
        timestamp = int(time.time())
        filename = f'latency_results_{timestamp}.csv'
        
        if self.latency_data:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.latency_data[0].keys())
                writer.writeheader()
                writer.writerows(self.latency_data)
        
        print(f"Results saved to {filename}")
        return filename
    
    def analyze_results(self):
        """Analyze and print results"""
        if not self.latency_data:
            print("\n❌ No latency data collected!")
            print("Possible issues:")
            print("- Alert packets not being received on", self.monitor_iface)
            print("- Alert header parsing failing")
            print("- P4 program not generating alerts")
            print("- Controller heartbeat mechanism not working for partial windows")
            return
        
        complete_latencies = [d['latency_ms'] for d in self.latency_data if d['window_type'] == 'complete']
        partial_latencies = [d['latency_ms'] for d in self.latency_data if d['window_type'] == 'partial']
        
        print("\n" + "="*60)
        print("LATENCY TEST RESULTS")
        print("="*60)
        
        if complete_latencies:
            print("✅ Complete Windows (Direct Inference):")
            print(f"  Count: {len(complete_latencies)}")
            print(f"  Average: {np.mean(complete_latencies):.2f} ms")
            print(f"  Median: {np.median(complete_latencies):.2f} ms")
            print(f"  Min: {np.min(complete_latencies):.2f} ms")
            print(f"  Max: {np.max(complete_latencies):.2f} ms")
            print(f"  95th percentile: {np.percentile(complete_latencies, 95):.2f} ms")
            print(f"  Standard deviation: {np.std(complete_latencies):.2f} ms")
        else:
            print("❌ Complete Windows: No responses received!")
        
        if partial_latencies:
            print("\n✅ Partial Windows (Controller Heartbeat-Triggered):")
            print(f"  Count: {len(partial_latencies)}")
            print(f"  Average: {np.mean(partial_latencies):.2f} ms ({np.mean(partial_latencies)/1000:.1f} seconds)")
            print(f"  Median: {np.median(partial_latencies):.2f} ms ({np.median(partial_latencies)/1000:.1f} seconds)")
            print(f"  Min: {np.min(partial_latencies):.2f} ms ({np.min(partial_latencies)/1000:.1f} seconds)")
            print(f"  Max: {np.max(partial_latencies):.2f} ms ({np.max(partial_latencies)/1000:.1f} seconds)")
            print(f"  Expected range: 60,000-75,000 ms (60s timeout + controller heartbeat)")
            
            # Check if latencies are in expected range
            expected_min = 55000  # 55s (allow some variation)
            expected_max = 80000  # 80s (60s + 15s + processing)
            in_range = [l for l in partial_latencies if expected_min <= l <= expected_max]
            print(f"  Within expected range: {len(in_range)}/{len(partial_latencies)} ({len(in_range)/len(partial_latencies)*100:.1f}%)")
        else:
            print("\n❌ Partial Windows: No responses received!")
            print("  This might indicate:")
            print("  - Controller heartbeat mechanism not working")
            print("  - Timeout processing not functioning")
            print("  - Alert packets not reaching monitoring interface")
        
        # Analysis of predictions
        if self.latency_data:
            sepsis_alerts = len([d for d in self.latency_data if d.get('sepsis_prediction', 0) > 0])
            hf_alerts = len([d for d in self.latency_data if d.get('hf_prediction', 0) > 0])
            high_news2 = len([d for d in self.latency_data if d.get('news2_score', 0) >= 7])
            
            print(f"\n📊 Prediction Summary:")
            print(f"  Sepsis alerts: {sepsis_alerts}/{len(self.latency_data)} ({sepsis_alerts/len(self.latency_data)*100:.1f}%)")
            print(f"  Heart failure alerts: {hf_alerts}/{len(self.latency_data)} ({hf_alerts/len(self.latency_data)*100:.1f}%)")
            print(f"  High NEWS2 scores (≥7): {high_news2}/{len(self.latency_data)} ({high_news2/len(self.latency_data)*100:.1f}%)")
        
        print("="*60)
        
        # Still waiting for responses
        if self.sent_times:
            print(f"\n⏳ Still waiting for {len(self.sent_times)} responses:")
            for pid, info in self.sent_times.items():
                elapsed = time.time() - info['start_time']
                print(f"  Patient {pid} ({info['type']}): {elapsed:.1f}s elapsed")

if __name__ == "__main__":
    print("=== IoT Gateway Latency Test (Fixed Alert Header) ===")
    print("Monitoring interfaces:")
    print(f"  Sensor interface: enx0c37965f8a10")
    print(f"  Monitor interface: enx0c37965f8a0a")
    print()
    print("Alert header structure:")
    print("  patient_id (32-bit) + timestamp (48-bit) + sepPrediction (32-bit) +")
    print("  news2Score (8-bit) + news2Alert (8-bit) + hfPrediction (32-bit)")
    print()
    
    tester = LatencyTester()
    tester.run_latency_test(num_complete=10, num_partial=5, spacing_seconds=2)
