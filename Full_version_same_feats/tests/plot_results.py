#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import sys
import os

def plot_latency_results():
    """Plot latency test results with prediction analysis"""
    files = glob.glob('latency_results_*.csv')
    if not files:
        print("No latency results found")
        return
    
    latest_file = max(files, key=lambda x: x.split('_')[-1].split('.')[0])
    print(f"Plotting latency results from {latest_file}")
    df = pd.read_csv(latest_file)
    
    if df.empty:
        print("No data in latency results file")
        return
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # Latency distribution
    complete = df[df['window_type'] == 'complete']['latency_ms']
    partial = df[df['window_type'] == 'partial']['latency_ms']
    
    if not complete.empty or not partial.empty:
        axes[0,0].hist([complete.dropna(), partial.dropna()], bins=30, alpha=0.7, 
                       label=['Complete Windows', 'Partial Windows'])
        axes[0,0].set_title('Latency Distribution')
        axes[0,0].set_xlabel('Latency (ms)')
        axes[0,0].set_ylabel('Frequency')
        axes[0,0].legend()
        axes[0,0].grid(True)
    
    # Box plot
    if not complete.empty and not partial.empty:
        data_to_plot = [complete.dropna(), partial.dropna()]
        axes[0,1].boxplot(data_to_plot, labels=['Complete', 'Partial'])
        axes[0,1].set_title('Latency Box Plot')
        axes[0,1].set_ylabel('Latency (ms)')
        axes[0,1].grid(True)
    
    # Time series
    if 'timestamp' in df.columns:
        colors = ['blue' if x == 'complete' else 'red' for x in df['window_type']]
        axes[0,2].scatter(df['timestamp'], df['latency_ms'], c=colors, alpha=0.6)
        axes[0,2].set_title('Latency Over Time')
        axes[0,2].set_xlabel('Time')
        axes[0,2].set_ylabel('Latency (ms)')
        axes[0,2].grid(True)
    
    # CDF
    if not complete.empty and not partial.empty:
        complete_sorted = np.sort(complete.dropna())
        partial_sorted = np.sort(partial.dropna())
        axes[1,0].plot(complete_sorted, np.linspace(0, 1, len(complete_sorted)), label='Complete')
        axes[1,0].plot(partial_sorted, np.linspace(0, 1, len(partial_sorted)), label='Partial')
        axes[1,0].set_title('Latency CDF')
        axes[1,0].set_xlabel('Latency (ms)')
        axes[1,0].set_ylabel('Cumulative Probability')
        axes[1,0].legend()
        axes[1,0].grid(True)
    
    # Prediction Analysis
    if 'sepsis_prediction' in df.columns:
        sepsis_count = (df['sepsis_prediction'] > 0).sum()
        hf_count = (df['hf_prediction'] > 0).sum() if 'hf_prediction' in df.columns else 0
        total = len(df)
        
        prediction_data = [sepsis_count, hf_count, total - sepsis_count - hf_count]
        labels = ['Sepsis Alerts', 'Heart Failure Alerts', 'Normal']
        
        axes[1,1].pie(prediction_data, labels=labels, autopct='%1.1f%%', startangle=90)
        axes[1,1].set_title('Alert Distribution')
    
    # NEWS2 Score Analysis
    if 'news2_score' in df.columns:
        news2_scores = df['news2_score'].dropna()
        if not news2_scores.empty:
            axes[1,2].hist(news2_scores, bins=range(0, int(news2_scores.max()) + 2), alpha=0.7)
            axes[1,2].axvline(x=7, color='r', linestyle='--', label='High Risk Threshold')
            axes[1,2].set_title('NEWS2 Score Distribution')
            axes[1,2].set_xlabel('NEWS2 Score')
            axes[1,2].set_ylabel('Frequency')
            axes[1,2].legend()
            axes[1,2].grid(True)
    
    plt.tight_layout()
    plt.savefig('latency_analysis.png', dpi=300, bbox_inches='tight')
    print("Latency plots saved as latency_analysis.png")

