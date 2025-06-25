/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

// Custom EtherType for our NEWS2 packets
const bit<16> TYPE_NEWS2 = 0x9876;

// Constants for consciousness levels
const bit<8> CONSCIOUSNESS_ALERT = 0;
const bit<8> CONSCIOUSNESS_CONFUSED = 1;
const bit<8> CONSCIOUSNESS_VOICE = 2;
const bit<8> CONSCIOUSNESS_PAIN = 3;
const bit<8> CONSCIOUSNESS_UNRESPONSIVE = 4;

// Constants for alert levels
const bit<8> ALERT_LOW = 0;
const bit<8> ALERT_MEDIUM = 1;
const bit<8> ALERT_HIGH = 2;

/*************************************************************************
 ***********************  H E A D E R S  *********************************
 *************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header news2_t {
    // patient ID (for identification purposes)
    bit<16> patientID;                // Unique identifier for the patient
    bit<32> timestamp;                // Timestamp of the measurement (in seconds since epoch)
    // Input vital signs (integers)
    bit<8>  respiratoryRate;           // breaths per minute (scaled)
    bit<8>  oxygenSaturation;          // percentage
    bit<16> systolicBP;                // mmHg
    bit<8>  pulseRate;                 // beats per minute
    bit<8>  consciousnessLevel;        // enum: 0=Alert, 1=Confused, 2=Voice, 3=Pain, 4=Unresponsive
    bit<16>  temperature;               // temperature in Celsius (scaled * 10)
    bit<8>  supplementalOxygen;        // 0=No, 1=Yes (if patient is on supplemental oxygen)
    
    // Output fields
    bit<8>  news2Score;                // Total NEWS2 score
    bit<8>  alertLevel;                // 0=Low, 1=Medium, 2=High
}

struct metadata_t {
    // Individual scores for each parameter
    bit<2> respiratoryRateScore;
    bit<2> oxygenSaturationScore;
    bit<2> systolicBPScore;
    bit<2> pulseRateScore;
    bit<2> consciousnessScore;
    bit<2> temperatureScore;
}

struct headers {
    ethernet_t ethernet;
    news2_t    news2;
}

/*************************************************************************
 ***********************  P A R S E R  ***********************************
 *************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata_t meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_NEWS2: parse_news2;
            default: accept;
        }
    }

    state parse_news2 {
        packet.extract(hdr.news2);
        transition accept;
    }
}

/*************************************************************************
 ************   C H E C K S U M    V E R I F I C A T I O N   *************
 *************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata_t meta) {
    apply { }
}

/*************************************************************************
 **************  I N G R E S S   P R O C E S S I N G   *******************
 *************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata_t meta,
                  inout standard_metadata_t standard_metadata) {

    // Actions for each table
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
        hdr.news2.news2Score = total_score;
        hdr.news2.alertLevel = alert_level;
    }

    // Table for Respiratory Rate Score
    table respiratory_rate_score {
        key = {
            hdr.news2.respiratoryRate: range;
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
            hdr.news2.oxygenSaturation: range;
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
            hdr.news2.systolicBP: range;
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
            hdr.news2.pulseRate: range;
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
            hdr.news2.consciousnessLevel: exact;
        }
        actions = {
            set_consciousness_score;
            NoAction;
        }
        default_action = NoAction();
        const entries = {
            CONSCIOUSNESS_ALERT        : set_consciousness_score(0);
            CONSCIOUSNESS_CONFUSED     : set_consciousness_score(3);
            CONSCIOUSNESS_VOICE        : set_consciousness_score(3);
            CONSCIOUSNESS_PAIN         : set_consciousness_score(3);
            CONSCIOUSNESS_UNRESPONSIVE : set_consciousness_score(3);
        }
    }

    // Table for Temperature Score
    table temperature_score {
        key = {
            hdr.news2.temperature: range;  // Note: Temperature is scaled *10
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
            hdr.news2.supplementalOxygen : exact;
        }
        actions = {
            set_news2_result;
            NoAction;
        }
        default_action = NoAction();
        size = 8200;
    }

    apply {
        if (hdr.news2.isValid()) {
            // Apply the tables to calculate individual scores
            respiratory_rate_score.apply();
            oxygen_saturation_score.apply();
            systolic_bp_score.apply();
            pulse_rate_score.apply();
            consciousness_score.apply();
            temperature_score.apply();
            
            // Use the aggregate table to get the final score
            news2_aggregate.apply();
        }
        
        // Forward the packet by setting the egress port
        standard_metadata.egress_spec = 2; 
    }
}

/*************************************************************************
 ****************  E G R E S S   P R O C E S S I N G   *******************
 *************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

/*************************************************************************
 *************   C H E C K S U M    C O M P U T A T I O N   **************
 *************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata_t meta) {
    apply { }
}

/*************************************************************************
 ***********************  D E P A R S E R  *******************************
 *************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.news2);
    }
}

/*************************************************************************
 ***********************  S W I T C H  *******************************
 *************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;