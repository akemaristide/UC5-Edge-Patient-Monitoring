#!/usr/bin/env python3

import time
import threading
import random
import pandas as pd
import numpy as np
import struct
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from scapy.all import Ether, sendp, sniff, Packet, IntField, BitField, ShortField, ByteField, bind_layers

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

class Patient:
    """Represents a hospital patient with realistic vital sign patterns"""
    def __init__(self, patient_id, condition_type, admission_time, severity='moderate'):
        self.patient_id = patient_id
        self.condition_type = condition_type  # 0=Normal, 1=Sepsis, 2=Heart Failure
        self.severity = severity  # mild, moderate, severe
        self.admission_time = admission_time
        self.is_active = True
        self.last_transmission = None
        self.vital_history = deque(maxlen=200)  # Keep last 200 readings for 24h
        self.deterioration_trend = 0  # -1=improving, 0=stable, 1=deteriorating
        self.missing_sensor_probability = 0.05  # 5% base chance of missing sensors
        self.hours_since_admission = 0
        self.treatment_response_time = random.randint(4, 12)  # Hours until treatment response
        
        # Initialize baseline vitals based on condition and severity
        self.initialize_vitals()
    
    def initialize_vitals(self):
        """Initialize patient vitals based on their condition and severity"""
        severity_multiplier = {'mild': 0.7, 'moderate': 1.0, 'severe': 1.3}[self.severity]
        
        if self.condition_type == 0:  # Normal patient
            self.baseline_vitals = {
                'temperature': random.randint(365, 375),  # 36.5-37.5°C
                'oxygen_saturation': random.randint(96, 99),
                'pulse_rate': random.randint(60, 100),
                'systolic_bp': random.randint(110, 140),
                'respiratory_rate': random.randint(12, 20),
                'avpu': 0,  # Alert
                'supplemental_oxygen': 0,
                'referral_source': random.randint(0, 3),
                'age': random.randint(20, 80),
                'sex': random.randint(0, 1)
            }
        elif self.condition_type == 1:  # Sepsis patient
            base_temp = 355 + int((395-355) * severity_multiplier)
            self.baseline_vitals = {
                'temperature': random.randint(max(300, base_temp-20), min(420, base_temp+20)),
                'oxygen_saturation': random.randint(max(75, 96 - int(8 * severity_multiplier)), 96),
                'pulse_rate': random.randint(90, min(160, 130 + int(30 * severity_multiplier))),
                'systolic_bp': random.randint(max(60, 110 - int(30 * severity_multiplier)), 110),
                'respiratory_rate': random.randint(20, min(40, 30 + int(10 * severity_multiplier))),
                'avpu': random.randint(0, min(2, int(2 * severity_multiplier))),
                'supplemental_oxygen': random.randint(0, 1),
                'referral_source': random.randint(1, 3),
                'age': random.randint(40, 85),
                'sex': random.randint(0, 1)
            }
        else:  # Heart failure patient
            self.baseline_vitals = {
                'temperature': random.randint(365, 380),
                'oxygen_saturation': random.randint(max(80, 94 - int(6 * severity_multiplier)), 94),
                'pulse_rate': random.randint(80, min(140, 120 + int(20 * severity_multiplier))),
                'systolic_bp': random.randint(90, min(180, 160 + int(20 * severity_multiplier))),
                'respiratory_rate': random.randint(18, min(35, 26 + int(9 * severity_multiplier))),
                'avpu': 0,
                'supplemental_oxygen': random.randint(0, 1),
                'referral_source': random.randint(1, 2),
                'age': random.randint(50, 90),
                'sex': random.randint(0, 1)
            }
    
    def evolve_condition(self, hours_elapsed):
        """Simulate realistic patient condition evolution over 24 hours"""
        self.hours_since_admission = hours_elapsed
        
        # Different evolution patterns for different conditions
        if self.condition_type == 1:  # Sepsis - can have rapid changes
            if hours_elapsed < 6:  # Initial deterioration phase
                if random.random() < 0.4:
                    self.deterioration_trend = 1
            elif hours_elapsed < self.treatment_response_time:  # Critical phase
                if random.random() < 0.6:
                    self.deterioration_trend = 1
                elif random.random() < 0.2:
                    self.deterioration_trend = -1
            else:  # Treatment response phase
                if random.random() < 0.7:
                    self.deterioration_trend = -1  # Improving
                elif random.random() < 0.2:
                    self.deterioration_trend = 0   # Stable
                else:
                    self.deterioration_trend = 1   # Still deteriorating
                    
        elif self.condition_type == 2:  # Heart failure - more gradual
            if hours_elapsed < 8:
                if random.random() < 0.3:
                    self.deterioration_trend = random.choice([-1, 1])
            elif hours_elapsed < 16:
                if random.random() < 0.4:
                    self.deterioration_trend = -1  # Treatment effect
            else:  # Later phase
                if random.random() < 0.2:
                    self.deterioration_trend = random.choice([-1, 0, 1])
        
        # Adjust missing sensor probability based on condition and time
        base_probability = {'mild': 0.03, 'moderate': 0.05, 'severe': 0.08}[self.severity]
        
        if self.deterioration_trend == 1:  # Deteriorating
            self.missing_sensor_probability = min(0.20, base_probability + 0.05)
        elif self.deterioration_trend == -1:  # Improving
            self.missing_sensor_probability = max(0.01, base_probability - 0.02)
        else:  # Stable
            self.missing_sensor_probability = base_probability
            
        # Night shift has slightly higher sensor issues
        current_hour = (self.admission_time + timedelta(hours=hours_elapsed)).hour
        if 22 <= current_hour or current_hour <= 6:
            self.missing_sensor_probability *= 1.3
    
    def get_current_vitals(self):
        """Generate current vital signs with realistic 24-hour variation"""
        current_vitals = {}
        
        # Circadian rhythm effects
        current_hour = (self.admission_time + timedelta(hours=self.hours_since_admission)).hour
        circadian_factor = 1.0
        if 2 <= current_hour <= 6:  # Early morning dip
            circadian_factor = 0.95
        elif 10 <= current_hour <= 14:  # Midday peak
            circadian_factor = 1.05
        
        for vital, baseline in self.baseline_vitals.items():
            if vital in ['age', 'sex']:  # These don't change
                current_vitals[vital] = baseline
                continue
            
            # Add realistic variation with circadian effects
            if vital == 'temperature':
                variation = random.randint(-8, 8)
                if self.deterioration_trend == 1:
                    variation += random.randint(0, 15)  # Fever spike
                variation = int(variation * circadian_factor)
                
            elif vital == 'oxygen_saturation':
                variation = random.randint(-4, 3)
                if self.deterioration_trend == 1:
                    variation -= random.randint(0, 8)  # Desaturation
                    
            elif vital == 'pulse_rate':
                variation = random.randint(-15, 15)
                if self.deterioration_trend == 1:
                    variation += random.randint(0, 25)  # Tachycardia
                variation = int(variation * circadian_factor)
                
            elif vital == 'systolic_bp':
                variation = random.randint(-8, 8)
                if self.deterioration_trend == 1 and self.condition_type == 1:
                    variation -= random.randint(0, 20)  # Hypotension
                variation = int(variation * circadian_factor)
                
            elif vital == 'respiratory_rate':
                variation = random.randint(-3, 3)
                if self.deterioration_trend == 1:
                    variation += random.randint(0, 8)  # Tachypnea
                variation = int(variation * circadian_factor)
                
            elif vital == 'avpu':
                if self.deterioration_trend == 1 and random.random() < 0.1:
                    variation = 1  # Occasional confusion
                else:
                    variation = 0
            else:
                variation = 0
            
            current_vitals[vital] = max(0, baseline + variation)
        
        # Store in history
        self.vital_history.append(current_vitals.copy())
        return current_vitals

