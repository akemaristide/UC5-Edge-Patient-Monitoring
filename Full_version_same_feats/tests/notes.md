# 🧪 IoT Gateway Test Suite - How Each Test Works

## 🔍 Scalability Test (5 Key Points):
• 🧵 **Concurrent Patient Simulation**: Creates separate threads for each "patient" (10, 20, 30... up to 100), where each thread independently sends sensor data for 4 minutes straight

• ⏰ **Realistic Timing**: Each patient waits 30-300 seconds between sending complete sensor windows (mimicking real hospital patient monitoring intervals), making it very slow but realistic

• 📊 **Step-by-Step Load Testing**: Tests 10 patients for 4 minutes, then 20 patients for 4 minutes, then 30 patients for 4 minutes, etc. - each step takes ~4.5 minutes total

• 📈 **Success Rate Monitoring**: Counts how many patients successfully generate alerts vs. total patients to find the system's breaking point (stops when <80% success rate)

• ⏳ **Total Time**: With 10 steps (10→100 patients) × 4+ minutes each = ~45+ minutes total - it's testing your system's ability to handle long-term concurrent patient loads, not just burst traffic

**Why it's slow**: Real patient monitoring isn't fast - patients send data every few minutes, and the test needs to run long enough to see if your system can reliably track many patients simultaneously over time! 🏥

---

## 🔍 Latency Test (5 Key Points):
• ⚡ **Two Window Types**: Sends 10 "complete" windows (all 10 sensors) for immediate P4 inference, and 5 "partial" windows (4-8 sensors) that trigger 60-second timeout mechanism

• ⏱️ **Precise Timing**: Measures exact time from first sensor packet sent to alert packet received - includes 0.01s delays between sensors (100ms total per window)

• 🧠 **ML Prediction Analysis**: Captures sepsis predictions, heart failure predictions, and NEWS2 scores from alert packets to verify ML models are working correctly

• 🎯 **Two Response Patterns**: Complete windows get ~500ms responses (direct P4 processing), partial windows get ~60-65 second responses (timeout + controller heartbeat)

• 📊 **Statistical Analysis**: Calculates averages, medians, percentiles, and standard deviations to characterize system performance consistency and reliability

**Why it's fast**: Only sends 15 total patients with 2-second spacing, focuses on measuring response times rather than load testing! ⚡

---

## 🔍 Performance Test (5 Key Points):
• 🚀 **Throughput Testing**: Tests increasing patient rates (10, 20, 40, 80, 160+ patients/minute) to find maximum sustainable throughput before system breaks

• 🖥️ **Gateway Monitoring**: Uses SSH to continuously monitor gateway CPU, memory, BMv2 process stats, and P4 switch responsiveness during each rate test

• ⚖️ **Realistic Load Mix**: Sends 90% complete windows (immediate processing) and 10% partial windows (timeout processing) to simulate real hospital conditions

• 📈 **Rate Limiting**: Calculates precise intervals between patients (e.g., 6 seconds at 10/min, 0.03 seconds at 2000/min) and maintains steady transmission rates

• 🎯 **Breaking Point Detection**: Monitors alert success rates and gateway resource usage to identify when system starts dropping patients or alerts

**Why it takes time**: Each rate tested for 2+ minutes to get stable measurements, plus SSH monitoring overhead and multiple rates tested! 🕐

---

## 🔍 Timeout Test (5 Key Points):
• 🔧 **Missing Sensor Scenarios**: Tests 10 different incomplete data patterns (missing 1, 2, 3+ sensors, critical-only, random patterns) to verify timeout behavior

• ⏰ **Timeout Threshold Testing**: Sends <10 sensors to trigger 60-second timeout mechanism, verifies all scenarios fall within expected 60-75 second range

• 🧠 **ML Imputation Validation**: Tests how well ML models handle missing data - checks if predictions still work with incomplete sensor sets

• 📊 **Sensor Importance Analysis**: Compares prediction accuracy when missing different sensor types (critical vs non-critical) to understand sensor priority

• 🔄 **Heartbeat Dependency**: Relies on controller's 15-second heartbeat schedule to trigger processing of incomplete windows after timeout period

**Why it's moderate time**: Tests 10 scenarios × 3 repetitions × 3 runs each, but each scenario only waits ~65 seconds for timeout responses! ⏳