#!/bin/bash

echo "=== IoT Gateway Patient Monitoring System - Comprehensive Testing Suite ==="
echo "Testing started at: $(date)"
echo

# Check if interfaces are up
echo "Checking network interfaces..."
if ! ip link show enx0c37965f8a0a &>/dev/null; then
    echo "ERROR: enx0c37965f8a0a (monitoring interface) not found"
    exit 1
fi

if ! ip link show enx0c37965f8a10 &>/dev/null; then
    echo "ERROR: enx0c37965f8a10 (sensor interface) not found"
    exit 1
fi

echo "✓ Network interfaces verified"
echo

# Check if bmv2 is running
if ! pgrep -f simple_switch >/dev/null; then
    echo "WARNING: BMv2 switch may not be running"
fi

# Create results directory
RESULTS_DIR="test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"
cd "$RESULTS_DIR"

echo "Results will be saved in: $(pwd)"
echo

# Function to run test with error handling
run_test() {
    local test_name=$1
    local test_script=$2
    local duration=$3
    
    echo "=== Running $test_name ==="
    echo "Estimated duration: $duration"
    echo "Started at: $(date)"
    
    if sudo python3 "../$test_script" > "${test_name,,}_output.txt" 2>&1; then
        echo "✓ $test_name completed successfully"
    else
        echo "✗ $test_name failed - check ${test_name,,}_output.txt for details"
    fi
    
    echo "Completed at: $(date)"
    echo
    
    # Cool down period
    sleep 30
}

# Run all tests
echo "Starting test sequence..."
echo

run_test "Latency Test" "latency_test.py" "10-15 minutes"
run_test "Performance Test" "performance_test.py" "15-20 minutes" 
run_test "Scalability Test" "scalability_test.py" "20-25 minutes"
run_test "Timeout Test" "timeout_test.py" "8-10 minutes"

echo "=== Generating Plots ==="
python3 "../plot_results.py" > plot_output.txt 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Plots generated successfully"
else
    echo "✗ Plot generation failed - check plot_output.txt"
fi

echo
echo "=== Testing Summary ==="
echo "All tests completed at: $(date)"
echo "Results saved in: $(pwd)"
echo
echo "Files generated:"
ls -la *.csv *.png *.txt 2>/dev/null | head -20
echo
echo "To view plots:"
echo "  firefox *.png"
echo "  # or copy to your local machine for viewing"
echo
echo "To analyze CSV data:"
echo "  python3 -c \"import pandas as pd; print(pd.read_csv('latency_results_*.csv').describe())\""
