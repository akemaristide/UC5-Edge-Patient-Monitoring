#!/usr/bin/env python3

import argparse
import csv
import os
import random
import sys
import time
import threading
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../utils/'))
import grpc
import p4runtime_lib.bmv2
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections
import p4runtime_lib.helper
from scapy.all import Ether, Packet, bind_layers, raw
from scapy.fields import ByteField, BitField, ShortField, IntField, StrFixedLenField

from p4.v1 import p4runtime_pb2

# ---------------------------
# Global configuration
# ---------------------------
CPU_PORT = 510  # CPU port used in both PacketIn and PacketOut
CSV_LOG = "./logs/controller_imputation_log.csv"
NUM_PATIENTS = 2000
HEARTBEAT_NS = 15  # Heartbeat interval in seconds

# Ensure CSV log file has a header
with open(CSV_LOG, "w", newline="") as csvfile:
    csv.writer(csvfile).writerow(["reception_time", "patient_id", "sensor_id", "old_value", "new_value"])

# ---------------------------
# Define the Planter header
# ---------------------------
class Planter(Packet):
    name = "Planter"
    fields_desc = [
        StrFixedLenField("P", "P", length=1),
        StrFixedLenField("Four", "4", length=1),
        ByteField("version", 0x01),
        ByteField("type", 0x01),
        IntField("patient_id", 0),
        BitField("timestamp", 0, 48),
        ShortField("feature0", 0),
        ShortField("feature1", 0),
        ShortField("feature2", 0),
        ShortField("feature3", 0),
        ShortField("feature4", 0),
        ShortField("feature5", 0),
        ShortField("feature6", 0),
        ShortField("feature7", 0),
        ShortField("feature8", 0),
        ShortField("feature9", 0),
        IntField("result", 0)
    ]

# Bind Planter to Ether with EtherType 0x1234
ETHERTYPE_PLANTER = 0x1234
bind_layers(Ether, Planter, type=ETHERTYPE_PLANTER)

# ---------------------------
# Define the Sensor header for heartbeat
# ---------------------------
class Sensor(Packet):
    name = "Sensor"
    fields_desc = [
        IntField("patient_id", 0),
        IntField("sensor_id", 999),
        BitField("timestamp", 0, 48),
        ShortField("feature_value", 0)
    ]

ETHERTYPE_SENSOR = 0x1235
bind_layers(Ether, Sensor, type=ETHERTYPE_SENSOR)

# ---------------------------
# Imputation helper: generate plausible random value for each sensor
# ---------------------------
def impute_value(sensor_id):
    if sensor_id == 0:  # temperature (scaled by 10)
        return random.randint(350, 400)
    elif sensor_id == 1:  # oxygen saturation
        return random.randint(90, 100)
    elif sensor_id == 2:  # pulse rate
        return random.randint(60, 100)
    elif sensor_id == 3:  # systolic blood pressure
        return random.randint(100, 140)
    elif sensor_id == 4:  # respiratory rate
        return random.randint(12, 20)
    elif sensor_id == 5:  # avpu
        return random.randint(0, 3)
    elif sensor_id == 6:  # supplemental oxygen (binary)
        return random.randint(0, 1)
    elif sensor_id == 7:  # referral source
        return 1
    elif sensor_id == 8:  # age
        return random.randint(30, 80)
    elif sensor_id == 9:  # sex (0 or 1)
        return random.randint(0, 1)
    else:
        return 1

def log_imputation(recv_time, patient_id, sensor_id, old_val, new_val):
    with open(CSV_LOG, "a", newline="") as csvfile:
        csv.writer(csvfile).writerow([recv_time, patient_id, sensor_id, old_val, new_val])

