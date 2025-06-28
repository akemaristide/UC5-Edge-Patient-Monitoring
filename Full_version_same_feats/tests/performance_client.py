#!/usr/bin/env python3
import requests
import time
import threading
import csv
import random
from scapy.all import *
from collections import defaultdict

# Define packet structures
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

# Bind packet types to EtherTypes
bind_layers(Ether, Sensor, type=0x1235)
bind_layers(Ether, Alert, type=0x1236)

class PerformanceClient:
    def __init__(self, gateway_ip='192.168.1.12', stats_port=8080):
        self.gateway_ip = gateway_ip
        self.stats_url = f"http://{gateway_ip}:{stats_port}"
        self.gateway_stats_history = []
        
        # Network interfaces
        self.sensor_iface = 'enx0c37965f8a10'
        self.monitor_iface = 'enx0c37965f8a0a'
        
        # Performance tracking
        self.alerts_received = 0
        self.windows_sent = 0
        self.monitoring_active = True
        self.start_time = None
        
        # Sample patient data for different conditions
        self.sample_data = {
            0: [370, 98, 80, 120, 16, 0, 0, 1, 45, 1],    # Normal
            1: [390, 94, 110, 90, 22, 1, 1, 2, 65, 1],    # Sepsis
            2: [365, 95, 95, 140, 18, 0, 1, 1, 75, 0]     # Heart failure
        }
        
    def get_gateway_stats(self):
        """Get current gateway stats via HTTP - much simpler!"""
        try:
            response = requests.get(self.stats_url, timeout=5)
            if response.status_code == 200:
                stats = response.json()
                print(f"📊 Gateway: CPU={stats.get('system_cpu_percent', 0):.1f}%, "
                      f"Mem={stats.get('system_memory_percent', 0):.1f}%, "
                      f"BMv2 CPU={stats.get('bmv2_cpu_percent', 0):.1f}%")
                return stats
            else:
                return {'http_error': f"Status {response.status_code}"}
        except Exception as e:
            return {'connection_error': str(e)}
    
    def test_gateway_connection(self):
        """Test if gateway stats server is accessible"""
        try:
            stats = self.get_gateway_stats()
            if 'error' not in stats and 'timestamp' in stats:
                print(f"✅ Gateway stats server accessible at {self.stats_url}")
                return True
            else:
                print(f"❌ Gateway stats server error: {stats}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to gateway stats server: {e}")
            return False
    
    def send_patient_window(self, patient_id, condition=0):
        """Send a patient window based on condition"""
        values = self.sample_data.get(condition, self.sample_data[0])
        base_timestamp = int(time.time() * 1000)
        
        # 90% complete windows, 10% partial for realistic load
        if patient_id % 10 == 0:  # 10% partial
            sensors_to_send = 6  # Partial window
        else:  # 90% complete
            sensors_to_send = 10  # Complete window
        
        try:
            for sensor_id in range(sensors_to_send):
                pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                    patient_id=patient_id,
                    sensor_id=sensor_id,
                    timestamp=base_timestamp + sensor_id * 100,
                    feature_value=values[sensor_id]
                )
                sendp(pkt, iface=self.sensor_iface, verbose=False)
                time.sleep(0.01)  # 10ms between sensors
            
            self.windows_sent += 1
            if self.windows_sent % 100 == 0:  # Progress indicator
                print(f"📤 Sent {self.windows_sent} patient windows so far...")
                
        except Exception as e:
            print(f"❌ Error sending patient {patient_id}: {e}")
    
    def monitor_alerts(self):
        """Monitor alert packets and count them"""
        def alert_handler(pkt):
            if not self.monitoring_active:
                return
                
            if pkt.haslayer(Ether) and pkt[Ether].type == 0x1236:
                self.alerts_received += 1
                if self.alerts_received % 10 == 0:  # Progress indicator
                    print(f"📨 Received {self.alerts_received} alerts so far...")
        
        try:
            sniff(iface=self.monitor_iface, prn=alert_handler, 
                  filter="ether proto 0x1236", store=0)
        except Exception as e:
            print(f"❌ Alert monitoring error: {e}")
    
    def collect_performance_data(self):
        """Collect performance data including gateway stats"""
        performance_data = []
        
        while self.monitoring_active:
            current_time = time.time()
            if self.start_time:
                elapsed = current_time - self.start_time
                
                # Get gateway stats via HTTP (much faster than SSH!)
                gateway_stats = self.get_gateway_stats()
                
                stats = {
                    'timestamp': current_time,
                    'elapsed_seconds': elapsed,
                    'windows_sent': self.windows_sent,
                    'alerts_received': self.alerts_received,
                    'windows_per_second': self.windows_sent / elapsed if elapsed > 0 else 0,
                    'alerts_per_second': self.alerts_received / elapsed if elapsed > 0 else 0,
                    
                    # Gateway system stats via HTTP
                    'gateway_cpu_percent': gateway_stats.get('system_cpu_percent', 0),
                    'gateway_memory_percent': gateway_stats.get('system_memory_percent', 0),
                    'gateway_memory_mb': gateway_stats.get('system_memory_mb', 0),
                    'gateway_load_1min': gateway_stats.get('load_1min', 0),
                    'gateway_load_5min': gateway_stats.get('load_5min', 0),
                    
                    # BMv2 process stats
                    'bmv2_cpu_percent': gateway_stats.get('bmv2_cpu_percent', 0),
                    'bmv2_memory_mb': gateway_stats.get('bmv2_memory_mb', 0),
                    'bmv2_pid': gateway_stats.get('bmv2_pid', 0),
                    
                    # P4 switch responsiveness
                    'p4_switch_responsive': gateway_stats.get('p4_switch_responsive', False),
                    
                    # Connection status
                    'gateway_connection_ok': 'error' not in gateway_stats
                }
                
                performance_data.append(stats)
                self.gateway_stats_history.append(stats)
            
            time.sleep(2)  # Collect stats every 2 seconds
        
        return performance_data
    
    def run_performance_test(self, target_rates=[10, 20, 40, 80, 160, 320], duration_per_rate=120):
        """Test different patient rates with HTTP-based gateway monitoring"""
        print(f"=== Performance Test with HTTP Gateway Monitoring ===")
        print(f"Gateway: {self.gateway_ip}, Stats URL: {self.stats_url}")
        
        # Test gateway connection
        if not self.test_gateway_connection():
            response = input("\nContinue without gateway monitoring? (y/n): ")
            if response.lower() != 'y':
                print("Test cancelled. Start performance_server.py on gateway and try again.")
                return []
        
        results = []
        
        for rate in target_rates:
            print(f"\n{'='*60}")
            print(f"🧪 Testing {rate} patients/minute for {duration_per_rate} seconds...")
            print(f"Expected: {rate * duration_per_rate / 60:.0f} total patients")
            
            # Reset counters
            self.alerts_received = 0
            self.windows_sent = 0
            self.monitoring_active = True
            self.start_time = time.time()
            
            # Start monitoring threads
            alert_thread = threading.Thread(target=self.monitor_alerts)
            stats_thread = threading.Thread(target=self.collect_performance_data)
            alert_thread.daemon = True
            stats_thread.daemon = True
            alert_thread.start()
            stats_thread.start()
            
            # Send patients at target rate
            patient_id = 20000 + (rate * 10)  # Unique ID range per rate
            interval = 60.0 / rate    # Seconds between patients
            
            test_end_time = time.time() + duration_per_rate
            
            print(f"🚀 Starting patient transmission (interval: {interval:.3f}s between patients)...")
            
            while time.time() < test_end_time:
                send_start = time.time()
                
                # Mix of conditions
                condition = patient_id % 3
                self.send_patient_window(patient_id, condition)
                patient_id += 1
                
                # Rate limiting
                elapsed = time.time() - send_start
                if elapsed < interval:
                    time.sleep(interval - elapsed)
            
            # Wait for final alerts
            print("⏳ Waiting for final alerts (30 seconds)...")
            time.sleep(30)
            self.monitoring_active = False
            
            # Calculate results for this rate
            total_time = time.time() - self.start_time
            actual_rate = (self.windows_sent / total_time) * 60  # per minute
            alert_rate = (self.alerts_received / self.windows_sent) * 100 if self.windows_sent > 0 else 0
            
            # Calculate averages from collected data
            if self.gateway_stats_history:
                recent_stats = self.gateway_stats_history[-min(10, len(self.gateway_stats_history)):]
                avg_gateway_cpu = sum(d['gateway_cpu_percent'] for d in recent_stats) / len(recent_stats)
                max_gateway_cpu = max(d['gateway_cpu_percent'] for d in recent_stats)
                avg_bmv2_cpu = sum(d['bmv2_cpu_percent'] for d in recent_stats if d['bmv2_cpu_percent']) / max(1, len([d for d in recent_stats if d['bmv2_cpu_percent']]))
                avg_bmv2_memory = sum(d['bmv2_memory_mb'] for d in recent_stats if d['bmv2_memory_mb']) / max(1, len([d for d in recent_stats if d['bmv2_memory_mb']]))
                connection_success_rate = sum(1 for d in recent_stats if d['gateway_connection_ok']) / len(recent_stats) * 100
            else:
                avg_gateway_cpu = max_gateway_cpu = avg_bmv2_cpu = avg_bmv2_memory = connection_success_rate = 0
            
            rate_result = {
                'target_rate': rate,
                'actual_rate': actual_rate,
                'windows_sent': self.windows_sent,
                'alerts_received': self.alerts_received,
                'alert_rate_percent': alert_rate,
                'duration_seconds': total_time,
                'avg_gateway_cpu_percent': avg_gateway_cpu,
                'max_gateway_cpu_percent': max_gateway_cpu,
                'avg_bmv2_cpu_percent': avg_bmv2_cpu,
                'avg_bmv2_memory_mb': avg_bmv2_memory,
                'gateway_connection_success_rate': connection_success_rate
            }
            
            results.append(rate_result)
            
            print(f"\n📊 Results for {rate} patients/min:")
            print(f"  📤 Sent: {self.windows_sent} windows ({actual_rate:.1f} actual rate)")
            print(f"  📨 Received: {self.alerts_received} alerts ({alert_rate:.1f}% success)")
            print(f"  🖥️  Gateway CPU: {avg_gateway_cpu:.1f}% avg, {max_gateway_cpu:.1f}% max")
            print(f"  🔧 BMv2 Process: {avg_bmv2_cpu:.1f}% CPU, {avg_bmv2_memory:.1f}MB memory")
            print(f"  🔗 HTTP Connection: {connection_success_rate:.1f}% success")
            
            # Save detailed data for this rate
            self.save_rate_data(rate)
            
            # Cool down between rates
            print("😴 Cooling down (10 seconds)...")
            time.sleep(10)
        
        self.save_summary_results(results)
        self.print_results(results)
        return results
    
    def save_rate_data(self, rate):
        """Save detailed performance data for one rate"""
        filename = f'performance_rate_{rate}_{int(time.time())}.csv'
        
        if self.gateway_stats_history:
            with open(filename, 'w', newline='') as f:
                fieldnames = self.gateway_stats_history[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.gateway_stats_history)
            print(f"💾 Detailed data saved to {filename}")
    
    def save_summary_results(self, results):
        """Save summary results for plotting"""
        filename = f'performance_summary_{int(time.time())}.csv'
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        
        print(f"💾 Summary results saved to {filename}")
        return filename
    
    def print_results(self, results):
        """Print formatted results"""
        print("\n" + "="*80)
        print("PERFORMANCE TEST RESULTS (HTTP Gateway Monitoring)")
        print("="*80)
        print(f"{'Target':<8} {'Actual':<8} {'Windows':<8} {'Alerts':<8} {'Rate%':<8} {'GW CPU%':<8} {'BMv2 CPU%':<10} {'HTTP%':<6}")
        print("-" * 80)
        
        for r in results:
            print(f"{r['target_rate']:<8} {r['actual_rate']:<8.1f} {r['windows_sent']:<8} "
                  f"{r['alerts_received']:<8} {r['alert_rate_percent']:<8.1f} "
                  f"{r['avg_gateway_cpu_percent']:<8.1f} {r['avg_bmv2_cpu_percent']:<10.1f} "
                  f"{r['gateway_connection_success_rate']:<6.1f}")
        
        print("="*80)

if __name__ == "__main__":
    # Configure your gateway details
    print("🔧 Performance Test Setup (Split Architecture)")
    print("=" * 50)
    
    gateway_ip = input("Gateway IP [192.168.1.12]: ").strip() or "192.168.1.12"
    stats_port = input("Stats server port [8080]: ").strip() or "8080"
    
    print(f"\nConnecting to gateway stats at http://{gateway_ip}:{stats_port}")
    print("Make sure performance_server.py is running on the gateway!")
    
    client = PerformanceClient(
        gateway_ip=gateway_ip,
        stats_port=int(stats_port)
    )
    
    print("\nStarting performance test with HTTP monitoring...")
    client.run_performance_test(
        target_rates=[10, 20, 40, 80, 160, 320],
        duration_per_rate=120
    )