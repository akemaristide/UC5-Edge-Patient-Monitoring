#!/usr/bin/env python3
import time
import threading
import csv
import subprocess
import json
import getpass
from scapy.all import *

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

class PerformanceTester:
    def __init__(self, gateway_ip='192.168.1.12', gateway_user='ubuntu', ssh_password='SmartEdge-2023'):
        self.sensor_iface = 'enx0c37965f8a10'
        self.monitor_iface = 'enx0c37965f8a0a'
        self.gateway_ip = gateway_ip
        self.gateway_user = gateway_user
        self.ssh_password = ssh_password
        self.performance_data = []
        self.alerts_received = 0
        self.windows_sent = 0
        self.monitoring_active = True
        self.start_time = None
        
        # Prompt for password if not provided
        if not self.ssh_password:
            self.ssh_password = getpass.getpass(f"Enter SSH password for {gateway_user}@{gateway_ip}: ")
        
    def get_gateway_stats(self):
        """Collect resource statistics from the gateway via SSH with password"""
        try:
            # Check if sshpass is available
            try:
                subprocess.run(['which', 'sshpass'], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                print("ERROR: sshpass not installed. Install with: sudo apt-get install sshpass")
                return {"error": "sshpass not available"}
            
            # SSH command with sshpass
            ssh_cmd = [
                'sshpass', '-p', self.ssh_password,
                'ssh', 
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{self.gateway_user}@{self.gateway_ip}',
                'python3', '-c', '''
import psutil
import json
import subprocess
import os
import time

# System stats
cpu_percent = psutil.cpu_percent(interval=0.1)
memory = psutil.virtual_memory()
disk = psutil.disk_usage("/")
net_stats = psutil.net_io_counters()

# BMv2 process stats
bmv2_stats = {}
try:
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "num_threads"]):
        proc_info = proc.info
        if proc_info["name"] and ("simple_switch" in proc_info["name"] or "bmv2" in proc_info["name"]):
            bmv2_stats["bmv2_pid"] = proc_info["pid"]
            bmv2_stats["bmv2_cpu_percent"] = proc_info["cpu_percent"]
            bmv2_stats["bmv2_memory_mb"] = proc_info["memory_info"].rss / 1024 / 1024 if proc_info["memory_info"] else 0
            bmv2_stats["bmv2_threads"] = proc_info["num_threads"]
            break
except Exception as e:
    bmv2_stats["bmv2_error"] = str(e)

# Check if P4 switch is responsive
p4_responsive = False
try:
    result = subprocess.run(["timeout", "3", "simple_switch_CLI", "--thrift-port", "9090"], 
                          input="help\\n", capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        p4_responsive = True
except:
    pass

# System load
try:
    load_avg = os.getloadavg()
    load_stats = {"load_1min": load_avg[0], "load_5min": load_avg[1], "load_15min": load_avg[2]}
except:
    load_stats = {}

stats = {
    "timestamp": time.time(),
    "system_cpu_percent": cpu_percent,
    "system_memory_percent": memory.percent,
    "system_memory_mb": memory.used / 1024 / 1024,
    "system_memory_available_mb": memory.available / 1024 / 1024,
    "disk_usage_percent": disk.percent,
    "network_bytes_sent": net_stats.bytes_sent,
    "network_bytes_recv": net_stats.bytes_recv,
    "network_packets_sent": net_stats.packets_sent,
    "network_packets_recv": net_stats.packets_recv,
    "p4_switch_responsive": p4_responsive,
    **bmv2_stats,
    **load_stats
}

print(json.dumps(stats))
'''
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            else:
                return {"ssh_error": f"SSH failed: {result.stderr}"}
                
        except Exception as e:
            return {"collection_error": str(e)}
    
    def monitor_alerts(self):
        """Monitor alert packets and count them"""
        def alert_handler(pkt):
            if not self.monitoring_active:
                return
                
            if pkt.haslayer(Ether) and pkt[Ether].type == 0x1236:
                self.alerts_received += 1
        
        sniff(iface=self.monitor_iface, prn=alert_handler, 
              filter="ether proto 0x1236", store=0)
    
    def send_patient_window(self, patient_id, condition=0):
        """Send a patient window based on condition"""
        # Different conditions for testing
        conditions = {
            0: [370, 98, 80, 120, 16, 0, 0, 1, 45, 1],    # Normal
            1: [390, 94, 110, 90, 22, 1, 1, 2, 65, 1],    # Sepsis
            2: [365, 95, 95, 140, 18, 0, 1, 1, 75, 0]     # Heart failure
        }
        
        values = conditions.get(condition, conditions[0])
        base_timestamp = int(time.time() * 1000)
        
        # 90% complete windows, 10% partial for realistic load
        if patient_id % 10 == 0:  # 10% partial
            sensors_to_send = 6  # Partial window
        else:  # 90% complete
            sensors_to_send = 10  # Complete window
        
        for sensor_id in range(sensors_to_send):
            pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                patient_id=patient_id,
                sensor_id=sensor_id,
                timestamp=base_timestamp + sensor_id * 100,
                feature_value=values[sensor_id]  # Fixed variable name
            )
            sendp(pkt, iface=self.sensor_iface, verbose=False)
        
        self.windows_sent += 1
    
    def collect_system_stats(self):
        """Collect gateway performance statistics"""
        while self.monitoring_active:
            current_time = time.time()
            if self.start_time:
                elapsed = current_time - self.start_time
                
                # Get gateway stats via SSH
                gateway_stats = self.get_gateway_stats()
                
                # Host network stats (for comparison)
                try:
                    import psutil
                    net_stats = psutil.net_io_counters(pernic=True)
                    eth0_stats = net_stats.get('enx0c37965f8a0a', None)  # Fixed interface name
                    eth1_stats = net_stats.get('enx0c37965f8a10', None)  # Fixed interface name (removed comma)
                except:
                    eth0_stats = eth1_stats = None
                
                stats = {
                    'timestamp': current_time,
                    'elapsed_seconds': elapsed,
                    'windows_sent': self.windows_sent,
                    'alerts_received': self.alerts_received,
                    'windows_per_second': self.windows_sent / elapsed if elapsed > 0 else 0,
                    'alerts_per_second': self.alerts_received / elapsed if elapsed > 0 else 0,
                    
                    # Gateway system stats
                    'gateway_cpu_percent': gateway_stats.get('system_cpu_percent', 0),
                    'gateway_memory_percent': gateway_stats.get('system_memory_percent', 0),
                    'gateway_memory_mb': gateway_stats.get('system_memory_mb', 0),
                    'gateway_memory_available_mb': gateway_stats.get('system_memory_available_mb', 0),
                    'gateway_disk_percent': gateway_stats.get('disk_usage_percent', 0),
                    'gateway_load_1min': gateway_stats.get('load_1min', 0),
                    'gateway_load_5min': gateway_stats.get('load_5min', 0),
                    
                    # BMv2 process stats
                    'bmv2_cpu_percent': gateway_stats.get('bmv2_cpu_percent', 0),
                    'bmv2_memory_mb': gateway_stats.get('bmv2_memory_mb', 0),
                    'bmv2_pid': gateway_stats.get('bmv2_pid', 0),
                    'bmv2_threads': gateway_stats.get('bmv2_threads', 0),
                    'bmv2_process_name': gateway_stats.get('bmv2_process_name', ''),
                    
                    # P4 switch responsiveness
                    'p4_switch_responsive': gateway_stats.get('p4_switch_responsive', False),
                    
                    # Gateway network stats (all interfaces)
                    'gateway_total_bytes_sent': gateway_stats.get('network_bytes_sent', 0),
                    'gateway_total_bytes_recv': gateway_stats.get('network_bytes_recv', 0),
                    'gateway_total_packets_sent': gateway_stats.get('network_packets_sent', 0),
                    'gateway_total_packets_recv': gateway_stats.get('network_packets_recv', 0),
                    
                    # Host network stats (for reference)
                    'host_eth0_rx_packets': eth0_stats.packets_recv if eth0_stats else 0,
                    'host_eth0_tx_packets': eth0_stats.packets_sent if eth0_stats else 0,
                    'host_eth1_rx_packets': eth1_stats.packets_recv if eth1_stats else 0,
                    'host_eth1_tx_packets': eth1_stats.packets_sent if eth1_stats else 0,
                    
                    # Error tracking
                    'gateway_stats_errors': len([k for k in gateway_stats.keys() if 'error' in k])
                }
                
                # Add per-interface gateway stats if available
                for key, value in gateway_stats.items():
                    if any(iface in key for iface in ['eth', 'ens', 'enp']) and 'bytes' in key:
                        stats[f'gateway_{key}'] = value
                
                self.performance_data.append(stats)
            
            time.sleep(1)  # Collect stats every second
    
    def run_performance_test(self, target_rates=[10, 20, 40, 80, 160, 320, 640, 1280, 2000], duration_per_rate=120):
        """Test different patient rates"""
        print(f"=== Performance Test: Testing rates {target_rates} patients/min ===")
        print(f"Gateway: {self.gateway_ip}, User: {self.gateway_user}")
        
        results = []
        
        for rate in target_rates:
            print(f"\nTesting {rate} patients/minute for {duration_per_rate} seconds...")
            
            # Reset counters
            self.alerts_received = 0
            self.windows_sent = 0
            self.performance_data = []
            self.monitoring_active = True
            self.start_time = time.time()
            
            # Start monitoring threads
            alert_thread = threading.Thread(target=self.monitor_alerts)
            stats_thread = threading.Thread(target=self.collect_system_stats)
            alert_thread.daemon = True
            stats_thread.daemon = True
            alert_thread.start()
            stats_thread.start()
            
            # Send patients at target rate
            patient_id = 20000 + (rate * 10)  # Unique ID range per rate
            interval = 60.0 / rate    # Seconds between patients
            
            test_end_time = time.time() + duration_per_rate
            
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
            time.sleep(30)
            self.monitoring_active = False
            
            # Calculate results for this rate
            total_time = time.time() - self.start_time
            actual_rate = (self.windows_sent / total_time) * 60  # per minute
            alert_rate = (self.alerts_received / self.windows_sent) * 100 if self.windows_sent > 0 else 0
            
            # Calculate averages from collected data
            if self.performance_data:
                avg_gateway_cpu = sum(d['gateway_cpu_percent'] for d in self.performance_data) / len(self.performance_data)
                max_gateway_cpu = max(d['gateway_cpu_percent'] for d in self.performance_data)
                avg_gateway_memory = sum(d['gateway_memory_mb'] for d in self.performance_data) / len(self.performance_data)
                avg_bmv2_cpu = sum(d['bmv2_cpu_percent'] for d in self.performance_data if d['bmv2_cpu_percent']) / max(1, len([d for d in self.performance_data if d['bmv2_cpu_percent']]))
                avg_bmv2_memory = sum(d['bmv2_memory_mb'] for d in self.performance_data if d['bmv2_memory_mb']) / max(1, len([d for d in self.performance_data if d['bmv2_memory_mb']]))
                p4_responsive_rate = sum(1 for d in self.performance_data if d['p4_switch_responsive']) / len(self.performance_data) * 100
                gateway_errors = sum(d['gateway_stats_errors'] for d in self.performance_data)
            else:
                avg_gateway_cpu = max_gateway_cpu = avg_gateway_memory = 0
                avg_bmv2_cpu = avg_bmv2_memory = p4_responsive_rate = gateway_errors = 0
            
            rate_result = {
                'target_rate': rate,
                'actual_rate': actual_rate,
                'windows_sent': self.windows_sent,
                'alerts_received': self.alerts_received,
                'alert_rate_percent': alert_rate,
                'duration_seconds': total_time,
                'avg_gateway_cpu_percent': avg_gateway_cpu,
                'max_gateway_cpu_percent': max_gateway_cpu,
                'avg_gateway_memory_mb': avg_gateway_memory,
                'avg_bmv2_cpu_percent': avg_bmv2_cpu,
                'avg_bmv2_memory_mb': avg_bmv2_memory,
                'p4_responsive_rate_percent': p4_responsive_rate,
                'gateway_stats_errors': gateway_errors
            }
            
            results.append(rate_result)
            
            print(f"Rate {rate}: {actual_rate:.1f} actual, {alert_rate:.1f}% alerts")
            print(f"  Gateway CPU: {avg_gateway_cpu:.1f}% avg, {max_gateway_cpu:.1f}% max")
            print(f"  BMv2 CPU: {avg_bmv2_cpu:.1f}%, Memory: {avg_bmv2_memory:.1f}MB")
            print(f"  P4 Responsive: {p4_responsive_rate:.1f}%")
            
            # Save detailed data for this rate
            self.save_rate_data(rate)
            
            # Cool down between rates
            time.sleep(10)
        
        self.save_summary_results(results)
        self.print_results(results)
        return results
    
    def save_rate_data(self, rate):
        """Save detailed performance data for one rate"""
        filename = f'performance_rate_{rate}_{int(time.time())}.csv'
        
        if self.performance_data:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.performance_data[0].keys())
                writer.writeheader()
                writer.writerows(self.performance_data)
        
        print(f"Detailed data saved to {filename}")
    
    def save_summary_results(self, results):
        """Save summary results for plotting"""
        filename = f'performance_summary_{int(time.time())}.csv'
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        
        print(f"Summary results saved to {filename}")
        return filename
    
    def print_results(self, results):
        """Print formatted results with gateway stats"""
        print("\n" + "="*90)
        print("PERFORMANCE TEST RESULTS (Gateway Monitoring)")
        print("="*90)
        print(f"{'Target':<8} {'Actual':<8} {'Windows':<8} {'Alerts':<8} {'Rate%':<8} {'GW CPU%':<8} {'BMv2 CPU%':<10} {'P4 Resp%':<8}")
        print("-" * 90)
        
        for r in results:
            print(f"{r['target_rate']:<8} {r['actual_rate']:<8.1f} {r['windows_sent']:<8} "
                  f"{r['alerts_received']:<8} {r['alert_rate_percent']:<8.1f} "
                  f"{r['avg_gateway_cpu_percent']:<8.1f} {r['avg_bmv2_cpu_percent']:<10.1f} "
                  f"{r['p4_responsive_rate_percent']:<8.1f}")
        
        print("="*90)
        print("GW = Gateway, BMv2 = P4 switch process, P4 Resp = P4 switch responsiveness")
        
        # Could increase to test much larger scales
        tester.run_scalability_test(
            max_patients=1000,    # Test up to 1000 concurrent patients
            step=50,              # Increment by 50
            duration_per_step=300 # 5 minutes per step
        )

        # Or even larger for stress testing
        tester.run_scalability_test(
            max_patients=5000,    # Stress test with 5000 patients
            step=100,             # Increment by 100  
            duration_per_step=180 # 3 minutes per step (shorter for time)
        )

if __name__ == "__main__":
    # Configure your gateway details
    tester = PerformanceTester(
        gateway_ip='192.168.1.12',  # Your gateway IP
        gateway_user='ubuntu',      # Your gateway SSH user
        ssh_password='SmartEdge-2023'
    )
    tester.run_performance_test(target_rates=[10, 20, 40, 80, 160, 320, 640, 1280, 2000], duration_per_rate=120)
