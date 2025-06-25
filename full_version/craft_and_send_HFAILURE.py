import numpy as np
from scapy.all import *
import pandas as pd

# Define Planter packet structure
class Planter(Packet):
    name = 'Planter'
    fields_desc = [
        StrFixedLenField('P', 'P', length=1),
        StrFixedLenField('Four', '4', length=1),
        XByteField('version', 0x01),
        XByteField('type', 0x01),
        ShortField('patient_id', 0),
        IntField('timestamp', 0),
        IntField('feature0', 0),
        IntField('feature1', 0),
        IntField('feature2', 0),
        IntField('feature3', 0),
        IntField('feature4', 0),
        IntField('feature5', 0),
        IntField('result', 0xDEADBABE)
    ]

bind_layers(Ether, Planter, type=0x1234)

# Validate interface
# send_iface = 's1-eth2'
send_iface = 'eth0'
if send_iface not in get_if_list():
    print(f"Error: Interface {send_iface} not found. Available: {get_if_list()}")
    exit(1)

# Load data from CSV
data_file = '/home/akem/Planter/Tables/HeartFailure/val_normal_vs_heart_failure.csv'
try:
    Test_Data = pd.read_csv(data_file)
    Test_Data['temperature'] = Test_Data['temperature'] * 10
    test_X = Test_Data[['temperature','pulse_rate','systolic_bp','respiratory_rate','referral_source','oxygen_saturation']].values
except Exception as e:
    print(f"Error loading CSV file: {str(e)}")
    exit(1)

# Craft and send packets
for i in range(len(Test_Data)):
    pkt = Ether(dst='00:04:00:00:00:00', type=0x1234) / Planter(
        patient_id=int(Test_Data['patient_id'].iloc[i]),
        timestamp=int(Test_Data['timestamp'].iloc[i]),
        feature0=int(test_X[i][0]),  # 
        feature1=int(test_X[i][1]),  # 
        feature2=int(test_X[i][2]),  # 
        feature3=int(test_X[i][3]),  # 
        feature4=int(test_X[i][4]),  # 
        feature5=int(test_X[i][5]),  # 
        result=int(404)
    )
    pkt = pkt/' '
    sendp(pkt, iface=send_iface, verbose=False)