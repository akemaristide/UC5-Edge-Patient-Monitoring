#!/usr/bin/env python3
"""
Quick fix for merged table entries - ensure proper priority values.
"""

def quick_fix_priorities():
    input_file = "tables/s1-commands-merged.txt"
    output_file = "tables/s1-commands-merged-corrected.txt"
    
    print(f"Reading from {input_file}")
    
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    priority_counter = 0
    
    for line in lines:
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            fixed_lines.append(line)
            continue
            
        # Process feature table entries with dual actions
        if 'extract_feature' in line and '_dual' in line and '=>' in line:
            parts = line.split(' => ')
            if len(parts) == 2:
                left_part = parts[0]  # table_add ... match_key
                right_part = parts[1].strip()  # parameters
                
                # Split the right part into parameters
                params = right_part.split()
                
                if len(params) >= 3:
                    # Assume format: sep_code hf_code incorrect_priority
                    sep_code = params[0]
                    hf_code = params[1]
                    # Use sequential priority instead of the third parameter
                    
                    # Reconstruct with proper priority
                    fixed_line = f"{left_part} => {sep_code} {hf_code} {priority_counter}"
                    fixed_lines.append(fixed_line)
                    priority_counter += 1
                else:
                    # Keep original if format is different
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        else:
            # Not a feature table entry, keep as is
            fixed_lines.append(line)
            # Reset priority counter for each new table section
            if line.strip() == "":
                priority_counter = 0
    
    # Write fixed file
    with open(output_file, 'w') as f:
        for line in fixed_lines:
            f.write(line + '\n')
    
    print(f"Fixed merged table entries written to {output_file}")
    print(f"Fixed {priority_counter} entries")

if __name__ == "__main__":
    quick_fix_priorities()
