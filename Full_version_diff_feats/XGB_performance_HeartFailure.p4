
#include <core.p4>
#include <v1model.p4>

/*************************************************************************
*********************** headers and metadata *****************************
*************************************************************************/

const bit<16> ETHERTYPE_Planter = 0x1234;
const bit<8>  Planter_P     = 0x50;   // 'P'
const bit<8>  Planter_4     = 0x34;   // '4'
const bit<8>  Planter_VER   = 0x01;   // v0.1

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
    bit<16> patient_id;
    bit<32> timestamp;
    bit<32> feature0;
    bit<32> feature1;
    bit<32> feature2;
    bit<32> feature3;
    bit<32> feature4;
    bit<32> feature5;
    bit<32> result;
}

struct header_t {
    ethernet_h   ethernet;
    Planter_h    Planter;
}

struct metadata_t {
    bit<16> temperature;
    bit<16> oxygen_saturation;
    bit<16> pulse_rate;
    bit<16> systolic_bp;
    bit<16> respiratory_rate;
    bit<16> referral_source;
    
    bit<18> code_f0_hf;
    bit<16> code_f1_hf;
    bit<14> code_f2_hf;
    bit<12> code_f3_hf;
    bit<12> code_f4_hf;
    bit<14> code_f5_hf;
    bit<7> sum_prob_hf;
    bit<4> tree_0_vote_hf;
    bit<4> tree_1_vote_hf;
    bit<4> tree_2_vote_hf;
    bit<4> tree_3_vote_hf;
    bit<7> tree_0_prob_hf;
    bit<7> tree_1_prob_hf;
    bit<7> tree_2_prob_hf;
    bit<7> tree_3_prob_hf;
    bit<32>  DstAddr;
    bit<32> result_hf;
    bit<8> flag ;
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
        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
        ETHERTYPE_Planter : check_planter_version;
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
    
    action extract_feature0_hf(out bit<18> meta_code, bit<18> tree){
        meta_code = tree;
    }

    action extract_feature1_hf(out bit<16> meta_code, bit<16> tree){
        meta_code = tree;
    }

    action extract_feature2_hf(out bit<14> meta_code, bit<14> tree){
        meta_code = tree;
    }

    action extract_feature3_hf(out bit<12> meta_code, bit<12> tree){
        meta_code = tree;
    }

    action extract_feature4_hf(out bit<12> meta_code, bit<12> tree){
        meta_code = tree;
    }

    action extract_feature5_hf(out bit<14> meta_code, bit<14> tree){
        meta_code = tree;
    }    
    