def plot_performance_results():
    """Plot performance test results with gateway monitoring"""
    files = glob.glob('performance_summary_*.csv')
    if not files:
        print("No performance results found")
        return
    
    latest_file = max(files, key=lambda x: x.split('_')[-1].split('.')[0])
    print(f"Plotting performance results from {latest_file}")
    df = pd.read_csv(latest_file)
    
    if df.empty:
        print("No data in performance results file")
        return
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # Throughput
    axes[0,0].plot(df['target_rate'], df['actual_rate'], 'bo-', label='Actual Rate')
    axes[0,0].plot(df['target_rate'], df['target_rate'], 'r--', label='Target Rate')
    axes[0,0].set_title('System Throughput')
    axes[0,0].set_xlabel('Target Rate (patients/min)')
    axes[0,0].set_ylabel('Actual Rate (patients/min)')
    axes[0,0].legend()
    axes[0,0].grid(True)
    
    # Alert Rate
    axes[0,1].plot(df['target_rate'], df['alert_rate_percent'], 'go-')
    axes[0,1].set_title('Alert Generation Rate')
    axes[0,1].set_xlabel('Target Rate (patients/min)')
    axes[0,1].set_ylabel('Alert Rate (%)')
    axes[0,1].grid(True)
    
    # Gateway CPU Usage (updated column names)
    if 'avg_gateway_cpu_percent' in df.columns:
        axes[0,2].plot(df['target_rate'], df['avg_gateway_cpu_percent'], 'ro-', label='Gateway Avg')
        if 'max_gateway_cpu_percent' in df.columns:
            axes[0,2].plot(df['target_rate'], df['max_gateway_cpu_percent'], 'r^--', label='Gateway Max')
        if 'avg_bmv2_cpu_percent' in df.columns:
            axes[0,2].plot(df['target_rate'], df['avg_bmv2_cpu_percent'], 'bo-', label='BMv2 Process')
        axes[0,2].set_title('CPU Usage (Gateway)')
        axes[0,2].set_xlabel('Target Rate (patients/min)')
        axes[0,2].set_ylabel('CPU Usage (%)')
        axes[0,2].legend()
        axes[0,2].grid(True)
    
    # Gateway Memory Usage
    if 'avg_gateway_memory_mb' in df.columns:
        axes[1,0].plot(df['target_rate'], df['avg_gateway_memory_mb'], 'mo-', label='Gateway Memory')
        if 'avg_bmv2_memory_mb' in df.columns:
            axes[1,0].plot(df['target_rate'], df['avg_bmv2_memory_mb'], 'co-', label='BMv2 Memory')
        axes[1,0].set_title('Memory Usage (Gateway)')
        axes[1,0].set_xlabel('Target Rate (patients/min)')
        axes[1,0].set_ylabel('Memory (MB)')
        axes[1,0].legend()
        axes[1,0].grid(True)
    
    # P4 Switch Responsiveness
    if 'p4_responsive_rate_percent' in df.columns:
        axes[1,1].plot(df['target_rate'], df['p4_responsive_rate_percent'], 'co-')
        axes[1,1].axhline(y=95, color='r', linestyle='--', label='95% threshold')
        axes[1,1].set_title('P4 Switch Responsiveness')
        axes[1,1].set_xlabel('Target Rate (patients/min)')
        axes[1,1].set_ylabel('Responsive Rate (%)')
        axes[1,1].legend()
        axes[1,1].grid(True)
    
    # System Load (if available)
    if 'gateway_load_1min' in df.columns:
        axes[1,2].plot(df['target_rate'], df['gateway_load_1min'], 'ko-', label='1 min')
        if 'gateway_load_5min' in df.columns:
            axes[1,2].plot(df['target_rate'], df['gateway_load_5min'], 'go-', label='5 min')
        axes[1,2].set_title('Gateway System Load')
        axes[1,2].set_xlabel('Target Rate (patients/min)')
        axes[1,2].set_ylabel('Load Average')
        axes[1,2].legend()
        axes[1,2].grid(True)
    
    plt.tight_layout()
    plt.savefig('performance_analysis.png', dpi=300, bbox_inches='tight')
    print("Performance plots saved as performance_analysis.png")

