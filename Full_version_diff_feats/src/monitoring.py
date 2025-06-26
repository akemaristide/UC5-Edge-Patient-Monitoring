#!/usr/bin/env python3
# filepath: /home/akem/tutorials/exercises/UC5_Sepsis_Monitoring/monitoring.py

import csv
import time
from datetime import datetime
from termcolor import colored
from scapy.all import Ether, sniff, Packet, IntField, BitField, bind_layers, ShortField

# Define Alert packet structure
class Alert(Packet):
    name = "Alert"
    fields_desc = [
        IntField("patient_id", 0),
        BitField("timestamp", 0, 48),  # Timestamp of the alert (48 bits)
        IntField("alert_value", 0),
        BitField("news2Score", 0, 8),  # NEWS2 score (8 bits)
        BitField("news2Alert", 0, 8),   # NEWS2 alert level
        IntField("hfPrediction", 0)     # HF prediction (not used in this script)
    ]

# Bind Alert packet with Ether using Ethertype 0x1236
ETHERTYPE_ALERT = 0x1236
bind_layers(Ether, Alert, type=ETHERTYPE_ALERT)

CSV_FILE = "./logs/alerts_log.csv"
MONITOR_IFACE = "s1-eth1"

# Initialize CSV: write header if file does not exist.
# Always create a new CSV file and write the header
with open(CSV_FILE, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["reception_time", "patient_id", "alert_timestamp", "sepsis_alert", "heart_fail_alert" ,"news2_score", "news2_alert"])

def process_alert(packet):
    if Alert in packet:
        alert = packet[Alert]
        # Extract fields from alert header
        patient_id       = alert.patient_id
        alert_ts         = alert.timestamp
        alert_value      = alert.alert_value
        news2_score      = alert.news2Score
        news2_alert      = alert.news2Alert
        heart_fail_alert = alert.hfPrediction

        # Get current time as reception time
        recv_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Print information for sepsis alert
        if alert_value == 1:
            print(f"\033[91m Sepsis Risk prediction received @ {recv_time} -> Patient: {patient_id}, Value: {alert_value}\033[0m")
        else:
            print(f"Sepsis Risk prediction received @ {recv_time} -> Patient: {patient_id}, Value: {alert_value}")
        # Print information for heart failure alert
        if heart_fail_alert == 1:
            print(f"\033[91m Heart Failure Risk prediction received @ {recv_time} -> Patient: {patient_id}, Value: {heart_fail_alert}\033[0m")
        else:
            print(f"Heart Failure Risk prediction received @ {recv_time} -> Patient: {patient_id}, Value: {heart_fail_alert}")

        # Color-code alertLevel for NEWS2 score
        if news2_alert == 1:
            alert_str = colored(f"Medium (1)", "yellow")
        elif news2_alert == 2:
            alert_str = colored(f"High (2)", "red")
        elif news2_alert == 0:
            alert_str = colored(f"Low (0)", "green")
        else:
            alert_str = f"Unknown ({news2_alert})"  # Fallback for unexpected values
        # Print required fields
        print(f"NEWS2 alert received  @ {recv_time} -> Patient: {patient_id}, Score: {news2_score}, Alert Level: {alert_str}")
        
        # Append record to CSV file
        with open(CSV_FILE, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([recv_time, patient_id, alert_ts, alert_value, heart_fail_alert, news2_score, news2_alert])

def main():
    print(f"Monitoring for alert packets on interface {MONITOR_IFACE}...")
    # Sniff continuously, calling process_alert for each packet
    sniff(iface=MONITOR_IFACE, prn=process_alert, store=0)

if __name__ == "__main__":
    main()