    @pragma stage 0
    table lookup_feature0_hf {
        key = { meta.temperature:ternary; }
        actions = {
            extract_feature0_hf(meta.code_f0_hf);
            NoAction;
            }
        size = 32;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature1_hf {
        key = { meta.pulse_rate:ternary; }
        actions = {
            extract_feature1_hf(meta.code_f1_hf);
            NoAction;
            }
        size = 32;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature2_hf {
        key = { meta.systolic_bp:ternary; }
        actions = {
            extract_feature2_hf(meta.code_f2_hf);
            NoAction;
            }
        size = 35;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature3_hf {
        key = { meta.respiratory_rate:ternary; }
        actions = {
            extract_feature3_hf(meta.code_f3_hf);
            NoAction;
            }
        size = 10;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature4_hf {
        key = { meta.referral_source:ternary; }
        actions = {
            extract_feature4_hf(meta.code_f4_hf);
            NoAction;
            }
        size = 4;
        default_action = NoAction;
    }

    @pragma stage 0
    table lookup_feature5_hf {
        key = { meta.oxygen_saturation:ternary; }
        actions = {
            extract_feature5_hf(meta.code_f5_hf);
            NoAction;
            }
        size = 18;
        default_action = NoAction;
    }

    action read_prob0_hf(bit<7> prob, bit<4> vote){
        meta.tree_0_prob_hf = prob;
        meta.tree_0_vote_hf = vote;
    }
    action write_default_class0_hf() {
        meta.tree_0_vote_hf = 1;
    }


    action read_prob1_hf(bit<7> prob, bit<4> vote){
        meta.tree_1_prob_hf = prob;
        meta.tree_1_vote_hf = vote;
    }
    action write_default_class1_hf() {
        meta.tree_1_vote_hf = 1;
    }


    action read_prob2_hf(bit<7> prob, bit<4> vote){
        meta.tree_2_prob_hf = prob;
        meta.tree_2_vote_hf = vote;
    }
    action write_default_class2_hf() {
        meta.tree_2_vote_hf = 1;
    }


    action read_prob3_hf(bit<7> prob, bit<4> vote){
        meta.tree_3_prob_hf = prob;
        meta.tree_3_vote_hf = vote;
    }
    action write_default_class3_hf() {
        meta.tree_3_vote_hf = 1;
    }    
    
    @pragma stage 1
    table lookup_leaf_id0_hf {
        key = { meta.code_f0_hf[3:0]:exact;
                meta.code_f1_hf[3:0]:exact;
                meta.code_f2_hf[2:0]:exact;
                meta.code_f3_hf[2:0]:exact;
                meta.code_f4_hf[2:0]:exact;
                meta.code_f5_hf[2:0]:exact;
                }
        actions={
            read_prob0_hf;
            write_default_class0_hf;
        }
        size = 6840;
        default_action = write_default_class0_hf;
    }

    @pragma stage 1
    table lookup_leaf_id1_hf {
        key = { meta.code_f0_hf[7:4]:exact;
                meta.code_f1_hf[7:4]:exact;
                meta.code_f2_hf[5:3]:exact;
                meta.code_f3_hf[5:3]:exact;
                meta.code_f4_hf[5:3]:exact;
                meta.code_f5_hf[5:3]:exact;
                }
        actions={
            read_prob1_hf;
            write_default_class1_hf;
        }
        size = 5952;
        default_action = write_default_class1_hf;
    }

    @pragma stage 1
    table lookup_leaf_id2_hf {
        key = { meta.code_f0_hf[12:8]:exact;
                meta.code_f1_hf[11:8]:exact;
                meta.code_f2_hf[9:6]:exact;
                meta.code_f3_hf[8:6]:exact;
                meta.code_f4_hf[8:6]:exact;
                meta.code_f5_hf[9:6]:exact;
                }
        actions={
            read_prob2_hf;
            write_default_class2_hf;
        }
        size = 23100;
        default_action = write_default_class2_hf;
    }

    @pragma stage 1
    table lookup_leaf_id3_hf {
        key = { meta.code_f0_hf[17:13]:exact;
                meta.code_f1_hf[15:12]:exact;
                meta.code_f2_hf[13:10]:exact;
                meta.code_f3_hf[11:9]:exact;
                meta.code_f4_hf[11:9]:exact;
                meta.code_f5_hf[13:10]:exact;
                }
        actions={
            read_prob3_hf;
            write_default_class3_hf;
        }
        size = 19992;
        default_action = write_default_class3_hf;
    }    
    
    action read_lable_hf(bit<32> label){
        hdr.Planter.result = label;
    }

    action write_default_decision_hf() {
        hdr.Planter.result = 0;
    }

    table decision_hf {
        key = { meta.tree_0_vote_hf:exact;
                meta.tree_1_vote_hf:exact;
                meta.tree_2_vote_hf:exact;
                meta.tree_3_vote_hf:exact;
                }
        actions={
            read_lable_hf;
            write_default_decision_hf;
        }
        size = 6555;
        default_action = write_default_decision_hf;
    }    
    
    apply{
        lookup_feature0_hf.apply();
        lookup_feature1_hf.apply();
        lookup_feature2_hf.apply();
        lookup_feature3_hf.apply();
        lookup_feature4_hf.apply();
        lookup_feature5_hf.apply();
        lookup_leaf_id0_hf.apply();
        lookup_leaf_id1_hf.apply();
        lookup_leaf_id2_hf.apply();
        lookup_leaf_id3_hf.apply();
        decision_hf.apply();
        send(1);
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