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
//  --cpu-port 510

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
    bit<32>  sepPrediction; // Sepsis alert value 
    bit<8>   news2Score; // NEWS2 score
    bit<8>   news2Alert; // NEWS2 alert level
    bit<32>  hfPrediction; // Heart Failure prediction result
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

    bit<8>  code_f0_sep;
    bit<6>  code_f1_sep;
    bit<8>  code_f2_sep;
    bit<8>  code_f3_sep;
    bit<4>  code_f4_sep;
    bit<8>  code_f5_sep;
    bit<4>  code_f6_sep;
    bit<8>  code_f7_sep;
    bit<18> code_f8_sep;
    bit<8>  code_f9_sep;
    bit<7>  sum_prob_sep;
    bit<4>  tree_0_vote_sep;
    bit<4>  tree_1_vote_sep;
    bit<4>  tree_2_vote_sep;
    bit<4>  tree_3_vote_sep;
    bit<7>  tree_0_prob_sep;
    bit<7>  tree_1_prob_sep;
    bit<7>  tree_2_prob_sep;
    bit<7>  tree_3_prob_sep;

    bit<6> code_f0_hf;
    bit<6> code_f1_hf;
    bit<4> code_f2_hf;
    bit<2> code_f3_hf;
    bit<6> code_f4_hf;
    bit<2> code_f5_hf;
    bit<4> code_f6_hf;
    bit<6> code_f7_hf;
    bit<10> code_f8_hf;
    bit<4> code_f9_hf;
    bit<7> sum_prob_hf;
    bit<4> tree_0_vote_hf;
    bit<4> tree_1_vote_hf;
    bit<7> tree_0_prob_hf;
    bit<7> tree_1_prob_hf;

    bit<32>  DstAddr;
    bit<32>  result_sep;
    bit<32>  result_hf;
    bit<8>   flag ;

    // Individual news2 scores for each vital sign
    bit<2> respiratoryRateScore;
    bit<2> oxygenSaturationScore;
    bit<2> systolicBPScore;
    bit<2> pulseRateScore;
    bit<2> consciousnessScore;
    bit<2> temperatureScore;
    bit<8> news2Score;
    bit<8> news2Alert;
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
    // NEWS2 actions and tables
     action set_respiratory_rate_score(bit<2> score) {
        meta.respiratoryRateScore = score;
    }
    action set_oxygen_saturation_score(bit<2> score) {
        meta.oxygenSaturationScore = score;
    }
    action set_systolic_bp_score(bit<2> score) {
        meta.systolicBPScore = score;
    }
    action set_pulse_rate_score(bit<2> score) {
        meta.pulseRateScore = score;
    }
    action set_consciousness_score(bit<2> score) {
        meta.consciousnessScore = score;
    }
    action set_temperature_score(bit<2> score) {
        meta.temperatureScore = score;
    }
    action set_news2_result(bit<8> total_score, bit<8> alert_level) {
       meta.news2Score = total_score;
       meta.news2Alert = alert_level;
    }
    // Table for Respiratory Rate Score
    table respiratory_rate_score {
        key = {
            meta.respiratory_rate: range;
        }
        actions = {
            set_respiratory_rate_score;
            NoAction;
        }
        default_action = NoAction();
        const entries = {
            0..8     : set_respiratory_rate_score(3);
            9..11    : set_respiratory_rate_score(1);
            12..20   : set_respiratory_rate_score(0);
            21..24   : set_respiratory_rate_score(2);
            25..0xFF : set_respiratory_rate_score(3);
        }
    }
    // Table for Oxygen Saturation Score - Scale 1 (normal)
    table oxygen_saturation_score {
        key = {
            meta.oxygen_saturation: range;
        }
        actions = {
            set_oxygen_saturation_score;
            NoAction;
        }
        default_action = NoAction();
        const entries = {
            0..91  : set_oxygen_saturation_score(3);
            92..93 : set_oxygen_saturation_score(2);
            94..95 : set_oxygen_saturation_score(1);
            96..100: set_oxygen_saturation_score(0);
        }
    }
    // Table for Systolic BP Score
    table systolic_bp_score {
        key = {
            meta.systolic_bp: range;
        }
        actions = {
            set_systolic_bp_score;
            NoAction;
        }
        default_action = NoAction();
        const entries = {
            0..90    : set_systolic_bp_score(3);
            91..100  : set_systolic_bp_score(2);
            101..110 : set_systolic_bp_score(1);
            111..219 : set_systolic_bp_score(0);
            220..0xFFFF : set_systolic_bp_score(3);
        }
    }
    // Table for Pulse Rate Score
    table pulse_rate_score {
        key = {
            meta.pulse_rate: range;
        }
        actions = {
            set_pulse_rate_score;
            NoAction;
        }
        default_action = NoAction();
        const entries = {
            0..40   : set_pulse_rate_score(3);
            41..50  : set_pulse_rate_score(1);
            51..90  : set_pulse_rate_score(0);
            91..110 : set_pulse_rate_score(1);
            111..130: set_pulse_rate_score(2);
            131..0xFF: set_pulse_rate_score(3);
        }
    }
    // Table for Consciousness Level Score
    table consciousness_score {
        key = {
            meta.avpu: exact;
        }
        actions = {
            set_consciousness_score;
            NoAction;
        }
        default_action = NoAction();
        const entries = {
            0 : set_consciousness_score(0);
            1 : set_consciousness_score(3);
            2 : set_consciousness_score(3);
            3 : set_consciousness_score(3);
        }
    }
    // Table for Temperature Score
    table temperature_score {
        key = {
            meta.temperature: range;  // Note: Temperature is scaled *10
        }
        actions = {
            set_temperature_score;
            NoAction;
        }
        default_action = NoAction();
        const entries = {
            0..350    : set_temperature_score(3);
            351..360  : set_temperature_score(1);
            361..380  : set_temperature_score(0);
            381..390  : set_temperature_score(1);
            391..0xFFFF : set_temperature_score(2);
        }
    }
    // Final table to calculate total score and alert level
    table news2_aggregate {
        key = {
            meta.respiratoryRateScore    : exact;
            meta.oxygenSaturationScore   : exact;
            meta.systolicBPScore         : exact;
            meta.pulseRateScore          : exact;
            meta.consciousnessScore      : exact;
            meta.temperatureScore        : exact;
            meta.supplemental_oxygen     : exact;
        }
        actions = {
            set_news2_result;
            NoAction;
        }
        default_action = NoAction();
        size = 8200;
    }

    // Planter actions and tables
    action extract_feature0_sep(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }
    action extract_feature1_sep(out bit<6> meta_code, bit<6> tree){
        meta_code = tree;
    }
    action extract_feature2_sep(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }
    action extract_feature3_sep(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }
    action extract_feature4_sep(out bit<4> meta_code, bit<4> tree){
        meta_code = tree;
    }
    action extract_feature5_sep(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }
    action extract_feature6_sep(out bit<4> meta_code, bit<4> tree){
        meta_code = tree;
    }
    action extract_feature7_sep(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }
    action extract_feature8_sep(out bit<18> meta_code, bit<18> tree){
        meta_code = tree;
    }
    action extract_feature9_sep(out bit<8> meta_code, bit<8> tree){
        meta_code = tree;
    }

    @pragma stage 0
    table lookup_feature0_sep {
        key = {meta.temperature:ternary; }
        actions = {
            extract_feature0_sep(meta.code_f0_sep);
            NoAction;
            }
        size = 16;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature1_sep {
        key = { meta.oxygen_saturation:ternary; }
        actions = {
            extract_feature1_sep(meta.code_f1_sep);
            NoAction;
            }
        size = 10;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature2_sep {
        key = { meta.pulse_rate:ternary; }
        actions = {
            extract_feature2_sep(meta.code_f2_sep);
            NoAction;
            }
        size = 13;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature3_sep {
        key = { meta.systolic_bp:ternary; }
        actions = {
            extract_feature3_sep(meta.code_f3_sep);
            NoAction;
            }
        size = 17;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature4_sep {
        key = { meta.respiratory_rate:ternary; }
        actions = {
            extract_feature4_sep(meta.code_f4_sep);
            NoAction;
            }
        size = 7;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature5_sep {
        key = { meta.avpu:ternary; }
        actions = {
            extract_feature5_sep(meta.code_f5_sep);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature6_sep {
        key = { meta.supplemental_oxygen:ternary; }
        actions = {
            extract_feature6_sep(meta.code_f6_sep);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature7_sep {
        key = { meta.referral_source:ternary; }
        actions = {
            extract_feature7_sep(meta.code_f7_sep);
            NoAction;
            }
        size = 4;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature8_sep {
        key = { meta.age:ternary; }
        actions = {
            extract_feature8_sep(meta.code_f8_sep);
            NoAction;
            }
        size = 28;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature9_sep {
        key = { meta.sex:ternary; }
        actions = {
            extract_feature9_sep(meta.code_f9_sep);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }


    action read_prob0_sep(bit<7> prob, bit<4> vote){
        meta.tree_0_prob_sep = prob;
        meta.tree_0_vote_sep = vote;
    }
    action write_default_class0_sep() {
        meta.tree_0_vote_sep = 0;
    }

    action read_prob1_sep(bit<7> prob, bit<4> vote){
        meta.tree_1_prob_sep = prob;
        meta.tree_1_vote_sep = vote;
    }
    action write_default_class1_sep() {
        meta.tree_1_vote_sep = 0;
    }

    action read_prob2_sep(bit<7> prob, bit<4> vote){
        meta.tree_2_prob_sep = prob;
        meta.tree_2_vote_sep = vote;
    }
    action write_default_class2_sep() {
        meta.tree_2_vote_sep = 0;
    }

    action read_prob3_sep(bit<7> prob, bit<4> vote){
        meta.tree_3_prob_sep = prob;
        meta.tree_3_vote_sep = vote;
    }
    action write_default_class3_sep() {
        meta.tree_3_vote_sep = 0;
    }

    @pragma stage 1
    table lookup_leaf_id0_sep {
        key = { meta.code_f0_sep[2:0]:exact;
                meta.code_f1_sep[0:0]:exact;
                meta.code_f2_sep[2:0]:exact;
                meta.code_f3_sep[2:0]:exact;
                meta.code_f4_sep[0:0]:exact;
                meta.code_f5_sep[1:0]:exact;
                meta.code_f6_sep[0:0]:exact;
                meta.code_f7_sep[1:0]:exact;
                meta.code_f8_sep[3:0]:exact;
                meta.code_f9_sep[1:0]:exact;
                }
        actions={
            read_prob0_sep;
            write_default_class0_sep;
        }
        size = 648;
        default_action = write_default_class0_sep;
    }

    @pragma stage 1
    table lookup_leaf_id1_sep {
        key = { meta.code_f0_sep[5:3]:exact;
                meta.code_f1_sep[1:1]:exact;
                meta.code_f2_sep[5:3]:exact;
                meta.code_f3_sep[5:3]:exact;
                meta.code_f4_sep[1:1]:exact;
                meta.code_f5_sep[3:2]:exact;
                meta.code_f6_sep[1:1]:exact;
                meta.code_f7_sep[3:2]:exact;
                meta.code_f8_sep[7:4]:exact;
                meta.code_f9_sep[3:2]:exact;
                }
        actions={
            read_prob1_sep;
            write_default_class1_sep;
        }
        size = 1161;
        default_action = write_default_class1_sep;
    }

    @pragma stage 1
    table lookup_leaf_id2_sep {
        key = { meta.code_f0_sep[6:6]:exact;
                meta.code_f1_sep[3:2]:exact;
                meta.code_f2_sep[6:6]:exact;
                meta.code_f3_sep[6:6]:exact;
                meta.code_f4_sep[2:2]:exact;
                meta.code_f5_sep[5:4]:exact;
                meta.code_f6_sep[2:2]:exact;
                meta.code_f7_sep[5:4]:exact;
                meta.code_f8_sep[12:8]:exact;
                meta.code_f9_sep[5:4]:exact;
                }
        actions={
            read_prob2_sep;
            write_default_class2_sep;
        }
        size = 86;
        default_action = write_default_class2_sep;
    }

    @pragma stage 1
    table lookup_leaf_id3_sep {
        key = { meta.code_f0_sep[7:7]:exact;
                meta.code_f1_sep[5:4]:exact;
                meta.code_f2_sep[7:7]:exact;
                meta.code_f3_sep[7:7]:exact;
                meta.code_f4_sep[3:3]:exact;
                meta.code_f5_sep[7:6]:exact;
                meta.code_f6_sep[3:3]:exact;
                meta.code_f7_sep[7:6]:exact;
                meta.code_f8_sep[17:13]:exact;
                meta.code_f9_sep[7:6]:exact;
                }
        actions={
            read_prob3_sep;
            write_default_class3_sep;
        }
        size = 166;
        default_action = write_default_class3_sep;
    }

    action read_lable_sep(bit<32> label){
        meta.result_sep = label;
    }

    action write_default_decision_sep() {
        meta.result_sep = 0;
    }

    @pragma stage 2
    table decision_sep {
        key = { meta.tree_0_vote_sep:exact;
                meta.tree_1_vote_sep:exact;
                meta.tree_2_vote_sep:exact;
                meta.tree_3_vote_sep:exact;
                }
        actions={
            read_lable_sep;
            write_default_decision_sep;
        }
        size = 1677;
        default_action = write_default_decision_sep;
    }

    // Tables and actions for Heart Failure prediction
     action extract_feature0_hf(out bit<6> meta_code, bit<6> tree){
        meta_code = tree;
    }

    action extract_feature1_hf(out bit<6> meta_code, bit<6> tree){
        meta_code = tree;
    }

    action extract_feature2_hf(out bit<4> meta_code, bit<4> tree){
        meta_code = tree;
    }

    action extract_feature3_hf(out bit<2> meta_code, bit<2> tree){
        meta_code = tree;
    }

    action extract_feature4_hf(out bit<6> meta_code, bit<6> tree){
        meta_code = tree;
    }

    action extract_feature5_hf(out bit<2> meta_code, bit<2> tree){
        meta_code = tree;
    }

    action extract_feature6_hf(out bit<4> meta_code, bit<4> tree){
        meta_code = tree;
    }

    action extract_feature7_hf(out bit<6> meta_code, bit<6> tree){
        meta_code = tree;
    }

    action extract_feature8_hf(out bit<10> meta_code, bit<10> tree){
        meta_code = tree;
    }

    action extract_feature9_hf(out bit<4> meta_code, bit<4> tree){
        meta_code = tree;
    }

    @pragma stage 0
    table lookup_feature0_hf {
        key = { meta.temperature:ternary; }
        actions = {
            extract_feature0_hf(meta.code_f0_hf);
            NoAction;
            }
        size = 17;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature1_hf {
        key = { meta.oxygen_saturation:ternary; }
        actions = {
            extract_feature1_hf(meta.code_f1_hf);
            NoAction;
            }
        size = 14;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature2_hf {
        key = { meta.pulse_rate:ternary; }
        actions = {
            extract_feature2_hf(meta.code_f2_hf);
            NoAction;
            }
        size = 13;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature3_hf {
        key = { meta.systolic_bp:ternary; }
        actions = {
            extract_feature3_hf(meta.code_f3_hf);
            NoAction;
            }
        size = 9;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature4_hf {
        key = { meta.respiratory_rate:ternary; }
        actions = {
            extract_feature4_hf(meta.code_f4_hf);
            NoAction;
            }
        size = 10;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature5_hf {
        key = { meta.avpu:ternary; }
        actions = {
            extract_feature5_hf(meta.code_f5_hf);
            NoAction;
            }
        size = 1;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature6_hf {
        key = { meta.supplemental_oxygen:ternary; }
        actions = {
            extract_feature6_hf(meta.code_f6_hf);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature7_hf {
        key = { meta.referral_source:ternary; }
        actions = {
            extract_feature7_hf(meta.code_f7_hf);
            NoAction;
            }
        size = 3;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature8_hf {
        key = { meta.age:ternary; }
        actions = {
            extract_feature8_hf(meta.code_f8_hf);
            NoAction;
            }
        size = 26;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature9_hf {
        key = { meta.sex:ternary; }
        actions = {
            extract_feature9_hf(meta.code_f9_hf);
            NoAction;
            }
        size = 2;
        default_action = NoAction;
    }


    action read_prob0_hf(bit<7> prob, bit<4> vote){
        meta.tree_0_prob_hf = prob;
        meta.tree_0_vote_hf = vote;
    }
    action write_default_class0_hf() {
        meta.tree_0_vote_hf = 8;
    }


    action read_prob1_hf(bit<7> prob, bit<4> vote){
        meta.tree_1_prob_hf = prob;
        meta.tree_1_vote_hf = vote;
    }
    action write_default_class1_hf() {
        meta.tree_1_vote_hf = 8;
    }

    @pragma stage 1
    table lookup_leaf_id0_hf {
        key = { meta.code_f0_hf[2:0]:exact;
                meta.code_f1_hf[2:0]:exact;
                meta.code_f2_hf[1:0]:exact;
                meta.code_f3_hf[0:0]:exact;
                meta.code_f4_hf[2:0]:exact;
                meta.code_f5_hf[0:0]:exact;
                meta.code_f6_hf[1:0]:exact;
                meta.code_f7_hf[2:0]:exact;
                meta.code_f8_hf[4:0]:exact;
                meta.code_f9_hf[1:0]:exact;
                }
        actions={
            read_prob0_hf;
            write_default_class0_hf;
        }
        size = 4680;
        default_action = write_default_class0_hf;
    }

    @pragma stage 1
    table lookup_leaf_id1_hf {
        key = { meta.code_f0_hf[5:3]:exact;
                meta.code_f1_hf[5:3]:exact;
                meta.code_f2_hf[3:2]:exact;
                meta.code_f3_hf[1:1]:exact;
                meta.code_f4_hf[5:3]:exact;
                meta.code_f5_hf[1:1]:exact;
                meta.code_f6_hf[3:2]:exact;
                meta.code_f7_hf[5:3]:exact;
                meta.code_f8_hf[9:5]:exact;
                meta.code_f9_hf[3:2]:exact;
                }
        actions={
            read_prob1_hf;
            write_default_class1_hf;
        }
        size = 8496;
        default_action = write_default_class1_hf;
    }

    action read_lable_hf(bit<32> label){
        meta.result_hf = label;
    }

    action write_default_decision_hf() {
        meta.result_hf = 0;
    }

    table decision_hf {
        key = { meta.tree_0_vote_hf:exact;
                meta.tree_1_vote_hf:exact;
                }
        actions={
            read_lable_hf;
            write_default_decision_hf;
        }
        size = 46;
        default_action = write_default_decision_hf;
    }

    // End of Planter actions and tables 

    // Monitoring actions and tables
    // Tracking registers
    register<bit<48>>(NUM_PATIENTS) reg_first_timestamp; // updated at start of each window
    // Features registers
    register<bit<16>>(NUM_PATIENTS) reg_temperature; // temperature feature * 10 
    register<bit<16>>(NUM_PATIENTS) reg_oxygen_saturation; 
    register<bit<16>>(NUM_PATIENTS) reg_pulse_rate; 
    register<bit<16>>(NUM_PATIENTS) reg_systolic_bp; 
    register<bit<16>>(NUM_PATIENTS) reg_respiratory_rate;
    register<bit<16>>(NUM_PATIENTS) reg_avpu; // 0= Alert, 1 = Voice, 2 = Pain, 3 = Unresponsive
    register<bit<16>>(NUM_PATIENTS) reg_supplemental_oxygen; // 0 = No, 1 = Yes
    register<bit<16>>(NUM_PATIENTS) reg_referral_source; //  0 = post ICU, 1 = A&E, 2 = general ward, 3 = community referral
    register<bit<8>>(NUM_PATIENTS) reg_age;
    register<bit<8>>(NUM_PATIENTS) reg_sex; // 0, female: 1
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
    action generate_alert_pkt(bit<32> pid, bit<48> tnow) {
        hdr.Sensor.setInvalid(); // remove sensor header
        hdr.Planter.setInvalid(); // remove Planter header
        hdr.Alert.setValid();
        hdr.ethernet.etherType = ETHERTYPE_Alert; // Set the ethernet type for Alert
        hdr.Alert.patient_id   = pid;
        hdr.Alert.timestamp    = tnow;
        hdr.Alert.sepPrediction= meta.result_sep; // sepsis prediction result
        hdr.Alert.news2Score   = meta.news2Score; 
        hdr.Alert.news2Alert   = meta.news2Alert;  
        hdr.Alert.hfPrediction = meta.result_hf; // Heart Failure prediction result
        ig_intr_md.egress_spec = MONITORING_PORT; // to monitoring port
    }

    apply {
        bit<1> runInference = 0;

        if (hdr.Sensor.isValid()) {
            bit<32> pid = hdr.Sensor.patient_id;
            bit<32> sid = hdr.Sensor.sensor_id;
            bit<16> feature_value = hdr.Sensor.feature_value;

            if (pid < NUM_PATIENTS && pid >= 0) { // Check if patient ID is valid
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
                }// End heartbeat logic
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
            // calculate NEWS2 scores
            respiratory_rate_score.apply();
            oxygen_saturation_score.apply();
            systolic_bp_score.apply();
            pulse_rate_score.apply();
            consciousness_score.apply();
            temperature_score.apply();
            news2_aggregate.apply();
            // Feature tables for Sepsis prediction
            lookup_feature0_sep.apply();
            lookup_feature1_sep.apply();
            lookup_feature2_sep.apply();
            lookup_feature3_sep.apply();
            lookup_feature4_sep.apply();
            lookup_feature5_sep.apply();
            lookup_feature6_sep.apply();
            lookup_feature7_sep.apply();
            lookup_feature8_sep.apply();
            lookup_feature9_sep.apply();
            // Feature tables for Heart Failure prediction
            lookup_feature0_hf.apply();
            lookup_feature1_hf.apply();
            lookup_feature2_hf.apply();
            lookup_feature3_hf.apply();
            lookup_feature4_hf.apply();
            lookup_feature5_hf.apply();
            lookup_feature6_hf.apply();
            lookup_feature7_hf.apply();
            lookup_feature8_hf.apply();
            lookup_feature9_hf.apply();
            // Code tables for Sepsis prediction
            lookup_leaf_id0_sep.apply();
            lookup_leaf_id1_sep.apply();
            lookup_leaf_id2_sep.apply();
            lookup_leaf_id3_sep.apply();
            // Code tables for Heart Failure prediction
            lookup_leaf_id0_hf.apply();
            lookup_leaf_id1_hf.apply();
            // decision tables
            decision_sep.apply();
            decision_hf.apply();

            bit<48> tnow = ig_intr_md.ingress_global_timestamp;
            if (hdr.Sensor.isValid()) {
                generate_alert_pkt(hdr.Sensor.patient_id, tnow);
            } else {
                generate_alert_pkt(hdr.Planter.patient_id, tnow);
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
