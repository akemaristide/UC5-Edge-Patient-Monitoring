#!/usr/bin/env python3
"""
Script to fix the merged table entries by removing the priority field
that was incorrectly added to dual-action entries.
"""

def fix_merged_tables():
    input_file = "tables/s1-commands-merged.txt"
    output_file = "tables/s1-commands-merged-fixed.txt"
    
    print("Fixing merged table entries...")
    
    with open(input_file, 'r') as f_in, open(output_file, 'w') as f_out:
        for line in f_in:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                f_out.write(line + '\n')
                continue
            
            # Process feature table entries with dual actions
            if 'extract_feature' in line and '_dual' in line:
                parts = line.split()
                if len(parts) >= 7:  # Has extra priority field
                    # Remove the last field (priority) for dual actions
                    fixed_line = ' '.join(parts[:-1])
                    f_out.write(fixed_line + '\n')
                else:
                    f_out.write(line + '\n')
            else:
                # Keep other entries as-is (leaf tables, etc.)
                f_out.write(line + '\n')
    
    print(f"Fixed table entries written to {output_file}")

if __name__ == "__main__":
    fix_merged_tables()
