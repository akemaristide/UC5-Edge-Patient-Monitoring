#include <core.p4>
#include <v1model.p4>

/*************************************************************************
*********************** headers and metadata *****************************
*************************************************************************/
#define CPU_PORT 510 // CPU port for control plane packets
#define MONITORING_PORT 1

// When running with simple_switch_grpc, we must provide the
// following command line option to enable the ability for the
// software switch to receive and send messages to the controller:
//
//     --cpu-port 510

const   int     CPU_PORT_CLONE_SESSION_ID = 57;
const   int     NUM_PATIENTS              = 2000; // Number of patients
const   bit<16> ETHERTYPE_Planter         = 0x1234;
const   bit<16> ETHERTYPE_Sensor          = 0x1235;
const   bit<16> ETHERTYPE_Alert           = 0x1236;
const   bit<8>  Planter_P                 = 0x50;   // 'P'
const   bit<8>  Planter_4                 = 0x34;   // '4'
const   bit<8>  Planter_VER               = 0x01;   // v0.1
const   bit<48> TIMEOUT_NS                = 60000000; // 1 minute in microseconds
const   bit<48> QUIET_NS                  = 30000000; // 30 seconds in microseconds

header ethernet_h {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header Planter_h{
    bit<8> p;
    bit<8> four;
    bit<8> ver;
    bit<8> typ;
    bit<32> patient_id;
    bit<48> timestamp;
    bit<16> feature0;
    bit<16> feature1;
    bit<16> feature2;
    bit<16> feature3;
    bit<16> feature4;
    bit<16> feature5;
    bit<16> feature6;
    bit<16> feature7;
    bit<16> feature8;
    bit<16> feature9;
    bit<32> result;
}

header Sensor_h {
    bit<32>  patient_id;
    bit<32>  sensor_id;
    bit<48>  timestamp; // Timestamp of the sensor reading
    bit<16>  feature_value;
}

header Alert_h {
    bit<32>  patient_id;
    bit<48>  timestamp; // Timestamp of the alert
    bit<32>  alert_value; 
}

struct header_t {
    ethernet_h   ethernet;
    Planter_h    Planter;
    Sensor_h     Sensor;
    Alert_h      Alert;
}

struct metadata_t {
    bit<16> temperature;
    bit<16> oxygen_saturation;
    bit<16> pulse_rate;
    bit<16> systolic_bp;
    bit<16> respiratory_rate;
    bit<16> avpu;
    bit<16> supplemental_oxygen;
    bit<16> referral_source; 
    bit<8>  age; 
    bit<8>  sex;

    bit<8>  code_f0;
    bit<6>  code_f1;
    bit<8>  code_f2;
    bit<8>  code_f3;
    bit<4>  code_f4;
    bit<8>  code_f5;
    bit<4>  code_f6;
    bit<8>  code_f7;
    bit<18> code_f8;
    bit<8>  code_f9;

    bit<7> sum_prob;
    bit<4> tree_0_vote;
    bit<4> tree_1_vote;
    bit<4> tree_2_vote;
    bit<4> tree_3_vote;
    bit<7> tree_0_prob;
    bit<7> tree_1_prob;
    bit<7> tree_2_prob;
    bit<7> tree_3_prob;

    bit<32>  DstAddr;
    bit<32>  result;
    bit<8>   flag ;
}

/*************************************************************************
*********************** Ingress Parser ***********************************
*************************************************************************/

parser SwitchParser(
    packet_in pkt,
    out header_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t ig_intr_md) {

    state start {
	transition select(ig_intr_md.ingress_port){
        CPU_PORT: skip_two_bytes;	
	    default:  parse_ethernet;
        }
    }

    state skip_two_bytes {
        pkt.advance(16); // Skip 16 bits (2 bytes)
        transition parse_ethernet;
    }


    // state start {
    //     transition parse_ethernet;
    // }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
        ETHERTYPE_Planter : check_planter_version;
        ETHERTYPE_Sensor  : parse_sensor;
        default           : accept;
        }
    }

    state check_planter_version {
        transition select(pkt.lookahead<Planter_h>().p,
                          pkt.lookahead<Planter_h>().four,
                          pkt.lookahead<Planter_h>().ver) {
        (Planter_P, Planter_4, Planter_VER) : parse_planter;
        default                             : accept;
        }
    }

    state parse_planter {
        pkt.extract(hdr.Planter);
        meta.flag = 1 ;
        transition accept;
    }

    state parse_sensor {
        pkt.extract(hdr.Sensor);
        transition accept;
    }
}

