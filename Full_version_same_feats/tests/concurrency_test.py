#!/usr/bin/env python3

import time
import threading
import random
import pandas as pd
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from scapy.all import Ether, sendp, sniff, Packet, IntField, BitField, ShortField, ByteField, bind_layers
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
        IntField("patient_id", 0),
        BitField("timestamp", 0, 48),
        IntField("sepPrediction", 0),
        ByteField("news2Score", 0),
        ByteField("news2Alert", 0),
        IntField("hfPrediction", 0)
    ]

bind_layers(Ether, Sensor, type=0x1235)
bind_layers(Ether, Alert, type=0x1236)

class ConcurrencyTester:
    def __init__(self, send_interface='enx0c37965f8a10', receive_interface='enx0c37965f8a0a'):
        self.send_iface = send_interface
        self.receive_iface = receive_interface
        self.received_alerts = defaultdict(list)
        self.test_active = True
        self.results = {}
        self.patient_id_counter = 1000  # Start at safe range
        self.max_patient_id = 50000     # Maximum allowed patient ID
        
        # Sample patient data for different conditions
        self.sample_data = {
            0: [370, 98, 80, 120, 16, 0, 0, 1, 45, 1],    # Normal
            1: [390, 94, 110, 90, 22, 1, 1, 2, 65, 1],    # Sepsis  
            2: [365, 95, 95, 140, 18, 0, 1, 1, 75, 0]     # Heart failure
        }
        
    def get_next_patient_id_batch(self, num_patients):
        """Get next batch of patient IDs, wrapping around if needed"""
        start_id = self.patient_id_counter
        
        # Check if we'll exceed max_patient_id
        if start_id + num_patients > self.max_patient_id:
            # Wrap around to beginning, but avoid conflict with active tests
            self.patient_id_counter = 1000
            start_id = self.patient_id_counter
            print(f"  🔄 Wrapping patient IDs: starting from {start_id}")
        
        # Generate patient ID list
        patient_ids = list(range(start_id, start_id + num_patients))
        
        # Update counter for next batch
        self.patient_id_counter = start_id + num_patients + 50  # Add buffer
        
        return patient_ids
        
    def send_patient_burst(self, num_patients, condition_mix=True):
        """Send a burst of patients concurrently with safe ID management"""
        def send_single_patient(patient_id):
            try:
                # Choose condition (mix or single)
                if condition_mix:
                    condition = patient_id % 3  # Rotate through conditions
                else:
                    condition = 0  # All normal for speed
                
                values = self.sample_data[condition]
                # Use patient_id in timestamp to ensure uniqueness without overflow
                base_timestamp = int(time.time() * 1000) + (patient_id % 1000)
                
                # Send all 10 sensors rapidly
                for sensor_id in range(10):
                    pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                        patient_id=patient_id,
                        sensor_id=sensor_id,
                        timestamp=base_timestamp + sensor_id,
                        feature_value=values[sensor_id]
                    )
                    sendp(pkt, iface=self.send_iface, verbose=False)
                
                return patient_id
            except Exception as e:
                print(f"Error sending patient {patient_id}: {e}")
                return None
        
        # Get safe patient ID batch
        patient_ids = self.get_next_patient_id_batch(num_patients)
        
        # Use ThreadPoolExecutor for maximum concurrency
        start_time = time.time()
        successful_patients = []
        
        with ThreadPoolExecutor(max_workers=min(num_patients, 100)) as executor:
            # Submit all patient sending tasks
            future_to_patient = {
                executor.submit(send_single_patient, patient_id): patient_id 
                for patient_id in patient_ids
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_patient):
                patient_id = future_to_patient[future]
                try:
                    result = future.result(timeout=5)  # 5 second timeout per patient
                    if result:
                        successful_patients.append(result)
                except Exception as e:
                    print(f"Patient {patient_id} failed: {e}")
        
        send_duration = time.time() - start_time
        return successful_patients, send_duration
    
    def monitor_alerts(self):
        """Monitor alert packets in background"""
        def alert_handler(pkt):
            if not self.test_active:
                return
                
            if pkt.haslayer(Ether) and pkt[Ether].type == 0x1236:
                try:
                    # Fast parsing - prioritize speed over robustness
                    if pkt.haslayer(Alert):
                        alert = pkt[Alert]
                        patient_id = alert.patient_id
                        sep_pred = alert.sepPrediction
                        hf_pred = alert.hfPrediction
                        news2_score = alert.news2Score
                    else:
                        # Quick manual parse
                        payload = bytes(pkt.payload)
                        if len(payload) >= 20:
                            patient_id = struct.unpack('!I', payload[0:4])[0]
                            sep_pred = struct.unpack('!I', payload[10:14])[0]
                            news2_score = payload[14]
                            hf_pred = struct.unpack('!I', payload[16:20])[0]
                        else:
                            return
                    
                    if patient_id > 0:
                        self.received_alerts[patient_id].append({
                            'timestamp': time.time(),
                            'sepsis': sep_pred,
                            'heart_failure': hf_pred,
                            'news2': news2_score
                        })
                        
                except Exception:
                    pass  # Skip errors for speed
        
        try:
            sniff(iface=self.receive_iface, prn=alert_handler, 
                  filter="ether proto 0x1236", store=0)
        except Exception as e:
            print(f"Monitor error: {e}")
    
    def run_concurrency_test(self, start_patients=100, max_patients=10000, step=500):
        """Run fast concurrency test with specified parameters"""
        print("🚀 FAST CONCURRENCY TEST")
        print("=" * 60)
        print(f"Range: {start_patients} to {max_patients} patients (step: {step})")
        print(f"Send interface: {self.send_iface}")
        print(f"Receive interface: {self.receive_iface}")
        print(f"Patient ID range: 1-{self.max_patient_id} (will wrap if needed)")
        
        # Validate that we can handle the test range
        total_patients_needed = sum(range(start_patients, max_patients + 1, step))
        if total_patients_needed > self.max_patient_id * 2:
            print(f"⚠️  Warning: Test needs {total_patients_needed} total patient IDs")
            print(f"   Will reuse IDs with sufficient gaps to avoid conflicts")
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_alerts)
        monitor_thread.daemon = True
        monitor_thread.start()
        time.sleep(2)  # Let monitor start
        
        test_results = []
        
        # Generate test points
        test_points = list(range(start_patients, max_patients + 1, step))
        print(f"Testing {len(test_points)} concurrency levels...")
        
        for i, num_patients in enumerate(test_points):
            print(f"\n📊 Test {i+1}/{len(test_points)}: {num_patients} concurrent patients")
            print(f"  🆔 Patient ID counter at: {self.patient_id_counter}")
            
            # Clear previous alerts for clean measurement
            self.received_alerts.clear()
            
            # Send burst of patients
            start_time = time.time()
            successful_patients, send_duration = self.send_patient_burst(
                num_patients, condition_mix=False  # All normal for speed
            )
            
            print(f"  📤 Sent {len(successful_patients)}/{num_patients} patients in {send_duration:.2f}s")
            print(f"  ⚡ Send rate: {len(successful_patients)/send_duration:.1f} patients/second")
            
            # Wait for alerts (proportional to patient count, but capped)
            wait_time = min(max(10, num_patients * 0.01), 60)  # 10s to 60s max
            print(f"  ⏳ Waiting {wait_time:.1f}s for alerts...")
            
            # Monitor progress during wait
            for remaining in range(int(wait_time), 0, -5):
                time.sleep(5)
                alerts_received = len(self.received_alerts)
                if remaining % 10 == 0:  # Print every 10 seconds
                    print(f"    {remaining}s left... {alerts_received} alerts received")
            
            # Analyze results
            total_time = time.time() - start_time
            alerts_received = len(self.received_alerts)
            success_rate = (alerts_received / len(successful_patients)) * 100 if successful_patients else 0
            
            # Quick prediction analysis
            sepsis_alerts = sum(1 for alerts in self.received_alerts.values() 
                              for alert in alerts if alert['sepsis'] > 0)
            hf_alerts = sum(1 for alerts in self.received_alerts.values() 
                           for alert in alerts if alert['heart_failure'] > 0)
            
            result = {
                'concurrent_patients': num_patients,
                'patients_sent': len(successful_patients),
                'send_duration': send_duration,
                'send_rate': len(successful_patients) / send_duration if send_duration > 0 else 0,
                'alerts_received': alerts_received,
                'total_duration': total_time,
                'success_rate': success_rate,
                'sepsis_alerts': sepsis_alerts,
                'heart_failure_alerts': hf_alerts,
                'throughput': alerts_received / total_time if total_time > 0 else 0
            }
            
            test_results.append(result)
            
            print(f"  ✅ Results: {alerts_received}/{len(successful_patients)} alerts ({success_rate:.1f}% success)")
            print(f"  📈 Throughput: {result['throughput']:.1f} alerts/second")
            
            # Brief cooldown to let system recover
            if num_patients < max_patients:
                print("  😴 Cooling down (3s)...")
                time.sleep(3)
        
        self.test_active = False
        self.save_results(test_results)
        self.print_summary(test_results)
        return test_results
    
    def save_results(self, results):
        """Save concurrency test results"""
        filename = f'concurrency_test_results_{int(time.time())}.csv'
        df = pd.DataFrame(results)
        df.to_csv(filename, index=False)
        print(f"\n💾 Results saved to {filename}")
    
    def print_summary(self, results):
        """Print comprehensive summary"""
        print("\n" + "=" * 80)
        print("🎯 FAST CONCURRENCY TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"{'Patients':<10} {'Sent':<6} {'Alerts':<7} {'Success%':<9} {'Send/s':<8} {'Alerts/s':<9} {'Total(s)':<8}")
        print("-" * 80)
        
        max_success_rate = 0
        max_throughput = 0
        breaking_point = None
        
        for r in results:
            print(f"{r['concurrent_patients']:<10} {r['patients_sent']:<6} {r['alerts_received']:<7} "
                  f"{r['success_rate']:<9.1f} {r['send_rate']:<8.1f} {r['throughput']:<9.1f} {r['total_duration']:<8.1f}")
            
            # Track performance metrics
            if r['success_rate'] > max_success_rate:
                max_success_rate = r['success_rate']
            if r['throughput'] > max_throughput:
                max_throughput = r['throughput']
            
            # Detect breaking point (success rate drops below 80%)
            if r['success_rate'] < 80 and breaking_point is None:
                breaking_point = r['concurrent_patients']
        
        print("=" * 80)
        print(f"🏆 Peak Performance:")
        print(f"  Maximum success rate: {max_success_rate:.1f}%")
        print(f"  Maximum throughput: {max_throughput:.1f} alerts/second")
        
        if breaking_point:
            print(f"⚠️  Performance degradation starts around: {breaking_point} concurrent patients")
        else:
            print(f"✅ System maintained good performance up to {results[-1]['concurrent_patients']} patients")
        
        # System capacity estimate
        stable_results = [r for r in results if r['success_rate'] >= 90]
        if stable_results:
            max_stable = max(r['concurrent_patients'] for r in stable_results)
            print(f"📊 Recommended capacity: Up to {max_stable} concurrent patients (90%+ success)")

def main():
    print("🚀 Fast Concurrency Test Setup")
    print("Testing concurrent patient processing capability")
    print("=" * 50)
    
    # Get test parameters
    start = int(input("Start patient count [100]: ") or "100")
    end = int(input("End patient count [10000]: ") or "10000")  
    step = int(input("Step size [500]: ") or "500")
    
    print(f"\nWill test: {start} to {end} patients in steps of {step}")
    total_tests = len(range(start, end + 1, step))
    estimated_time = total_tests * 0.5  # Rough estimate: 30s per test
    print(f"Total tests: {total_tests}")
    print(f"Estimated duration: {estimated_time/60:.1f} minutes")
    print(f"Patient IDs will be managed within 1-50000 range")
    
    proceed = input("\nProceed? (y/n): ").lower()
    if proceed != 'y':
        print("Test cancelled.")
        return
    
    # Run the test
    tester = ConcurrencyTester()
    results = tester.run_concurrency_test(
        start_patients=start,
        max_patients=end, 
        step=step
    )
    
    print(f"\n🎉 Concurrency test complete!")
    print(f"Tested {len(results)} different concurrency levels")

if __name__ == "__main__":
    main()