def plot_scalability_results():
    """Plot scalability test results"""
    files = glob.glob('scalability_results_*.csv')
    if not files:
        print("No scalability results found")
        return
    
    latest_file = max(files, key=lambda x: x.split('_')[-1].split('.')[0])
    print(f"Plotting scalability results from {latest_file}")
    df = pd.read_csv(latest_file)
    
    if df.empty:
        print("No data in scalability results file")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Success Rate
    axes[0,0].plot(df['num_patients'], df['success_rate_percent'], 'bo-')
    axes[0,0].axhline(y=95, color='r', linestyle='--', label='95% threshold')
    axes[0,0].axhline(y=80, color='orange', linestyle='--', label='80% threshold')
    axes[0,0].set_title('Patient Success Rate')
    axes[0,0].set_xlabel('Number of Patients')
    axes[0,0].set_ylabel('Success Rate (%)')
    axes[0,0].legend()
    axes[0,0].grid(True)
    
    # Alerts per Second
    axes[0,1].plot(df['num_patients'], df['alerts_per_second'], 'go-')
    axes[0,1].set_title('Alert Processing Rate')
    axes[0,1].set_xlabel('Number of Patients')
    axes[0,1].set_ylabel('Alerts per Second')
    axes[0,1].grid(True)
    
    # Active vs Total Patients
    axes[1,0].plot(df['num_patients'], df['active_patients'], 'co-', label='Active')
    axes[1,0].plot(df['num_patients'], df['num_patients'], 'k--', label='Total')
    axes[1,0].fill_between(df['num_patients'], df['active_patients'], df['num_patients'], 
                           alpha=0.3, color='red', label='Lost Patients')
    axes[1,0].set_title('Active vs Total Patients')
    axes[1,0].set_xlabel('Number of Total Patients')
    axes[1,0].set_ylabel('Number of Patients')
    axes[1,0].legend()
    axes[1,0].grid(True)
    
    # Alerts per Patient
    axes[1,1].plot(df['num_patients'], df['avg_alerts_per_patient'], 'mo-')
    axes[1,1].set_title('Average Alerts per Patient')
    axes[1,1].set_xlabel('Number of Patients')
    axes[1,1].set_ylabel('Alerts per Patient')
    axes[1,1].grid(True)
    
    plt.tight_layout()
    plt.savefig('scalability_analysis.png', dpi=300, bbox_inches='tight')
    print("Scalability plots saved as scalability_analysis.png")