class TwentyFourHourTester:
    def __init__(self, send_interface='enx0c37965f8a10', receive_interface='enx0c37965f8a0a'):
        self.send_iface = send_interface
        self.receive_iface = receive_interface
        self.test_active = True
        self.start_time = None
        self.duration_hours = 24
        
        # Patient management with realistic ICU parameters
        self.active_patients = {}
        self.patient_id_counter = 1000
        self.max_concurrent_patients = 75  # Higher for 24h test
        
        # Enhanced ICU simulation parameters for 24h
        self.base_admission_rate = 2.2   # patients per hour on average
        self.base_discharge_rate = 2.0   # patients per hour on average
        self.transmission_interval = 60  # seconds between vital sign updates
        self.current_admission_rate = self.base_admission_rate
        self.current_discharge_rate = self.base_discharge_rate
        
        # Results tracking
        self.total_admissions = 0
        self.total_discharges = 0
        self.total_transmissions = 0
        self.total_alerts = 0
        self.received_alerts = defaultdict(list)
        self.hourly_stats = []
        self.system_events = []
        
        # Enhanced performance monitoring for 24h
        self.performance_metrics = {
            'hourly_patients': [],
            'hourly_transmissions': [],
            'hourly_alerts': [],
            'response_times': deque(maxlen=1000),  # Keep last 1000 for memory efficiency
            'error_count': 0,
            'shift_patterns': {
                'day': {'admissions': 0, 'discharges': 0, 'alerts': 0},
                'evening': {'admissions': 0, 'discharges': 0, 'alerts': 0},
                'night': {'admissions': 0, 'discharges': 0, 'alerts': 0}
            }
        }
        
        # Critical event tracking
        self.critical_events = []
        self.system_overload_events = []
        
    def get_shift(self, hour):
        """Determine hospital shift based on hour"""
        if 7 <= hour < 19:
            return 'day'
        elif 19 <= hour < 23:
            return 'evening'
        else:
            return 'night'
    
    def update_activity_rates(self, current_hour):
        """Update admission/discharge rates based on realistic hospital patterns"""
        # Day shift (7-19): High activity
        if 7 <= current_hour < 19:
            self.current_admission_rate = self.base_admission_rate * 1.3
            self.current_discharge_rate = self.base_discharge_rate * 1.4
        # Evening shift (19-23): Moderate activity
        elif 19 <= current_hour < 23:
            self.current_admission_rate = self.base_admission_rate * 0.9
            self.current_discharge_rate = self.base_discharge_rate * 0.8
        # Night shift (23-7): Lower activity
        else:
            self.current_admission_rate = self.base_admission_rate * 0.6
            self.current_discharge_rate = self.base_discharge_rate * 0.5
    
    def log_event(self, event_type, message, is_critical=False):
        """Log system events with timestamp and criticality"""
        timestamp = datetime.now()
        hours_elapsed = (timestamp - self.start_time).total_seconds() / 3600 if self.start_time else 0
        current_hour = timestamp.hour
        shift = self.get_shift(current_hour)
        
        event = {
            'timestamp': timestamp,
            'hours_elapsed': hours_elapsed,
            'type': event_type,
            'message': message,
            'shift': shift,
            'is_critical': is_critical
        }
        self.system_events.append(event)
        
        if is_critical:
            self.critical_events.append(event)
            print(f"🚨 [{hours_elapsed:5.1f}h] CRITICAL {event_type}: {message}")
        else:
            print(f"[{hours_elapsed:5.1f}h] {event_type}: {message}")
    
    def admit_patient(self):
        """Admit a new patient with realistic severity distribution"""
        if len(self.active_patients) >= self.max_concurrent_patients:
            self.log_event('CAPACITY', f"ICU at capacity ({self.max_concurrent_patients} patients)", True)
            return None
        
        patient_id = self.patient_id_counter
        self.patient_id_counter += 1
        
        # Realistic condition distribution in ICU over 24h
        condition_weights = [0.35, 0.40, 0.25]  # Normal, Sepsis, Heart Failure
        condition_type = np.random.choice([0, 1, 2], p=condition_weights)
        
        # Realistic severity distribution
        severity_weights = [0.4, 0.45, 0.15]  # Mild, Moderate, Severe
        severity = np.random.choice(['mild', 'moderate', 'severe'], p=severity_weights)
        
        patient = Patient(patient_id, condition_type, datetime.now(), severity)
        self.active_patients[patient_id] = patient
        self.total_admissions += 1
        
        # Track by shift
        shift = self.get_shift(datetime.now().hour)
        self.performance_metrics['shift_patterns'][shift]['admissions'] += 1
        
        condition_names = ['Normal', 'Sepsis', 'Heart Failure']
        self.log_event('ADMISSION', 
                      f"Patient {patient_id} admitted ({condition_names[condition_type]}, {severity})")
        
        return patient
    
    def discharge_patient(self):
        """Discharge a patient with realistic length-of-stay considerations"""
        if not self.active_patients:
            return
        
        # Prioritize patients based on length of stay and condition improvement
        discharge_candidates = []
        for patient_id, patient in self.active_patients.items():
            hours_stayed = (datetime.now() - patient.admission_time).total_seconds() / 3600
            
            # Discharge probability based on stay length and condition
            discharge_prob = 0
            if hours_stayed > 48:  # Long stay - high discharge probability
                discharge_prob = 0.8
            elif hours_stayed > 24:  # Medium stay
                discharge_prob = 0.4
            elif hours_stayed > 12:  # Short stay
                discharge_prob = 0.2
            
            # Adjust for patient condition
            if patient.deterioration_trend == -1:  # Improving
                discharge_prob *= 1.5
            elif patient.deterioration_trend == 1:  # Deteriorating
                discharge_prob *= 0.3
            
            discharge_candidates.append((patient_id, discharge_prob, hours_stayed))
        
        if discharge_candidates:
            # Select patient for discharge based on probability
            discharge_candidates.sort(key=lambda x: x[1], reverse=True)
            patient_id = discharge_candidates[0][0]
            
            patient = self.active_patients.pop(patient_id)
            patient.is_active = False
            self.total_discharges += 1
            
            # Track by shift
            shift = self.get_shift(datetime.now().hour)
            self.performance_metrics['shift_patterns'][shift]['discharges'] += 1
            
            hours_stayed = discharge_candidates[0][2]
            condition_names = ['Normal', 'Sepsis', 'Heart Failure']
            self.log_event('DISCHARGE', 
                          f"Patient {patient_id} discharged ({condition_names[patient.condition_type]}, "
                          f"stayed {hours_stayed:.1f}h)")
    
    def send_patient_vitals(self, patient):
        """Send vital signs for a patient with enhanced error handling"""
        try:
            vitals = patient.get_current_vitals()
            base_timestamp = int(time.time() * 1000)
            
            # Determine which sensors might be missing
            sensors_to_send = list(range(10))
            if random.random() < patient.missing_sensor_probability:
                num_missing = random.randint(1, 4)  # Up to 4 missing for severe cases
                sensors_to_skip = random.sample(sensors_to_send, num_missing)
                sensors_to_send = [s for s in sensors_to_send if s not in sensors_to_skip]
                
                if num_missing >= 3:
                    self.log_event('EQUIPMENT', 
                                  f"Patient {patient.patient_id}: {num_missing} sensors offline", True)
            
            # Send sensor packets
            sensor_mapping = ['temperature', 'oxygen_saturation', 'pulse_rate', 'systolic_bp',
                            'respiratory_rate', 'avpu', 'supplemental_oxygen', 'referral_source',
                            'age', 'sex']
            
            successful_sends = 0
            for sensor_id in sensors_to_send:
                if sensor_id < len(sensor_mapping):
                    vital_name = sensor_mapping[sensor_id]
                    value = vitals.get(vital_name, 0)
                    
                    try:
                        pkt = Ether(dst='00:04:00:00:00:00', type=0x1235) / Sensor(
                            patient_id=patient.patient_id,
                            sensor_id=sensor_id,
                            timestamp=base_timestamp + sensor_id,
                            feature_value=value
                        )
                        sendp(pkt, iface=self.send_iface, verbose=False)
                        successful_sends += 1
                    except Exception as e:
                        self.performance_metrics['error_count'] += 1
                        self.log_event('NETWORK', f"Failed to send sensor {sensor_id} for patient {patient.patient_id}")
            
            patient.last_transmission = datetime.now()
            self.total_transmissions += 1
            
            # Log critical missing data
            if len(sensors_to_send) < 7:  # Less than 7 sensors
                self.log_event('INCOMPLETE', 
                              f"Patient {patient.patient_id}: Only {len(sensors_to_send)}/10 sensors active")
            
        except Exception as e:
            self.performance_metrics['error_count'] += 1
            self.log_event('ERROR', f"Critical failure sending vitals for patient {patient.patient_id}: {e}", True)
    
    def monitor_alerts(self):
        """Enhanced alert monitoring with 24h pattern analysis"""
        def alert_handler(pkt):
            if not self.test_active:
                return
            
            if pkt.haslayer(Ether) and pkt[Ether].type == 0x1236:
                try:
                    receive_time = time.time()
                    current_hour = datetime.now().hour
                    shift = self.get_shift(current_hour)
                    
                    if pkt.haslayer(Alert):
                        alert = pkt[Alert]
                        patient_id = alert.patient_id
                        sep_pred = alert.sepPrediction
                        hf_pred = alert.hfPrediction
                        news2_score = alert.news2Score
                    else:
                        payload = bytes(pkt.payload)
                        if len(payload) >= 20:
                            patient_id = struct.unpack('!I', payload[0:4])[0]
                            sep_pred = struct.unpack('!I', payload[10:14])[0]
                            news2_score = payload[14]
                            hf_pred = struct.unpack('!I', payload[16:20])[0]
                        else:
                            return
                    
                    if patient_id in self.active_patients:
                        patient = self.active_patients[patient_id]
                        
                        alert_data = {
                            'timestamp': receive_time,
                            'sepsis_prediction': sep_pred,
                            'heart_failure_prediction': hf_pred,
                            'news2_score': news2_score,
                            'patient_condition': patient.condition_type,
                            'patient_severity': patient.severity,
                            'shift': shift,
                            'hours_since_admission': patient.hours_since_admission
                        }
                        
                        self.received_alerts[patient_id].append(alert_data)
                        self.total_alerts += 1
                        
                        # Track by shift
                        self.performance_metrics['shift_patterns'][shift]['alerts'] += 1
                        
                        # Calculate response time
                        if patient.last_transmission:
                            response_time = (receive_time - patient.last_transmission.timestamp()) * 1000
                            self.performance_metrics['response_times'].append(response_time)
                        
                        # Log significant alerts with enhanced context
                        is_critical_alert = (sep_pred > 0 or hf_pred > 0 or news2_score >= 7)
                        if is_critical_alert:
                            condition_names = ['Normal', 'Sepsis', 'Heart Failure']
                            self.log_event('ALERT', 
                                         f"Patient {patient_id} ({condition_names[patient.condition_type]}, "
                                         f"{patient.severity}): Sepsis={sep_pred}, HF={hf_pred}, "
                                         f"NEWS2={news2_score} [{shift} shift]",
                                         is_critical=(news2_score >= 7))
                    
                except Exception as e:
                    self.performance_metrics['error_count'] += 1
                    self.log_event('PARSE_ERROR', f"Alert parsing failed: {e}")
        
        try:
            sniff(iface=self.receive_iface, prn=alert_handler,
                  filter="ether proto 0x1236", store=0)
        except Exception as e:
            self.log_event('MONITOR_ERROR', f"Alert monitoring failed: {e}", True)
    
    def patient_management_loop(self):
        """Enhanced patient management with 24h patterns"""
        while self.test_active:
            try:
                current_hour = datetime.now().hour
                self.update_activity_rates(current_hour)
                
                # Patient admission (Poisson process)
                if random.random() < (self.current_admission_rate / 3600):
                    self.admit_patient()
                
                # Patient discharge (Poisson process)
                if random.random() < (self.current_discharge_rate / 3600) and self.active_patients:
                    self.discharge_patient()
                
                # Monitor for system overload
                if len(self.active_patients) > self.max_concurrent_patients * 0.9:
                    self.log_event('OVERLOAD', 
                                  f"System approaching capacity: {len(self.active_patients)}/{self.max_concurrent_patients}",
                                  True)
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                self.log_event('MGMT_ERROR', f"Patient management error: {e}", True)
                time.sleep(5)
    
    def vital_signs_loop(self):
        """Enhanced vital signs transmission with load balancing"""
        while self.test_active:
            try:
                current_time = datetime.now()
                hours_elapsed = (current_time - self.start_time).total_seconds() / 3600
                
                # Update patient conditions based on time
                for patient in list(self.active_patients.values()):
                    patient.evolve_condition(hours_elapsed)
                
                # Send vital signs for patients due for transmission
                patients_to_transmit = []
                for patient in self.active_patients.values():
                    if (patient.last_transmission is None or 
                        (current_time - patient.last_transmission).total_seconds() >= self.transmission_interval):
                        patients_to_transmit.append(patient)
                
                # Adaptive concurrency based on patient load
                max_workers = min(15, max(5, len(patients_to_transmit) // 3))
                
                if patients_to_transmit:
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        executor.map(self.send_patient_vitals, patients_to_transmit)
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.log_event('VITALS_ERROR', f"Vital signs transmission error: {e}", True)
                time.sleep(10)
    
    def collect_hourly_stats(self):
        """Enhanced hourly statistics collection for 24h monitoring"""
        hour_counter = 0
        
        while self.test_active and hour_counter < self.duration_hours:
            time.sleep(3600)  # Wait 1 hour
            hour_counter += 1
            
            if not self.test_active:
                break
            
            current_time = datetime.now()
            current_hour = current_time.hour
            shift = self.get_shift(current_hour)
            
            # Collect comprehensive hourly statistics
            prev_transmissions = sum(s.get('total_transmissions', 0) for s in self.hourly_stats)
            prev_alerts = sum(s.get('total_alerts', 0) for s in self.hourly_stats)
            
            stats = {
                'hour': hour_counter,
                'clock_hour': current_hour,
                'shift': shift,
                'active_patients': len(self.active_patients),
                'total_admissions': self.total_admissions,
                'total_discharges': self.total_discharges,
                'hourly_transmissions': self.total_transmissions - prev_transmissions,
                'hourly_alerts': self.total_alerts - prev_alerts,
                'avg_response_time': np.mean(list(self.performance_metrics['response_times'])) 
                                   if self.performance_metrics['response_times'] else 0,
                'p95_response_time': np.percentile(list(self.performance_metrics['response_times']), 95)
                                   if len(self.performance_metrics['response_times']) > 10 else 0,
                'error_count': self.performance_metrics['error_count'],
                'critical_events': len([e for e in self.critical_events if 
                                      (current_time - e['timestamp']).total_seconds() < 3600]),
                'timestamp': current_time,
                'admission_rate': self.current_admission_rate,
                'discharge_rate': self.current_discharge_rate
            }
            
            self.hourly_stats.append(stats)
            
            self.log_event('HOURLY_STATS', 
                         f"Hour {hour_counter} ({shift}): {stats['active_patients']} patients, "
                         f"{stats['hourly_transmissions']} transmissions, "
                         f"{stats['hourly_alerts']} alerts, "
                         f"{stats['avg_response_time']:.1f}ms avg response")
    
    def run_twenty_four_hour_test(self):
        """Run the complete 24-hour hospital simulation"""
        self.start_time = datetime.now()
        
        print("🏥 24-HOUR HOSPITAL ICU SIMULATION")
        print("=" * 70)
        print(f"Start time: {self.start_time}")
        print(f"Duration: {self.duration_hours} hours")
        print(f"Max concurrent patients: {self.max_concurrent_patients}")
        print(f"Transmission interval: {self.transmission_interval} seconds")
        print(f"Send interface: {self.send_iface}")
        print(f"Receive interface: {self.receive_iface}")
        print("=" * 70)
        
        self.log_event('START', f"24-hour simulation beginning")
        
        # Start all monitoring threads
        monitor_thread = threading.Thread(target=self.monitor_alerts)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        patient_mgmt_thread = threading.Thread(target=self.patient_management_loop)
        patient_mgmt_thread.daemon = True
        patient_mgmt_thread.start()
        
        vitals_thread = threading.Thread(target=self.vital_signs_loop)
        vitals_thread.daemon = True
        vitals_thread.start()
        
        stats_thread = threading.Thread(target=self.collect_hourly_stats)
        stats_thread.daemon = True
        stats_thread.start()
        
        # Admit initial patients (realistic ICU census)
        initial_patients = random.randint(15, 25)
        for _ in range(initial_patients):
            self.admit_patient()
        
        try:
            # Main test loop - run for 24 hours
            end_time = self.start_time + timedelta(hours=self.duration_hours)
            
            while datetime.now() < end_time and self.test_active:
                time.sleep(300)  # Check every 5 minutes
                
                # Progress update every 2 hours
                elapsed = (datetime.now() - self.start_time).total_seconds() / 3600
                if int(elapsed / 2) > int((elapsed - 5/60) / 2):  # Every 2 hours
                    progress = (elapsed / self.duration_hours) * 100
                    current_shift = self.get_shift(datetime.now().hour)
                    self.log_event('PROGRESS', 
                                 f"{progress:.1f}% complete - {len(self.active_patients)} active patients "
                                 f"({current_shift} shift), {len(self.critical_events)} critical events")
        
        except KeyboardInterrupt:
            self.log_event('INTERRUPT', "Test interrupted by user", True)
        
        finally:
            self.test_active = False
            self.log_event('END', "24-hour simulation complete")
            
            # Final cleanup - discharge remaining patients
            remaining_patients = len(self.active_patients)
            while self.active_patients:
                self.discharge_patient()
            
            self.log_event('CLEANUP', f"Discharged {remaining_patients} remaining patients")
            
            # Wait for final alerts
            time.sleep(60)
            
            self.analyze_results()
    
    def analyze_results(self):
        """Comprehensive 24-hour analysis with shift patterns and trends"""
        end_time = datetime.now()
        actual_duration = (end_time - self.start_time).total_seconds() / 3600
        
        print("\n" + "=" * 100)
        print("🎯 24-HOUR SIMULATION COMPREHENSIVE RESULTS")
        print("=" * 100)
        
        # Overall statistics
        print(f"Actual duration: {actual_duration:.2f} hours")
        print(f"Total patient admissions: {self.total_admissions}")
        print(f"Total patient discharges: {self.total_discharges}")
        print(f"Peak concurrent patients: {max((s['active_patients'] for s in self.hourly_stats), default=0)}")
        print(f"Total vital sign transmissions: {self.total_transmissions}")
        print(f"Total alerts received: {self.total_alerts}")
        print(f"Critical events: {len(self.critical_events)}")
        print(f"System errors: {self.performance_metrics['error_count']}")
        
        # Shift analysis
        print(f"\n📊 SHIFT PATTERN ANALYSIS:")
        for shift in ['day', 'evening', 'night']:
            shift_data = self.performance_metrics['shift_patterns'][shift]
            print(f"  {shift.upper()} SHIFT:")
            print(f"    Admissions: {shift_data['admissions']}")
            print(f"    Discharges: {shift_data['discharges']}")
            print(f"    Alerts: {shift_data['alerts']}")
        
        # Alert analysis by condition and severity
        condition_alerts = {0: {'mild': [], 'moderate': [], 'severe': []}, 
                           1: {'mild': [], 'moderate': [], 'severe': []}, 
                           2: {'mild': [], 'moderate': [], 'severe': []}}
        
        for patient_id, alerts in self.received_alerts.items():
            for alert in alerts:
                condition = alert['patient_condition']
                severity = alert.get('patient_severity', 'moderate')
                condition_alerts[condition][severity].append(alert)
        
        condition_names = ['Normal', 'Sepsis', 'Heart Failure']
        print(f"\n🔍 DETAILED ALERT ANALYSIS:")
        for condition in [0, 1, 2]:
            print(f"  {condition_names[condition].upper()} PATIENTS:")
            for severity in ['mild', 'moderate', 'severe']:
                alerts = condition_alerts[condition][severity]
                if alerts:
                    sepsis_alerts = sum(1 for a in alerts if a['sepsis_prediction'] > 0)
                    hf_alerts = sum(1 for a in alerts if a['heart_failure_prediction'] > 0)
                    high_news2 = sum(1 for a in alerts if a['news2_score'] >= 7)
                    critical_news2 = sum(1 for a in alerts if a['news2_score'] >= 9)
                    
                    print(f"    {severity.capitalize()}: {len(alerts)} total alerts")
                    print(f"      Sepsis predictions: {sepsis_alerts}")
                    print(f"      Heart failure predictions: {hf_alerts}")
                    print(f"      High NEWS2 (≥7): {high_news2}")
                    print(f"      Critical NEWS2 (≥9): {critical_news2}")
        
        # Performance metrics with 24h context
        if self.performance_metrics['response_times']:
            response_times = list(self.performance_metrics['response_times'])
            print(f"\n⚡ PERFORMANCE METRICS:")
            print(f"  Average response time: {np.mean(response_times):.1f} ms")
            print(f"  Median response time: {np.median(response_times):.1f} ms")
            print(f"  95th percentile: {np.percentile(response_times, 95):.1f} ms")
            print(f"  99th percentile: {np.percentile(response_times, 99):.1f} ms")
            print(f"  Maximum response time: {np.max(response_times):.1f} ms")
        
        # Hourly trends
        if self.hourly_stats:
            print(f"\n📈 HOURLY TRENDS:")
            print(f"{'Hour':<6} {'Shift':<8} {'Patients':<10} {'Trans':<8} {'Alerts':<8} {'Resp(ms)':<10} {'Errors':<8}")
            print("-" * 70)
            for stats in self.hourly_stats:
                print(f"{stats['hour']:<6} {stats['shift']:<8} {stats['active_patients']:<10} "
                      f"{stats['hourly_transmissions']:<8} {stats['hourly_alerts']:<8} "
                      f"{stats['avg_response_time']:<10.1f} {stats['error_count']:<8}")
        
        # Critical events summary
        if self.critical_events:
            print(f"\n🚨 CRITICAL EVENTS SUMMARY:")
            event_types = {}
            for event in self.critical_events:
                event_type = event['type']
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            for event_type, count in sorted(event_types.items()):
                print(f"  {event_type}: {count} occurrences")
        
        # System reliability and capacity analysis
        total_minutes = actual_duration * 60
        error_free_minutes = total_minutes - self.performance_metrics['error_count']
        uptime_percentage = (error_free_minutes / total_minutes) * 100
        
        print(f"\n🏆 SYSTEM RELIABILITY (24-HOUR):")
        print(f"  Uptime: {uptime_percentage:.3f}%")
        print(f"  Average patients per hour: {self.total_admissions / actual_duration:.1f}")
        print(f"  Average transmissions per hour: {self.total_transmissions / actual_duration:.1f}")
        print(f"  Average alerts per hour: {self.total_alerts / actual_duration:.1f}")
        print(f"  Patient throughput: {(self.total_admissions + self.total_discharges) / actual_duration:.1f} per hour")
        
        # Capacity utilization
        if self.hourly_stats:
            avg_patients = np.mean([s['active_patients'] for s in self.hourly_stats])
            max_patients = max([s['active_patients'] for s in self.hourly_stats])
            capacity_utilization = (avg_patients / self.max_concurrent_patients) * 100
            peak_utilization = (max_patients / self.max_concurrent_patients) * 100
            
            print(f"\n📊 CAPACITY ANALYSIS:")
            print(f"  Average utilization: {capacity_utilization:.1f}% ({avg_patients:.1f}/{self.max_concurrent_patients})")
            print(f"  Peak utilization: {peak_utilization:.1f}% ({max_patients}/{self.max_concurrent_patients})")
        
        # Save comprehensive results
        self.save_results()
        
        print("\n🎉 24-hour simulation analysis complete!")
        print("💾 Detailed results saved to CSV files for further analysis")
    
    def save_results(self):
        """Save comprehensive 24-hour test results"""
        timestamp = int(time.time())
        
        # Save hourly statistics
        if self.hourly_stats:
            df_hourly = pd.DataFrame(self.hourly_stats)
            df_hourly.to_csv(f'twenty_four_hour_hourly_stats_{timestamp}.csv', index=False)
        
        # Save system events
        if self.system_events:
            events_data = []
            for event in self.system_events:
                events_data.append({
                    'timestamp': event['timestamp'],
                    'hours_elapsed': event['hours_elapsed'],
                    'type': event['type'],
                    'message': event['message'],
                    'shift': event['shift'],
                    'is_critical': event['is_critical']
                })
            df_events = pd.DataFrame(events_data)
            df_events.to_csv(f'twenty_four_hour_events_{timestamp}.csv', index=False)
        
        # Save detailed alert analysis
        alert_details = []
        for patient_id, alerts in self.received_alerts.items():
            for alert in alerts:
                alert_details.append({
                    'patient_id': patient_id,
                    'timestamp': alert['timestamp'],
                    'sepsis_prediction': alert['sepsis_prediction'],
                    'heart_failure_prediction': alert['heart_failure_prediction'],
                    'news2_score': alert['news2_score'],
                    'patient_condition': alert['patient_condition'],
                    'patient_severity': alert.get('patient_severity', 'unknown'),
                    'shift': alert.get('shift', 'unknown'),
                    'hours_since_admission': alert.get('hours_since_admission', 0)
                })
        
        if alert_details:
            df_alerts = pd.DataFrame(alert_details)
            df_alerts.to_csv(f'twenty_four_hour_alerts_{timestamp}.csv', index=False)
        
        # Save shift pattern analysis
        shift_summary = []
        for shift, data in self.performance_metrics['shift_patterns'].items():
            shift_summary.append({
                'shift': shift,
                'admissions': data['admissions'],
                'discharges': data['discharges'],
                'alerts': data['alerts']
            })
        
        if shift_summary:
            df_shifts = pd.DataFrame(shift_summary)
            df_shifts.to_csv(f'twenty_four_hour_shift_patterns_{timestamp}.csv', index=False)
        
        # Save critical events
        if self.critical_events:
            critical_data = []
            for event in self.critical_events:
                critical_data.append({
                    'timestamp': event['timestamp'],
                    'hours_elapsed': event['hours_elapsed'],
                    'type': event['type'],
                    'message': event['message'],
                    'shift': event['shift']
                })
            df_critical = pd.DataFrame(critical_data)
            df_critical.to_csv(f'twenty_four_hour_critical_events_{timestamp}.csv', index=False)
        
        print(f"\n💾 Comprehensive results saved:")
        print(f"  twenty_four_hour_hourly_stats_{timestamp}.csv")
        print(f"  twenty_four_hour_events_{timestamp}.csv")
        print(f"  twenty_four_hour_alerts_{timestamp}.csv")
        print(f"  twenty_four_hour_shift_patterns_{timestamp}.csv")
        print(f"  twenty_four_hour_critical_events_{timestamp}.csv")

def main():
    print("🏥 24-Hour Hospital ICU Simulation")
    print("=" * 60)
    print("This comprehensive test simulates a full 24-hour period in an ICU with:")
    print("  • Realistic day/evening/night shift patterns")
    print("  • Dynamic patient admissions and discharges")
    print("  • Patient condition evolution over time")
    print("  • Missing sensor simulation with equipment failures")
    print("  • Comprehensive shift-based analysis")
    print("  • Critical event monitoring and alerting")
    print("  • System capacity and reliability assessment")
    print()
    
    # Enhanced configuration options for 24h test
    duration = float(input("Test duration in hours [24]: ") or "24")
    max_patients = int(input("Maximum concurrent patients [75]: ") or "75")
    transmission_interval = int(input("Vital signs interval in seconds [60]: ") or "60")
    
    print(f"\nTest configuration:")
    print(f"  Duration: {duration} hours")
    print(f"  Max concurrent patients: {max_patients}")
    print(f"  Transmission interval: {transmission_interval} seconds")
    print(f"  Estimated total patients: {int(duration * 2.2)}")
    print(f"  Estimated transmissions: {int(duration * max_patients * 60 / transmission_interval)}")
    print()
    
    print("⚠️  WARNING: This is a 24-hour test that will:")
    print("  • Generate substantial network traffic")
    print("  • Create large result files (>100MB)")
    print("  • Require continuous system operation")
    print("  • Monitor system performance around the clock")
    print()
    
    proceed = input("Start 24-hour simulation? (y/n): ").lower()
    if proceed != 'y':
        print("Test cancelled.")
        return
    
    # Run the comprehensive 24-hour test
    tester = TwentyFourHourTester()
    tester.duration_hours = duration
    tester.max_concurrent_patients = max_patients
    tester.transmission_interval = transmission_interval
    
    print(f"\n🚀 Starting 24-hour simulation at {datetime.now()}")
    print("Press Ctrl+C to stop early (will perform graceful shutdown)")
    
    tester.run_twenty_four_hour_test()

if __name__ == "__main__":
    main()