# ---------------------------
# Heartbeat sender thread
# ---------------------------
def heartbeat_loop(switch_conn):
    while True:
        for pid in range(NUM_PATIENTS):
            sensor_pkt = Ether(dst="00:04:00:00:00:00",src="08:00:27:bc:fc:b5",type=ETHERTYPE_SENSOR) / Sensor(patient_id=pid, sensor_id=999, timestamp=0, feature_value=0)            
            packet_out = p4runtime_pb2.PacketOut()
            packet_out.payload = raw(sensor_pkt)
            try:
                switch_conn.PacketOut(packet_out.SerializeToString(), [])
            except Exception as e:
                print(f"Error sending heartbeat for patient {pid}: {e}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sent heartbeat packets for all patients.")
        time.sleep(HEARTBEAT_NS)

# ---------------------------
# Parse and process packet
# ---------------------------
def parse_packet(raw_payload, p4info_helper, switch_conn):
    try:
        pkt = Ether(raw_payload)
        if Planter not in pkt:
            print("Received PacketIn does not contain a Planter header; ignoring.")
            return

        planter = pkt[Planter]
        recv_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        patient_id = planter.patient_id
        imputed = False

        for sensor_id in range(10):
            if sensor_id in [5, 6, 7, 8, 9]:  # Skip non-numeric fields
                continue
            field_name = f"feature{sensor_id}"
            cur_val = getattr(planter, field_name)
            if cur_val == 0:
                new_val = impute_value(sensor_id)
                log_imputation(recv_time, patient_id, sensor_id, cur_val, new_val)
                print(f"[{recv_time}] Imputing {field_name} for patient {patient_id}: {cur_val} -> {new_val}")
                setattr(planter, field_name, new_val)
                imputed = True

        if imputed:
            print(f"[{recv_time}] Modified Planter packet for patient {patient_id}:\n{planter.show2(dump=True)}")
        else:
            print(f"[{recv_time}] Received complete Planter packet for patient {patient_id}:\n{planter.show2(dump=True)}")

        packet_out = p4runtime_pb2.PacketOut()
        packet_out.payload = raw(pkt)

        print(f"[{recv_time}] Sending PacketOut to egress port {CPU_PORT}.")
        switch_conn.PacketOut(packet_out.SerializeToString(), [])

    except Exception as e:
        print(f"Error parsing packet: {e}")

# ---------------------------
# Packet-in handler
# ---------------------------
def handle_packet_in(switch_conn, p4info_helper):
    try:
        pktin = switch_conn.PacketIn()
        if pktin is not None:
            print(f"Received PacketIn: payload length = {len(pktin.packet.payload)} bytes")
            parse_packet(pktin.packet.payload, p4info_helper, switch_conn)
    except grpc.RpcError as e:
        printGrpcError(e)

# ---------------------------
# Main controller
# ---------------------------
def main(p4info_file_path, bmv2_file_path):
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        switch_conn = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name="s1",
            address="127.0.0.1:50051",
            device_id=0,
            proto_dump_file="p4runtime.log"
        )

        if switch_conn.MasterArbitrationUpdate() is None:
            print("Failed to establish mastership with switch")
            sys.exit(1)

        print("Controller is now listening for PacketIn messages...")

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=heartbeat_loop, args=(switch_conn,))
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

        # Start packet-in handler
        while True:
            handle_packet_in(switch_conn, p4info_helper)

    except grpc.RpcError as e:
        printGrpcError(e)
    finally:
        ShutdownAllSwitchConnections()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P4Runtime Controller for Planter Packet Imputation with Heartbeat")
    parser.add_argument("--p4info", type=str, required=True, help="Path to the p4info file in text pb format")
    parser.add_argument("--bmv2-json", type=str, required=True, help="Path to the BMv2 JSON file")

    args = parser.parse_args()
    if not os.path.exists(args.p4info):
        print(f"p4info file {args.p4info} not found!")
        sys.exit(1)
    if not os.path.exists(args.bmv2_json):
        print(f"BMv2 JSON file {args.bmv2_json} not found!")
        sys.exit(2)

    main(args.p4info, args.bmv2_json)