def plot_timeout_results():
    """Plot timeout test results"""
    files = glob.glob('timeout_results_*.csv')
    if not files:
        print("No timeout results found")
        return
    
    latest_file = max(files, key=lambda x: x.split('_')[-1].split('.')[0])
    print(f"Plotting timeout results from {latest_file}")
    df = pd.read_csv(latest_file)
    
    if df.empty:
        print("No data in timeout results file")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Response time by missing sensors
    if 'missing_sensors' in df.columns and 'response_time_ms' in df.columns:
        missing_groups = df.groupby('missing_sensors')['response_time_ms'].agg(['mean', 'std', 'count']).reset_index()
        
        axes[0,0].errorbar(missing_groups['missing_sensors'], missing_groups['mean'], 
                           yerr=missing_groups['std'], fmt='bo-', capsize=5)
        axes[0,0].set_title('Response Time vs Missing Sensors')
        axes[0,0].set_xlabel('Number of Missing Sensors')
        axes[0,0].set_ylabel('Response Time (ms)')
        axes[0,0].grid(True)
        
        # Add timeout threshold line
        axes[0,0].axhline(y=60000, color='r', linestyle='--', label='60s timeout')
        axes[0,0].legend()
    
    # Prediction accuracy by scenario
    if 'scenario' in df.columns:
        prediction_cols = [col for col in ['sepsis_prediction', 'hf_prediction', 'news2_score'] if col in df.columns]
        if prediction_cols:
            scenario_stats = df.groupby('scenario')[prediction_cols].mean().reset_index()
            
            x = range(len(scenario_stats))
            width = 0.25
            
            for i, col in enumerate(prediction_cols):
                offset = (i - len(prediction_cols)/2) * width
                axes[0,1].bar([j + offset for j in x], scenario_stats[col], width, 
                              label=col.replace('_', ' ').title())
            
            axes[0,1].set_title('Predictions by Scenario')
            axes[0,1].set_xlabel('Scenario')
            axes[0,1].set_ylabel('Prediction Value')
            axes[0,1].set_xticks(x)
            axes[0,1].set_xticklabels(scenario_stats['scenario'], rotation=45, ha='right')
            axes[0,1].legend()
            axes[0,1].grid(True)
    
    # Response time distribution
    if 'response_time_ms' in df.columns:
        response_times = df['response_time_ms'].dropna()
        if not response_times.empty:
            # Convert to seconds for better readability
            response_times_sec = response_times / 1000
            axes[1,0].hist(response_times_sec, bins=30, alpha=0.7)
            axes[1,0].axvline(x=60, color='r', linestyle='--', label='60s timeout')
            axes[1,0].set_title('Response Time Distribution')
            axes[1,0].set_xlabel('Response Time (seconds)')
            axes[1,0].set_ylabel('Frequency')
            axes[1,0].legend()
            axes[1,0].grid(True)
    
    # Scenario summary table (as text plot)
    if 'scenario' in df.columns:
        scenario_summary = df.groupby('scenario').agg({
            'sensors_sent': 'first',
            'missing_sensors': 'first', 
            'response_time_ms': ['mean', 'count']
        }).round(2)
        
        # Flatten column names
        scenario_summary.columns = ['_'.join(col).strip() if col[1] else col[0] for col in scenario_summary.columns.values]
        
        # Create text table
        axes[1,1].axis('tight')
        axes[1,1].axis('off')
        table_data = []
        table_data.append(['Scenario', 'Sensors', 'Missing', 'Avg Time(s)', 'Count'])
        
        for idx, row in scenario_summary.iterrows():
            table_data.append([
                idx[:10] + '...' if len(idx) > 10 else idx,  # Truncate long scenario names
                str(int(row.get('sensors_sent_first', 0))),
                str(int(row.get('missing_sensors_first', 0))),
                f"{row.get('response_time_ms_mean', 0)/1000:.1f}",
                str(int(row.get('response_time_ms_count', 0)))
            ])
        
        table = axes[1,1].table(cellText=table_data[1:], colLabels=table_data[0], 
                                cellLoc='center', loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)
        axes[1,1].set_title('Scenario Summary')
    
    plt.tight_layout()
    plt.savefig('timeout_analysis.png', dpi=300, bbox_inches='tight')
    print("Timeout plots saved as timeout_analysis.png")