/*************************************************************************
*********************** Egress Deparser *********************************
**************************************************************************/

control SwitchDeparser(
    packet_out pkt,
    in header_t hdr) {
    apply {
        pkt.emit(hdr);
    }
}

/*************************************************************************
********************** Checksum Verification *****************************
*************************************************************************/

control SwitchVerifyChecksum(inout header_t hdr,
                       inout metadata_t meta) {
    apply {}
}
/*************************************************************************
********************** Checksum Computation ******************************
*************************************************************************/

control SwitchComputeChecksum(inout header_t hdr,
                        inout metadata_t meta) {
    apply {}
}
/*************************************************************************
*********************** Ingress Processing********************************
**************************************************************************/

control SwitchIngress(
    inout header_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t ig_intr_md) {

    action send(bit<9> port) {
        ig_intr_md.egress_spec = port;
    }

    action drop() {
        mark_to_drop(ig_intr_md);
    }

    // ************ Start of Planter actions and tables **********//
    action extract_feature0(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }

    action extract_feature1(out bit<6> meta_code, bit<6> tree){
        meta_code = tree;
    }

    action extract_feature2(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }

    action extract_feature3(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }

    action extract_feature4(out bit<4> meta_code, bit<4> tree){
        meta_code = tree;
    }

    action extract_feature5(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }

    action extract_feature6(out bit<4> meta_code, bit<4> tree){
        meta_code = tree;
    }

    action extract_feature7(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }

    action extract_feature8(out bit<18> meta_code, bit<18> tree){
        meta_code = tree;
    }

    action extract_feature9(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }

    @pragma stage 0
    table lookup_feature0 {
        key = {meta.temperature:ternary; }
        actions = {
            extract_feature0(meta.code_f0);
            NoAction;
            }
        size = 16;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature1 {
        key = { meta.oxygen_saturation:ternary; }
        actions = {
            extract_feature1(meta.code_f1);
            NoAction;
            }
        size = 10;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature2 {
        key = { meta.pulse_rate:ternary; }
        actions = {
            extract_feature2(meta.code_f2);
            NoAction;
            }
        size = 13;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature3 {
        key = { meta.systolic_bp:ternary; }
        actions = {
            extract_feature3(meta.code_f3);
            NoAction;
            }
        size = 17;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature4 {
        key = { meta.respiratory_rate:ternary; }
        actions = {
            extract_feature4(meta.code_f4);
            NoAction;
            }
        size = 7;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature5 {
        key = { meta.avpu:ternary; }
        actions = {
            extract_feature5(meta.code_f5);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature6 {
        key = { meta.supplemental_oxygen:ternary; }
        actions = {
            extract_feature6(meta.code_f6);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature7 {
        key = { meta.referral_source:ternary; }
        actions = {
            extract_feature7(meta.code_f7);
            NoAction;
            }
        size = 4;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature8 {
        key = { meta.age:ternary; }
        actions = {
            extract_feature8(meta.code_f8);
            NoAction;
            }
        size = 28;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature9 {
        key = { meta.sex:ternary; }
        actions = {
            extract_feature9(meta.code_f9);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }


    action read_prob0(bit<7> prob, bit<4> vote){
        meta.tree_0_prob = prob;
        meta.tree_0_vote = vote;
    }
    action write_default_class0() {
        meta.tree_0_vote = 0;
    }


    action read_prob1(bit<7> prob, bit<4> vote){
        meta.tree_1_prob = prob;
        meta.tree_1_vote = vote;
    }
    action write_default_class1() {
        meta.tree_1_vote = 0;
    }


    action read_prob2(bit<7> prob, bit<4> vote){
        meta.tree_2_prob = prob;
        meta.tree_2_vote = vote;
    }
    action write_default_class2() {
        meta.tree_2_vote = 0;
    }


    action read_prob3(bit<7> prob, bit<4> vote){
        meta.tree_3_prob = prob;
        meta.tree_3_vote = vote;
    }
    action write_default_class3() {
        meta.tree_3_vote = 0;
    }

    @pragma stage 1
    table lookup_leaf_id0 {
        key = { meta.code_f0[2:0]:exact;
                meta.code_f1[0:0]:exact;
                meta.code_f2[2:0]:exact;
                meta.code_f3[2:0]:exact;
                meta.code_f4[0:0]:exact;
                meta.code_f5[1:0]:exact;
                meta.code_f6[0:0]:exact;
                meta.code_f7[1:0]:exact;
                meta.code_f8[3:0]:exact;
                meta.code_f9[1:0]:exact;
                }
        actions={
            read_prob0;
            write_default_class0;
        }
        size = 648;
        default_action = write_default_class0;
    }

    @pragma stage 1
    table lookup_leaf_id1 {
        key = { meta.code_f0[5:3]:exact;
                meta.code_f1[1:1]:exact;
                meta.code_f2[5:3]:exact;
                meta.code_f3[5:3]:exact;
                meta.code_f4[1:1]:exact;
                meta.code_f5[3:2]:exact;
                meta.code_f6[1:1]:exact;
                meta.code_f7[3:2]:exact;
                meta.code_f8[7:4]:exact;
                meta.code_f9[3:2]:exact;
                }
        actions={
            read_prob1;
            write_default_class1;
        }
        size = 1161;
        default_action = write_default_class1;
    }

    @pragma stage 1
    table lookup_leaf_id2 {
        key = { meta.code_f0[6:6]:exact;
                meta.code_f1[3:2]:exact;
                meta.code_f2[6:6]:exact;
                meta.code_f3[6:6]:exact;
                meta.code_f4[2:2]:exact;
                meta.code_f5[5:4]:exact;
                meta.code_f6[2:2]:exact;
                meta.code_f7[5:4]:exact;
                meta.code_f8[12:8]:exact;
                meta.code_f9[5:4]:exact;
                }
        actions={
            read_prob2;
            write_default_class2;
        }
        size = 86;
        default_action = write_default_class2;
    }

    @pragma stage 1
    table lookup_leaf_id3 {
        key = { meta.code_f0[7:7]:exact;
                meta.code_f1[5:4]:exact;
                meta.code_f2[7:7]:exact;
                meta.code_f3[7:7]:exact;
                meta.code_f4[3:3]:exact;
                meta.code_f5[7:6]:exact;
                meta.code_f6[3:3]:exact;
                meta.code_f7[7:6]:exact;
                meta.code_f8[17:13]:exact;
                meta.code_f9[7:6]:exact;
                }
        actions={
            read_prob3;
            write_default_class3;
        }
        size = 166;
        default_action = write_default_class3;
    }

    action read_lable(bit<32> label){
        meta.result = label;
    }

    action write_default_decision() {
        meta.result = 0;
    }

    @pragma stage 2
    table decision {
        key = { meta.tree_0_vote:exact;
                meta.tree_1_vote:exact;
                meta.tree_2_vote:exact;
                meta.tree_3_vote:exact;
                }
        actions={
            read_lable;
            write_default_decision;
        }
        size = 1677;
        default_action = write_default_decision;
    }
    // ************ End of Planter actions and tables **********//

    // ************ Start of Monitoring actions and tables **********//
    // Tracking registers
    register<bit<48>>(NUM_PATIENTS) reg_first_timestamp; // updated at start of each window
    // Features registers
    register<bit<16>>(NUM_PATIENTS) reg_temperature; // temperature feature * 10 
    register<bit<16>>(NUM_PATIENTS) reg_oxygen_saturation; // oxygen saturation feature
    register<bit<16>>(NUM_PATIENTS) reg_pulse_rate; // pulse rate feature
    register<bit<16>>(NUM_PATIENTS) reg_systolic_bp; // systolic blood pressure feature
    register<bit<16>>(NUM_PATIENTS) reg_respiratory_rate; // respiratory rate feature
    register<bit<16>>(NUM_PATIENTS) reg_avpu; // AVPU: 0= Alert, 1 = Voice, 2 = Pain, 3 = Unresponsive
    register<bit<16>>(NUM_PATIENTS) reg_supplemental_oxygen; // supplemental oxygen: 0 = No, 1 = Yes
    register<bit<16>>(NUM_PATIENTS) reg_referral_source; // referral source: 0 = post ICU, 1 = A&E, 2 = general ward, 3 = community referral
    register<bit<8>>(NUM_PATIENTS) reg_age; // age in years
    register<bit<8>>(NUM_PATIENTS) reg_sex; // sex: male: 0, female: 1
    // Prediction register
    register<bit<16>>(NUM_PATIENTS) reg_condition; // condition 
    // Register to track feature presence: 1 bit for each feature per patient
    register<bit<1>>(NUM_PATIENTS * 10) reg_feature_present; // feature presence flags for each patient - mimmicks 2D array

    // Action to check if a feature is present
    action check_presence(out bit<1> presence, bit<32> pid, bit<32> sid) {
        reg_feature_present.read(presence, pid * 10 + sid);
    }

    // Action to check if all features are present
    action check_all_present(out bit<1> all_present, bit<32> pid) {
        all_present = 1;
        bit<1> presence0; bit<1> presence1; bit<1> presence2; bit<1> presence3; bit<1> presence4; 
        bit<1> presence5; bit<1> presence6; bit<1> presence7; bit<1> presence8; bit<1> presence9;

        check_presence(presence0, pid, 0);
        check_presence(presence1, pid, 1);
        check_presence(presence2, pid, 2);
        check_presence(presence3, pid, 3);
        check_presence(presence4, pid, 4);
        check_presence(presence5, pid, 5);
        check_presence(presence6, pid, 6);
        check_presence(presence7, pid, 7);
        check_presence(presence8, pid, 8);
        check_presence(presence9, pid, 9);

        if (presence0 == 0 || presence1 == 0 || presence2 == 0 || presence3 == 0 || presence4 == 0 || 
            presence5 == 0 || presence6 == 0 || presence7 == 0 || presence8 == 0 || presence9 == 0) {
            // if any is absent
            all_present = 0;
        }
    }

    // Action to check if any feature is present
    action check_any_present(out bit<1> any_present, bit<32> pid) {
        any_present = 0;
        bit<1> presence0; bit<1> presence1; bit<1> presence2; bit<1> presence3; bit<1> presence4; 
        bit<1> presence5; bit<1> presence6; bit<1> presence7; bit<1> presence8; bit<1> presence9;

        check_presence(presence0, pid, 0);
        check_presence(presence1, pid, 1);
        check_presence(presence2, pid, 2);
        check_presence(presence3, pid, 3);
        check_presence(presence4, pid, 4);
        check_presence(presence5, pid, 5);
        check_presence(presence6, pid, 6);
        check_presence(presence7, pid, 7);
        check_presence(presence8, pid, 8);
        check_presence(presence9, pid, 9);

        if (presence0 == 1 || presence1 == 1 || presence2 == 1 || presence3 == 1 || presence4 == 1 || 
            presence5 == 1 || presence6 == 1 || presence7 == 1 || presence8 == 1 || presence9 == 1) {
            // if any is present
            any_present = 1;
        }
    }

    // Action to read all features
    action read_all_features(bit<32> pid){
        reg_temperature.read(meta.temperature, pid);
        reg_oxygen_saturation.read(meta.oxygen_saturation, pid);
        reg_pulse_rate.read(meta.pulse_rate, pid);
        reg_systolic_bp.read(meta.systolic_bp, pid);
        reg_respiratory_rate.read(meta.respiratory_rate, pid);
        reg_avpu.read(meta.avpu, pid);
        reg_supplemental_oxygen.read(meta.supplemental_oxygen, pid);
        reg_referral_source.read(meta.referral_source, pid);
        reg_age.read(meta.age, pid);
        reg_sex.read(meta.sex, pid);
    }

    // Action for re-initializing the registers for a patient
    action reinit_all_feat_regs(bit<32> pid){
        reg_temperature.write(pid, 0);
        reg_oxygen_saturation.write(pid, 0);
        reg_pulse_rate.write(pid, 0);
        reg_systolic_bp.write(pid, 0);
        reg_respiratory_rate.write(pid, 0);
        reg_avpu.write(pid, 0);
        reg_supplemental_oxygen.write(pid, 0);
        reg_referral_source.write(pid, 0);   
        reg_age.write(pid, 0);
        reg_sex.write(pid, 0);
        reg_condition.write(pid, 0);
    }

    // Action that resets the feature presence flags for a patient
    action reset_feature_presence(bit<32> pid) {
        reg_feature_present.write(pid * 10 + 0, 0);
        reg_feature_present.write(pid * 10 + 1, 0);
        reg_feature_present.write(pid * 10 + 2, 0);
        reg_feature_present.write(pid * 10 + 3, 0);
        reg_feature_present.write(pid * 10 + 4, 0);
        reg_feature_present.write(pid * 10 + 5, 0);
        reg_feature_present.write(pid * 10 + 6, 0);
        reg_feature_present.write(pid * 10 + 7, 0);
        reg_feature_present.write(pid * 10 + 8, 0);
        reg_feature_present.write(pid * 10 + 9, 0);
    }

    // Action to pack and send the Planter packet to CPU
    action pack_and_send_to_cpu(bit<32> pid, bit<48> tnow){
        ig_intr_md.egress_spec = CPU_PORT; // Set egress port to CPU
        hdr.Sensor.setInvalid(); // remove sensor header
        hdr.Planter.setValid();  // add Planter header
        hdr.ethernet.etherType = ETHERTYPE_Planter; // Set the ethernet type for Planter
        // Set the Planter header fields
        hdr.Planter.p    = Planter_P;
        hdr.Planter.four = Planter_4;
        hdr.Planter.ver  = Planter_VER;
        hdr.Planter.typ  = 0x01;
        hdr.Planter.patient_id = pid;
        hdr.Planter.timestamp  = tnow;
        hdr.Planter.feature0 = meta.temperature;
        hdr.Planter.feature1 = meta.oxygen_saturation;
        hdr.Planter.feature2 = meta.pulse_rate;
        hdr.Planter.feature3 = meta.systolic_bp;
        hdr.Planter.feature4 = meta.respiratory_rate;
        hdr.Planter.feature5 = meta.avpu;
        hdr.Planter.feature6 = meta.supplemental_oxygen;
        hdr.Planter.feature7 = meta.referral_source;
        hdr.Planter.feature8 = (bit<16>)meta.age;
        hdr.Planter.feature9 = (bit<16>)meta.sex;
        hdr.Planter.result   = 0x63; // No result - set to 99 for debug
    }

    // Prepare features for inference if Planter packet
    action prepare_planter_feats(){
        meta.temperature         = hdr.Planter.feature0;
        meta.oxygen_saturation   = hdr.Planter.feature1;
        meta.pulse_rate          = hdr.Planter.feature2;
        meta.systolic_bp         = hdr.Planter.feature3;
        meta.respiratory_rate    = hdr.Planter.feature4;
        meta.avpu                = hdr.Planter.feature5;
        meta.supplemental_oxygen = hdr.Planter.feature6;
        meta.referral_source     = hdr.Planter.feature7;
        meta.age                 = (bit<8>)hdr.Planter.feature8;
        meta.sex                 = (bit<8>)hdr.Planter.feature9;
    }

    // Create and send alert
    action generate_alert_pkt(bit<32> pid, bit<48> tnow, bit<32> alert_value) {
        hdr.Sensor.setInvalid(); // remove sensor header
        hdr.Planter.setInvalid(); // remove Planter header
        hdr.Alert.setValid();
        hdr.ethernet.etherType = ETHERTYPE_Alert; // Set the ethernet type for Alert
        hdr.Alert.patient_id   = pid;
        hdr.Alert.timestamp    = tnow;
        hdr.Alert.alert_value  = alert_value;
        ig_intr_md.egress_spec = MONITORING_PORT; // Send to monitoring port
    }

    apply {
        bit<1> runInference = 0;

        if (hdr.Sensor.isValid()) {
            bit<32> pid = hdr.Sensor.patient_id;
            bit<32> sid = hdr.Sensor.sensor_id;
            bit<16> feature_value = hdr.Sensor.feature_value;

            if (pid < NUM_PATIENTS && pid >= 0) {
                bit<48> tfirst;
                bit<48> tnow = ig_intr_md.ingress_global_timestamp;
                reg_first_timestamp.read(tfirst, pid);

                bit<48> delta = tnow - tfirst;

                // Heartbeat packet logic
                if (sid == 999) {
                    // Heartbeat: check for timed-out window and close if needed
                    if (tfirst != 0 && delta >= TIMEOUT_NS && delta < (TIMEOUT_NS + QUIET_NS)) {
                        bit<1> any_feature_present;
                        check_any_present(any_feature_present, pid);
                        if (any_feature_present == 1) {
                            read_all_features(pid);
                            pack_and_send_to_cpu(pid, tnow);
                        } else{
                            drop(); // Drop heartbeat if no features present
                        }
                        reg_first_timestamp.write(pid, 0);
                        reinit_all_feat_regs(pid);
                        reset_feature_presence(pid);
                    }else{
                        drop(); // Drop heartbeat if not in expected time window
                    }
                }
                // End heartbeat logic
                else if (tfirst == 0) {
                    // No window open, start new window
                    reg_first_timestamp.write(pid, tnow);
                    reg_feature_present.write(pid * 10 + sid, 1);
                    switch (sid) {
                        0:  { reg_temperature.write(pid, feature_value); }
                        1:  { reg_oxygen_saturation.write(pid, feature_value); }
                        2:  { reg_pulse_rate.write(pid, feature_value); }
                        3:  { reg_systolic_bp.write(pid, feature_value); }
                        4:  { reg_respiratory_rate.write(pid, feature_value); }
                        5:  { reg_avpu.write(pid, feature_value); }
                        6:  { reg_supplemental_oxygen.write(pid, feature_value); }
                        7:  { reg_referral_source.write(pid, feature_value); }
                        8:  { reg_age.write(pid, feature_value[7:0]); }
                        9:  { reg_sex.write(pid, feature_value[7:0]); }
                    }
                } else if (delta < TIMEOUT_NS) {
                    // Within window, aggregate feature
                    reg_feature_present.write(pid * 10 + sid, 1);
                    switch (sid) {
                        0:  { reg_temperature.write(pid, feature_value); }
                        1:  { reg_oxygen_saturation.write(pid, feature_value); }
                        2:  { reg_pulse_rate.write(pid, feature_value); }
                        3:  { reg_systolic_bp.write(pid, feature_value); }
                        4:  { reg_respiratory_rate.write(pid, feature_value); }
                        5:  { reg_avpu.write(pid, feature_value); }
                        6:  { reg_supplemental_oxygen.write(pid, feature_value); }
                        7:  { reg_referral_source.write(pid, feature_value); }
                        8:  { reg_age.write(pid, feature_value[7:0]); }
                        9:  { reg_sex.write(pid, feature_value[7:0]); }
                    }

                    bit<1> all_features_present;
                    check_all_present(all_features_present, pid);

                    if (all_features_present == 1) {
                        read_all_features(pid);
                        runInference = 1;
                        // reset features and timestamp
                        reg_first_timestamp.write(pid, 0);
                        reinit_all_feat_regs(pid);
                        reset_feature_presence(pid);
                    }
                } else if (delta < (TIMEOUT_NS + QUIET_NS)) {
                    // Quiet time: drop late packets
                    drop();
                } else {
                    // After quiet time, treat as new window
                    bit<1> any_feature_present;
                    check_any_present(any_feature_present, pid);

                    if (any_feature_present == 1) {
                        read_all_features(pid);
                        pack_and_send_to_cpu(pid, tnow);
                    }
                    reg_first_timestamp.write(pid, tnow);
                    reinit_all_feat_regs(pid);
                    reset_feature_presence(pid);
                    reg_feature_present.write(pid * 10 + sid, 1);
                    switch (sid) {
                        0:  { reg_temperature.write(pid, feature_value); }
                        1:  { reg_oxygen_saturation.write(pid, feature_value); }
                        2:  { reg_pulse_rate.write(pid, feature_value); }
                        3:  { reg_systolic_bp.write(pid, feature_value); }
                        4:  { reg_respiratory_rate.write(pid, feature_value); }
                        5:  { reg_avpu.write(pid, feature_value); }
                        6:  { reg_supplemental_oxygen.write(pid, feature_value); }
                        7:  { reg_referral_source.write(pid, feature_value); }
                        8:  { reg_age.write(pid, feature_value[7:0]); }
                        9:  { reg_sex.write(pid, feature_value[7:0]); }
                    }
                }
                // After window closes, check if all or some features were present
                // if (tfirst != 0 && delta >= TIMEOUT_NS && delta < (TIMEOUT_NS + QUIET_NS) && sid != 999) {
                //     bit<1> any_feature_present;
                //     check_any_present(any_feature_present, pid);

                //     if (any_feature_present == 1) {
                //         read_all_features(pid);
                //         pack_and_send_to_cpu(pid, tnow);
                //     }
                //     reg_first_timestamp.write(pid, 0);
                //     reinit_all_feat_regs(pid);
                //     reset_feature_presence(pid);
                // }
            } else { // If patient ID is invalid, drop the packet
                drop();
            }
        } else if (hdr.Planter.isValid()) {
            bit<32> pid = hdr.Planter.patient_id;
            prepare_planter_feats();
            runInference = 1;
            reg_first_timestamp.write(pid, 0);
            reinit_all_feat_regs(pid);
            reset_feature_presence(pid);
        } else { //if not a Sensor or Planter packet, drop it
            drop();
        }

        if (runInference == 1) {
            lookup_feature0.apply();
            lookup_feature1.apply();
            lookup_feature2.apply();
            lookup_feature3.apply();
            lookup_feature4.apply();
            lookup_feature5.apply();
            lookup_feature6.apply();
            lookup_feature7.apply();
            lookup_feature8.apply();
            lookup_feature9.apply();
            lookup_leaf_id0.apply();
            lookup_leaf_id1.apply();
            lookup_leaf_id2.apply();
            lookup_leaf_id3.apply();
            decision.apply();

            bit<48> tnow = ig_intr_md.ingress_global_timestamp;
            if (hdr.Sensor.isValid()) {
                generate_alert_pkt(hdr.Sensor.patient_id, tnow, meta.result);
            } else {
                generate_alert_pkt(hdr.Planter.patient_id, tnow, meta.result);
            }
        }
    }
}
/*************************************************************************
*********************** egress Processing********************************
**************************************************************************/

control SwitchEgress(inout header_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t eg_intr_md) {
    apply {
    }
}
/*************************************************************************
***********************  S W I T C H  ************************************
*************************************************************************/

V1Switch(
    SwitchParser(),
    SwitchVerifyChecksum(),
    SwitchIngress(),
    SwitchEgress(),
    SwitchComputeChecksum(),
    SwitchDeparser()
) main;
