#!/usr/bin/env python3
import time
import threading
import csv
import random
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
        
    def send_scenario(self, patient_id, scenario_name, sensors_to_send, condition=0):
        """Send a specific sensor scenario with mixed condition data"""
        values = self.get_sample_data(condition)
        
        send_time = time.time()
        base_timestamp = int(send_time * 1000)
        
        condition_names = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}
        condition_name = condition_names[condition]
        
        self.sent_scenarios[patient_id] = {
            'scenario': scenario_name,
            'condition': condition,
            'condition_name': condition_name,
            'sensors_sent': sensors_to_send,
            'send_time': send_time,
            'expected_timeout': len(sensors_to_send) < 10
        }
        
        for sensor_id in sensors_to_send:
            pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                patient_id=patient_id,
                sensor_id=sensor_id,
                timestamp=base_timestamp + sensor_id * 100,
                feature_value=values[sensor_id]
            )
            sendp(pkt, iface=self.sensor_iface, verbose=False)
            time.sleep(0.01)
        
        print(f"Patient {patient_id}: {scenario_name} ({condition_name}) - sent sensors {sensors_to_send}")
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
                            'condition': scenario_info['condition'],
                            'condition_name': scenario_info['condition_name'],
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
                        
                        print(f"Alert - Patient {patient_id} ({scenario_info['scenario']}, {scenario_info['condition_name']}): "
                              f"{response_time:.0f}ms, Sepsis:{sepsis_pred}, HF:{hf_pred}, NEWS2:{news2_score}")
                        
                        del self.sent_scenarios[patient_id]
                        
                except Exception as e:
                    print(f"Error processing timeout alert: {e}")
        
        sniff(iface=self.monitor_iface, prn=alert_handler, 
              filter="ether proto 0x1236", store=0)
    
    def run_mixed_timeout_test(self, repetitions=3):
        """Test different timeout scenarios with mixed conditions"""
        scenarios = [
            {'name': 'Complete', 'sensors': list(range(10))},     # All 10 sensors
            {'name': 'Missing_1', 'sensors': list(range(9))},     # Missing 1 sensor
            {'name': 'Missing_2', 'sensors': [0,1,2,3,4,5,6,7]}, # Missing 2 sensors
            {'name': 'Missing_3', 'sensors': [0,1,2,3,4,5,6]},   # Missing 3 sensors
            {'name': 'Critical_Only', 'sensors': [0,1,2,3]},      # Only temp, O2, pulse, BP
            {'name': 'Half_Missing', 'sensors': [0,2,4,6,8]},     # Every other sensor
            {'name': 'Most_Missing', 'sensors': [0,1,2]},         # Only first 3
            {'name': 'Single_Sensor', 'sensors': [0]},            # Only temperature
            {'name': 'No_Critical', 'sensors': [4,5,6,7,8,9]},    # Missing all critical
            {'name': 'Random_Pattern', 'sensors': [0,2,5,7,9]}    # Random pattern
        ]
        
        total_tests = len(scenarios) * repetitions * 3  # 3 conditions per scenario per repetition
        
        print(f"=== Mixed Condition Timeout Test ===")
        print(f"Testing {len(scenarios)} scenarios × {repetitions} repetitions × 3 conditions = {total_tests} total tests")
        print("Conditions: 0=Normal, 1=Sepsis, 2=Heart Failure")
        print("Note: Relies on controller's 15-second heartbeat for timeout processing")
        
        # Start monitoring
        monitor_thread = threading.Thread(target=self.monitor_alerts)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        patient_id = 1500  # Safe range for patient IDs
        
        # Create randomized test order
        test_cases = []
        for rep in range(repetitions):
            for scenario in scenarios:
                for condition in [0, 1, 2]:  # Normal, Sepsis, Heart Failure
                    test_cases.append({
                        'patient_id': patient_id,
                        'repetition': rep + 1,
                        'scenario': scenario,
                        'condition': condition
                    })
                    patient_id += 1
        
        # Shuffle to randomize order and avoid temporal bias
        random.shuffle(test_cases)
        
        print(f"\nStarting {len(test_cases)} mixed condition timeout tests...")
        
        for i, test_case in enumerate(test_cases):
            condition_name = {0: 'Normal', 1: 'Sepsis', 2: 'Heart Failure'}[test_case['condition']]
            
            self.send_scenario(
                test_case['patient_id'], 
                test_case['scenario']['name'], 
                test_case['scenario']['sensors'],
                test_case['condition']
            )
            
            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"Progress: {i + 1}/{len(test_cases)} tests sent...")
            
            time.sleep(2)  # Space between scenarios
        
        print(f"\nCompleted sending {len(test_cases)} test cases")
        
        # Wait for all alerts (including longest timeouts)
        print("Waiting for all timeout alerts (including 60s+ timeouts)...")
        total_wait = 120  # 2 minutes should cover all timeouts
        
        for remaining in range(total_wait, 0, -10):
            time.sleep(10)
            received = len(self.timeout_data)
            print(f"  {remaining}s remaining... Received {received}/{len(test_cases)} alerts")
        
        self.monitoring_active = False
        
        print(f"\nFinal results: {len(self.timeout_data)}/{len(test_cases)} alerts received")
        
        self.save_results()
        return self.analyze_mixed_results()
    
    def save_results(self):
        """Save timeout test results"""
        filename = f'timeout_results_mixed_{int(time.time())}.csv'
        
        if self.timeout_data:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.timeout_data[0].keys())
                writer.writeheader()
                writer.writerows(self.timeout_data)
        
        print(f"Timeout results saved to {filename}")
        return filename
    
    def analyze_mixed_results(self):
        """Analyze timeout behavior with condition breakdown"""
        if not self.timeout_data:
            print("❌ No timeout data collected!")
            print("Check if controller heartbeat mechanism is working")
            return
        
        # Group by scenario and condition
        scenarios = {}
        condition_analysis = {}
        
        for data in self.timeout_data:
            scenario = data['scenario']
            condition = data['condition']
            condition_name = data['condition_name']
            
            # Group by scenario
            if scenario not in scenarios:
                scenarios[scenario] = []
            scenarios[scenario].append(data)
            
            # Group by condition
            if condition_name not in condition_analysis:
                condition_analysis[condition_name] = []
            condition_analysis[condition_name].append(data)
        
        print("\n" + "="*80)
        print("MIXED CONDITION TIMEOUT BEHAVIOR TEST RESULTS")
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
        
        # Analysis by condition
        print(f"\n📊 Results by Patient Condition:")
        print("-" * 60)
        
        for condition_name, data_list in condition_analysis.items():
            sepsis_alerts = sum(1 for d in data_list if d['sepsis_prediction'] > 0)
            hf_alerts = sum(1 for d in data_list if d['hf_prediction'] > 0)
            high_news2 = sum(1 for d in data_list if d['news2_score'] >= 7)
            avg_news2 = sum(d['news2_score'] for d in data_list) / len(data_list)
            avg_time = sum(d['response_time_ms'] for d in data_list) / len(data_list)
            
            print(f"\n{condition_name} ({len(data_list)} total samples):")
            print(f"  Average response time: {avg_time/1000:.1f} seconds")
            print(f"  Sepsis alerts: {sepsis_alerts} ({sepsis_alerts/len(data_list)*100:.1f}%)")
            print(f"  Heart failure alerts: {hf_alerts} ({hf_alerts/len(data_list)*100:.1f}%)")
            print(f"  High NEWS2 scores (≥7): {high_news2} ({high_news2/len(data_list)*100:.1f}%)")
            print(f"  Average NEWS2 score: {avg_news2:.1f}")
            
            # Expected results commentary
            if condition_name == 'Normal':
                print(f"  Expected: Low sepsis/HF alerts, moderate NEWS2 scores")
            elif condition_name == 'Sepsis':
                print(f"  Expected: High sepsis alerts, moderate-high NEWS2 scores")
            elif condition_name == 'Heart Failure':
                print(f"  Expected: High heart failure alerts, moderate NEWS2 scores")
        
        # Analysis by missing sensor count
        print(f"\n📈 Analysis by Missing Sensor Count:")
        print("-" * 60)
        
        missing_analysis = {}
        for data in self.timeout_data:
            missing = data['missing_sensors']
            if missing not in missing_analysis:
                missing_analysis[missing] = []
            missing_analysis[missing].append(data['response_time_ms'])
        
        for missing, times in sorted(missing_analysis.items()):
            avg_time = sum(times) / len(times)
            print(f"Missing {missing} sensors: {len(times)} samples, avg {avg_time:.0f}ms")
            if missing == 0:
                if avg_time > 10000:  # More than 10 seconds
                    print(f"  ⚠️  Complete windows should be faster!")
            elif missing > 0:
                if avg_time < 50000:  # Less than 50 seconds
                    print(f"  ⚠️  Expected longer timeout for missing sensors!")
                else:
                    print(f"  ✅ Correct timeout behavior")
        
        # Timeout threshold analysis
        print(f"\n🔍 Timeout Threshold Analysis:")
        print("-" * 60)
        
        complete_times = [d['response_time_ms'] for d in self.timeout_data if d['missing_sensors'] == 0]
        timeout_times = [d['response_time_ms'] for d in self.timeout_data if d['missing_sensors'] > 0]
        
        if complete_times:
            avg_complete = sum(complete_times) / len(complete_times)
            print(f"Complete windows (10 sensors): {len(complete_times)} samples, avg {avg_complete:.0f}ms")
        
        if timeout_times:
            avg_timeout = sum(timeout_times) / len(timeout_times)
            print(f"Timeout windows (<10 sensors): {len(timeout_times)} samples, avg {avg_timeout/1000:.1f}s")
            
            # Check timeout consistency
            timeout_range = max(timeout_times) - min(timeout_times)
            print(f"Timeout range: {min(timeout_times)/1000:.1f}s - {max(timeout_times)/1000:.1f}s")
            print(f"Timeout consistency: ±{timeout_range/2000:.1f}s variation")
            
            if 60000 <= avg_timeout <= 75000:
                print(f"✅ Timeout behavior within expected 60-75 second range")
            else:
                print(f"⚠️  Timeout behavior outside expected range")
        
        print("="*80)
        
        # Still waiting for responses
        if self.sent_scenarios:
            print(f"\n⏳ Still waiting for {len(self.sent_scenarios)} responses:")
            for pid, info in self.sent_scenarios.items():
                elapsed = time.time() - info['send_time']
                print(f"  Patient {pid} ({info['scenario']}, {info['condition_name']}): {elapsed:.1f}s elapsed")

if __name__ == "__main__":
    print("=== IoT Gateway Mixed Condition Timeout Test ===")
    print("Testing timeout behavior with balanced samples from Normal, Sepsis, and Heart Failure patients")
    print("Monitoring interfaces:")
    print(f"  Sensor interface: enx0c37965f8a10")
    print(f"  Monitor interface: enx0c37965f8a0a")
    print()
    print("Conditions tested:")
    print("  0 = Normal patients")
    print("  1 = Sepsis patients") 
    print("  2 = Heart failure patients")
    print()
    print("Timeout scenarios:")
    print("  Complete, Missing_1-3, Critical_Only, Half_Missing,")
    print("  Most_Missing, Single_Sensor, No_Critical, Random_Pattern")
    print()
    
    tester = TimeoutTester()
    # Test with 3 repetitions of each scenario for each condition
    tester.run_mixed_timeout_test(repetitions=3)
