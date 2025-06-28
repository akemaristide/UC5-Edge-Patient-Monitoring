#!/usr/bin/env python3
import psutil
import json
import time
import threading
import subprocess
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class GatewayStatsServer:
    def __init__(self, port=8080):
        self.port = port
        self.current_stats = {}
        self.monitoring = False
        
    def collect_stats(self):
        """Collect comprehensive gateway stats locally"""
        try:
            # System stats - direct and fast
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            load_avg = os.getloadavg()
            
            # BMv2 process stats - direct access
            bmv2_stats = {}
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                if 'simple_switch' in proc.info['name']:
                    bmv2_stats = {
                        'bmv2_cpu_percent': proc.info['cpu_percent'],
                        'bmv2_memory_mb': proc.info['memory_info'].rss / 1024 / 1024,
                        'bmv2_pid': proc.info['pid']
                    }
                    break
            
            # P4 switch responsiveness - direct check
            p4_responsive = False
            try:
                result = subprocess.run(['timeout', '2', 'simple_switch_CLI', '--thrift-port', '9090'],
                                      input='help\n', capture_output=True, text=True, timeout=3)
                p4_responsive = result.returncode == 0
            except:
                pass
            
            return {
                'timestamp': time.time(),
                'system_cpu_percent': cpu_percent,
                'system_memory_percent': memory.percent,
                'system_memory_mb': memory.used / 1024 / 1024,
                'load_1min': load_avg[0],
                'load_5min': load_avg[1],
                'p4_switch_responsive': p4_responsive,
                **bmv2_stats
            }
            
        except Exception as e:
            return {'error': str(e), 'timestamp': time.time()}
    
    def stats_updater(self):
        """Update stats every second"""
        while self.monitoring:
            self.current_stats = self.collect_stats()
            time.sleep(1)  # Much faster than SSH allows!
    
    def start_server(self):
        """Start HTTP stats server"""
        self.monitoring = True
        stats_thread = threading.Thread(target=self.stats_updater)
        stats_thread.daemon = True
        stats_thread.start()
        
        class StatsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(outer_self.current_stats).encode())
                
            def log_message(self, format, *args):
                pass  # Suppress HTTP logs
        
        outer_self = self
        httpd = HTTPServer(('0.0.0.0', self.port), StatsHandler)
        print(f"Gateway stats server running on port {self.port}")
        httpd.serve_forever()

if __name__ == "__main__":
    server = GatewayStatsServer(port=8080)
    server.start_server()