def plot_combined_summary():
    """Create a combined summary plot from all test results"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Latency Summary
    latency_files = glob.glob('latency_results_*.csv')
    if latency_files:
        latest_file = max(latency_files, key=lambda x: x.split('_')[-1].split('.')[0])
        df = pd.read_csv(latest_file)
        if not df.empty:
            complete = df[df['window_type'] == 'complete']['latency_ms'].dropna()
            partial = df[df['window_type'] == 'partial']['latency_ms'].dropna()
            
            summary_data = []
            labels = []
            if not complete.empty:
                summary_data.append(complete.mean())
                labels.append(f'Complete\n({len(complete)} samples)')
            if not partial.empty:
                summary_data.append(partial.mean() / 1000)  # Convert to seconds
                labels.append(f'Partial\n({len(partial)} samples)')
            
            if summary_data:
                axes[0,0].bar(labels, summary_data, color=['blue', 'red'])
                axes[0,0].set_title('Average Latency')
                axes[0,0].set_ylabel('Time (ms / s)')
    
    # Performance Summary
    perf_files = glob.glob('performance_summary_*.csv')
    if perf_files:
        latest_file = max(perf_files, key=lambda x: x.split('_')[-1].split('.')[0])
        df = pd.read_csv(latest_file)
        if not df.empty:
            max_rate = df['actual_rate'].max()
            max_cpu = df.get('avg_gateway_cpu_percent', df.get('avg_cpu_percent', pd.Series([0]))).max()
            axes[0,1].bar(['Max Throughput\n(patients/min)', 'Peak CPU\n(%)'], 
                          [max_rate, max_cpu], color=['green', 'orange'])
            axes[0,1].set_title('Performance Peak Values')
    
    # Scalability Summary
    scale_files = glob.glob('scalability_results_*.csv')
    if scale_files:
        latest_file = max(scale_files, key=lambda x: x.split('_')[-1].split('.')[0])
        df = pd.read_csv(latest_file)
        if not df.empty:
            good_results = df[df['success_rate_percent'] >= 95]
            max_patients = good_results['num_patients'].max() if not good_results.empty else 0
            max_alerts_per_sec = df['alerts_per_second'].max()
            
            axes[1,0].bar(['Max Patients\n(95% success)', 'Max Alerts/sec'], 
                          [max_patients, max_alerts_per_sec], color=['cyan', 'purple'])
            axes[1,0].set_title('Scalability Limits')
    
    # System Health Summary
    all_tests = ['Latency', 'Performance', 'Scalability', 'Timeout']
    test_status = []
    
    for test_name in all_tests:
        files = glob.glob(f'{test_name.lower()}_results_*.csv') + glob.glob(f'{test_name.lower()}_summary_*.csv')
        if files:
            test_status.append(1)  # Test completed
        else:
            test_status.append(0)  # Test not found
    
    colors = ['green' if status else 'red' for status in test_status]
    axes[1,1].bar(all_tests, test_status, color=colors)
    axes[1,1].set_title('Test Completion Status')
    axes[1,1].set_ylabel('Completed')
    axes[1,1].set_ylim(0, 1.2)
    
    # Add text annotations
    for i, (test, status) in enumerate(zip(all_tests, test_status)):
        axes[1,1].text(i, status + 0.05, '✓' if status else '✗', 
                       ha='center', fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('combined_summary.png', dpi=300, bbox_inches='tight')
    print("Combined summary saved as combined_summary.png")

if __name__ == "__main__":
    print("=== IoT Gateway Test Results Plotter ===")
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type == 'latency':
            plot_latency_results()
        elif test_type == 'performance':
            plot_performance_results()
        elif test_type == 'scalability':
            plot_scalability_results()
        elif test_type == 'timeout':
            plot_timeout_results()
        elif test_type == 'summary':
            plot_combined_summary()
        else:
            print("Usage: python plot_results.py [latency|performance|scalability|timeout|summary]")
            print("Available CSV files:")
            for pattern in ['latency_results_*.csv', 'performance_summary_*.csv', 
                          'scalability_results_*.csv', 'timeout_results_*.csv']:
                files = glob.glob(pattern)
                print(f"  {pattern}: {len(files)} files")
    else:
        # Plot all available results
        print("Plotting all available results...")
        plot_latency_results()
        plot_performance_results()
        plot_scalability_results()
        plot_timeout_results()
        plot_combined_summary()
        print("\nAll plots generated!")
        print("Generated files:")
        for filename in ['latency_analysis.png', 'performance_analysis.png', 
                        'scalability_analysis.png', 'timeout_analysis.png', 'combined_summary.png']:
            if os.path.exists(filename):
                print(f"  ✓ {filename}")
            else:
                print(f"  ✗ {filename}")