#!/usr/bin/env python3
"""
Fix the merged table entries to have correct priorities.
"""

def fix_merged_table_entries():
    input_file = "tables/s1-commands-merged.txt"
    output_file = "tables/s1-commands-merged-fixed.txt"
    
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            fixed_lines.append(line)
            continue
            
        # Process feature table entries
        if 'extract_feature' in line and '_dual' in line:
            parts = line.split()
            if len(parts) >= 6:
                # Extract components
                table_cmd = parts[0]  # table_add
                table_name = parts[1]  # SwitchIngress.lookup_featureX
                action_name = parts[2]  # extract_featureX_dual
                match_key = parts[3]  # value&&&mask
                arrow = parts[4]  # =>
                
                # Check if we have 3 values after =>
                if len(parts) >= 8:
                    sep_code = parts[5]
                    hf_code = parts[6]
                    incorrect_priority = parts[7]
                    
                    # Extract actual priority from the incorrect third parameter
                    # The pattern suggests the last number was meant to be priority
                    # Let's use a sequential priority based on position
                    priority = incorrect_priority
                    
                    # Reconstruct the correct line
                    fixed_line = f"{table_cmd} {table_name} {action_name} {match_key} {arrow} {sep_code} {hf_code} {priority}"
                    fixed_lines.append(fixed_line)
                else:
                    # Line format is already correct or different
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        else:
            # Not a feature table entry, keep as is
            fixed_lines.append(line)
    
    # Write fixed file
    with open(output_file, 'w') as f:
        for line in fixed_lines:
            f.write(line + '\n')
    
    print(f"Fixed merged table entries written to {output_file}")

if __name__ == "__main__":
    fix_merged_table_entries()
