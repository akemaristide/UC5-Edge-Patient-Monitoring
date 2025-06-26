#!/bin/bash
simple_switch_CLI < ./tables/s1-commands-sep.txt
sleep 1
simple_switch_CLI < ./tables/s1-commands-hf.txt
sleep 1
simple_switch_CLI < ./tables/news2-commands.txt
sleep 1
python3 ./src/controller.py --p4info ./build/PatientMonitoring.p4.p4info.txtpb --bmv2-json ./build/PatientMonitoring.json