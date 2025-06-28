#!/usr/bin/env python3
import time
import threading
import csv
from scapy.all import *
import struct

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

class TimeoutTester:
    def __init__(self):
        self.sensor_iface = 'enx0c37965f8a10'
        self.monitor_iface = 'enx0c37965f8a0a'
        self.timeout_data = []
        self.sent_scenarios = {}
        self.monitoring_active = True
        
    def send_scenario(self, patient_id, scenario_name, sensors_to_send, values=None):
        """Send a specific sensor scenario"""
        if values is None:
            values = [380, 94, 110, 90, 22, 1, 1, 2, 65, 1]  # Default sepsis-like values
        
        send_time = time.time()
        base_timestamp = int(send_time * 1000)
        
        self.sent_scenarios[patient_id] = {
            'scenario': scenario_name,
            'sensors_sent': sensors_to_send,
            'send_time': send_time,
            'expected_timeout': len(sensors_to_send) < 10
        }
        
        for sensor_id in sensors_to_send:
            pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                patient_id=patient_id,
                sensor_id=sensor_id,
                timestamp=base_timestamp + sensor_id * 100,
                feature_value=values[sensor_id]  # Fixed variable name
            )
            sendp(pkt, iface=self.sensor_iface, verbose=False)
            time.sleep(0.01)
        
        print(f"Patient {patient_id}: {scenario_name} - sent sensors {sensors_to_send}")
        return send_time
    
    def monitor_alerts(self):
        """Monitor timeout alerts with proper Alert header parsing"""
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
                        sepsis_pred = alert.sepPrediction
                        hf_pred = alert.hfPrediction
                        news2_score = alert.news2Score
                    else:
                        # Fallback: manual parsing
                        payload_bytes = bytes(pkt.payload)
                        if len(payload_bytes) >= 18:
                            patient_id = struct.unpack('!I', payload_bytes[0:4])[0]
                            sepsis_pred = struct.unpack('!I', payload_bytes[10:14])[0]
                            news2_score = payload_bytes[14]
                            hf_pred = struct.unpack('!I', payload_bytes[16:20])[0]
                        else:
                            return
                    
                    if patient_id and patient_id in self.sent_scenarios:
                        scenario_info = self.sent_scenarios[patient_id]
                        response_time = (receive_time - scenario_info['send_time']) * 1000  # ms
                        
                        alert_data = {
                            'patient_id': patient_id,
                            'scenario': scenario_info['scenario'],
                            'sensors_sent': len(scenario_info['sensors_sent']),
                            'missing_sensors': 10 - len(scenario_info['sensors_sent']),
                            'response_time_ms': response_time,
                            'expected_timeout': scenario_info['expected_timeout'],
                            'sepsis_prediction': sepsis_pred,
                            'hf_prediction': hf_pred,
                            'news2_score': news2_score,
                            'timestamp': receive_time
                        }
                        
                        self.timeout_data.append(alert_data)
                        
                        print(f"Alert - Patient {patient_id} ({scenario_info['scenario']}): "
                              f"{response_time:.0f}ms, Sepsis:{sepsis_pred}, HF:{hf_pred}, NEWS2:{news2_score}")
                        
                        del self.sent_scenarios[patient_id]
                        
                except Exception as e:
                    print(f"Error processing timeout alert: {e}")
        
        sniff(iface=self.monitor_iface, prn=alert_handler, 
              filter="ether proto 0x1236", store=0)
    
    def run_timeout_test(self, repetitions=5):
        """Test different timeout scenarios"""
        scenarios = [
            {'name': 'Complete', 'sensors': list(range(10))},  # All 10 sensors
            {'name': 'Missing_1', 'sensors': list(range(9))},  # Missing 1 sensor
            {'name': 'Missing_2', 'sensors': [0,1,2,3,4,5,6,7]},  # Missing 2 sensors
            {'name': 'Missing_3', 'sensors': [0,1,2,3,4,5,6]},    # Missing 3 sensors
            {'name': 'Critical_Only', 'sensors': [0,1,2,3]},       # Only temp, O2, pulse, BP
            {'name': 'Half_Missing', 'sensors': [0,2,4,6,8]},      # Every other sensor
            {'name': 'Most_Missing', 'sensors': [0,1,2]},          # Only first 3
            {'name': 'Single_Sensor', 'sensors': [0]},             # Only temperature
            {'name': 'No_Critical', 'sensors': [4,5,6,7,8,9]},     # Missing all critical
            {'name': 'Random_Pattern', 'sensors': [0,2,5,7,9]}     # Random pattern
        ]
        
        print(f"=== Timeout Behavior Test: {len(scenarios)} scenarios × {repetitions} repetitions ===")
        print("Note: Relies on controller's 15-second heartbeat for timeout processing")
        
        # Start monitoring
        monitor_thread = threading.Thread(target=self.monitor_alerts)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        patient_id = 1500  # NEW - starts at 1.5K
        # Max: 1500 + 150 = 1,650 (fits in 2K limit, or any higher limit)
        
        for rep in range(repetitions):
            print(f"\n--- Repetition {rep + 1}/{repetitions} ---")
            
            for scenario in scenarios:
                self.send_scenario(patient_id, scenario['name'], scenario['sensors'])
                patient_id += 1
                time.sleep(2)  # Space between scenarios
            
            # Wait between repetitions
            time.sleep(10)
        
        # Wait for all alerts (including longest timeouts)
        print("\nWaiting for all timeout alerts (including 60s+ timeouts)...")
        time.sleep(120)  # Wait for timeouts + heartbeat processing
        
        self.monitoring_active = False
        self.save_results()
        return self.analyze_results()
    
    def save_results(self):
        """Save timeout test results"""
        filename = f'timeout_results_{int(time.time())}.csv'
        
        if self.timeout_data:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.timeout_data[0].keys())
                writer.writeheader()
                writer.writerows(self.timeout_data)
        
        print(f"Timeout results saved to {filename}")
        return filename
    
    def analyze_results(self):
        """Analyze timeout behavior"""
        if not self.timeout_data:
            print("❌ No timeout data collected!")
            print("Check if controller heartbeat mechanism is working")
            return
        
        # Group by scenario
        scenarios = {}
        for data in self.timeout_data:
            scenario = data['scenario']
            if scenario not in scenarios:
                scenarios[scenario] = []
            scenarios[scenario].append(data)
        
        print("\n" + "="*80)
        print("TIMEOUT BEHAVIOR TEST RESULTS")
        print("="*80)
        print(f"{'Scenario':<15} {'Count':<6} {'Sensors':<8} {'Avg Time(ms)':<12} {'Sepsis':<7} {'HF':<4} {'NEWS2':<7}")
        print("-" * 80)
        
        for scenario_name, data_list in scenarios.items():
            avg_time = sum(d['response_time_ms'] for d in data_list) / len(data_list)
            sensors_sent = data_list[0]['sensors_sent']
            sepsis_alerts = sum(1 for d in data_list if d['sepsis_prediction'] > 0)
            hf_alerts = sum(1 for d in data_list if d['hf_prediction'] > 0)
            avg_news2 = sum(d['news2_score'] for d in data_list) / len(data_list)
            
            print(f"{scenario_name:<15} {len(data_list):<6} {sensors_sent:<8} {avg_time:<12.0f} "
                  f"{sepsis_alerts:<7} {hf_alerts:<4} {avg_news2:<7.1f}")
        
        print("="*80)
        
        # Analysis by missing sensor count
        print("\nAnalysis by Missing Sensor Count:")
        missing_analysis = {}
        for data in self.timeout_data:
            missing = data['missing_sensors']
            if missing not in missing_analysis:
                missing_analysis[missing] = []
            missing_analysis[missing].append(data['response_time_ms'])
        
        for missing, times in sorted(missing_analysis.items()):
            avg_time = sum(times) / len(times)
            print(f"Missing {missing} sensors: {len(times)} samples, avg {avg_time:.0f}ms")
            if missing > 0 and avg_time < 50000:  # Less than 50 seconds
                print(f"  ⚠️  Expected longer timeout for missing sensors!")

if __name__ == "__main__":
    tester = TimeoutTester()
    tester.run_timeout_test(repetitions=3)
