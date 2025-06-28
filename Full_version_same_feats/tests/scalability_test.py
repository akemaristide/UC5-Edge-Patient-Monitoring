#!/usr/bin/env python3
import time
import threading
import csv
import random
from scapy.all import *
from collections import defaultdict
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

# Bind packet types to EtherTypes
bind_layers(Ether, Sensor, type=0x1235)
bind_layers(Ether, Alert, type=0x1236)

class ScalabilityTester:
    def __init__(self):
        self.sensor_iface = 'enx0c37965f8a10'
        self.monitor_iface = 'enx0c37965f8a0a'
        self.scalability_data = []
        self.patient_threads = {}
        self.alerts_by_patient = defaultdict(int)
        self.monitoring_active = True
        
    def simulate_patient(self, patient_id, duration_seconds, condition=0):
        """Simulate one patient for specified duration"""
        try:
            conditions = {
                0: [370, 98, 80, 120, 16, 0, 0, 1, 45, 1],    # Normal
                1: [390, 94, 110, 90, 22, 1, 1, 2, 65, 1],    # Sepsis
                2: [365, 95, 95, 140, 18, 0, 1, 1, 75, 0]     # Heart failure
            }
            
            values = conditions.get(condition, conditions[0])
            start_time = time.time()
            windows_sent = 0
            
            while time.time() - start_time < duration_seconds:
                base_timestamp = int(time.time() * 1000)
                
                # Send complete window (90% of time) or partial (10% of time)
                sensors_to_send = 10 if random.random() > 0.1 else random.randint(5, 9)
                
                for sensor_id in range(sensors_to_send):
                    # Add some realistic variation
                    noise = random.randint(-10, 10)
                    pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                        patient_id=patient_id,
                        sensor_id=sensor_id,
                        timestamp=base_timestamp + sensor_id * 100,
                        feature_value=max(0, values[sensor_id] + noise)  # Fixed indentation and variable name
                    )
                    sendp(pkt, iface=self.sensor_iface, verbose=False)
                    time.sleep(0.01)
                
                windows_sent += 1
                
                # Random interval between windows (30-300 seconds, realistic)
                interval = random.randint(30, 300)
                time.sleep(interval)
            
            return windows_sent
            
        except Exception as e:
            print(f"Patient {patient_id} simulation failed: {e}")
            return 0
    
    def monitor_alerts(self):
        """Monitor alerts and track by patient with proper Alert parsing"""
        def alert_handler(pkt):
            if not self.monitoring_active:
                return
                
            if pkt.haslayer(Ether) and pkt[Ether].type == 0x1236:
                try:
                    # Parse Alert header properly
                    if pkt.haslayer(Alert):
                        patient_id = pkt[Alert].patient_id
                    else:
                        # Fallback parsing
                        payload_bytes = bytes(pkt.payload)
                        if len(payload_bytes) >= 4:
                            patient_id = struct.unpack('!I', payload_bytes[0:4])[0]
                        else:
                            return
                    
                    if patient_id:
                        self.alerts_by_patient[patient_id] += 1
                        
                except Exception as e:
                    print(f"Error parsing alert in scalability test: {e}")
        
        sniff(iface=self.monitor_iface, prn=alert_handler, 
              filter="ether proto 0x1236", store=0)
    
    def run_scalability_test(self, max_patients=200, step=20, duration_per_step=300):
        """Test system with increasing number of concurrent patients"""
        print(f"=== Scalability Test: 0 to {max_patients} patients (step: {step}) ===")
        print("Note: Each patient sends mixed complete/partial windows with realistic timing")
        
        # Start alert monitoring
        monitor_thread = threading.Thread(target=self.monitor_alerts)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        results = []
        
        for num_patients in range(step, max_patients + 1, step):
            print(f"\nTesting {num_patients} concurrent patients for {duration_per_step} seconds...")
            
            # Reset for this test
            self.alerts_by_patient.clear()
            self.patient_threads.clear()
            
            test_start_time = time.time()
            
            # Start patient simulations
            threads = []
            for i in range(num_patients):
                patient_id = 30000 + i  # Unique ID range
                condition = i % 3  # Mix of conditions
                
                thread = threading.Thread(
                    target=self.simulate_patient,
                    args=(patient_id, duration_per_step, condition)
                )
                threads.append(thread)
                thread.start()
                
                # Stagger patient starts slightly
                time.sleep(0.1)
            
            # Wait for test duration
            time.sleep(duration_per_step)
            
            # Wait for threads to complete
            for thread in threads:
                thread.join(timeout=30)  # Don't wait forever
            
            # Wait for final alerts
            time.sleep(60)
            
            test_duration = time.time() - test_start_time
            
            # Calculate metrics
            active_patients = len([p for p in self.alerts_by_patient.keys() if self.alerts_by_patient[p] > 0])
            total_alerts = sum(self.alerts_by_patient.values())
            avg_alerts_per_patient = total_alerts / num_patients if num_patients > 0 else 0
            success_rate = (active_patients / num_patients) * 100 if num_patients > 0 else 0
            
            result = {
                'num_patients': num_patients,
                'duration_seconds': test_duration,
                'active_patients': active_patients,
                'total_alerts': total_alerts,
                'avg_alerts_per_patient': avg_alerts_per_patient,
                'success_rate_percent': success_rate,
                'alerts_per_second': total_alerts / test_duration if test_duration > 0 else 0
            }
            
            results.append(result)
            
            print(f"Results: {active_patients}/{num_patients} active ({success_rate:.1f}%), "
                  f"{total_alerts} total alerts, {result['alerts_per_second']:.2f} alerts/sec")
            
            # Stop if success rate drops significantly
            if success_rate < 80:
                print(f"⚠️  Success rate dropped below 80% at {num_patients} patients")
                break
            
            # Cool down between tests
            time.sleep(30)
        
        self.monitoring_active = False
        self.save_results(results)
        self.print_results(results)
        return results
    
    def save_results(self, results):
        """Save scalability results for plotting"""
        filename = f'scalability_results_{int(time.time())}.csv'
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        
        print(f"Scalability results saved to {filename}")
        return filename
    
    def print_results(self, results):
        """Print formatted results"""
        print("\n" + "="*70)
        print("SCALABILITY TEST RESULTS")
        print("="*70)
        print(f"{'Patients':<10} {'Active':<8} {'Success%':<10} {'Alerts':<8} {'Alerts/sec':<12}")
        print("-" * 70)
        
        for r in results:
            print(f"{r['num_patients']:<10} {r['active_patients']:<8} {r['success_rate_percent']:<10.1f} "
                  f"{r['total_alerts']:<8} {r['alerts_per_second']:<12.2f}")
        
        print("="*70)
        
        # Find maximum sustainable load
        good_results = [r for r in results if r['success_rate_percent'] >= 95]
        if good_results:
            max_load = max(good_results, key=lambda x: x['num_patients'])
            print(f"\n✅ Maximum sustainable load: {max_load['num_patients']} patients "
                  f"({max_load['alerts_per_second']:.2f} alerts/sec)")
        else:
            print(f"\n⚠️  No test achieved 95% success rate")

if __name__ == "__main__":
    tester = ScalabilityTester()
    tester.run_scalability_test(max_patients=100, step=10, duration_per_step=240)  # 4 minutes per step
