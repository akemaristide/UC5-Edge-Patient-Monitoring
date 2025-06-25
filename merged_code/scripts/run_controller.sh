simple_switch_CLI < ./tables/s1-commands.txt

sleep 10

python3 ./src/controller.py  --p4info ./build/PatientMonitoring.p4.p4info.txtpb --bmv2-json ./build/PatientMonitoring.json