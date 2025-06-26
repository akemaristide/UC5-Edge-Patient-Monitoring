#!/usr/bin/env python3
"""
Script to merge sepsis and heart failure table entries for the unified P4 program.
"""

def parse_feature_entry(line):
    """Parse a feature table entry line and extract components."""
    # Example: table_add SwitchIngress.lookup_feature0 extract_feature0 400&&&1008 => 18 0
    parts = line.strip().split()
    if len(parts) < 6 or not line.startswith('table_add SwitchIngress.lookup_feature'):
        return None
    
    table_name = parts[1]  # SwitchIngress.lookup_feature0
    action_name = parts[2]  # extract_feature0
    match_key = parts[3]   # 400&&&1008
    arrow = parts[4]       # =>
    code_val = parts[5]    # 18
    priority = parts[6]    # 0
    
    # Extract feature number
    feature_num = table_name.split('feature')[1]
    
    return {
        'feature_num': feature_num,
        'table_name': table_name,
        'action_name': action_name,
        'match_key': match_key,
        'code_val': code_val,
        'priority': priority,
        'original_line': line.strip()
    }

def parse_leaf_entry(line):
    """Parse a leaf table entry line."""
    # Example: table_add SwitchIngress.lookup_leaf_id0 read_prob0 0 0 0 0 0 0 0 0 0 0 => 0 8
    if not line.startswith('table_add SwitchIngress.lookup_leaf_id'):
        return None
    
    parts = line.strip().split()
    table_name = parts[1]
    action_name = parts[2]
    
    # Find the '=>' separator
    arrow_idx = parts.index('=>')
    match_keys = parts[3:arrow_idx]
    result_parts = parts[arrow_idx+1:]
    
    return {
        'table_name': table_name,
        'action_name': action_name,
        'match_keys': match_keys,
        'result_parts': result_parts,
        'original_line': line.strip()
    }

def read_table_file(filename):
    """Read and categorize table entries from a file."""
    feature_entries = {}  # feature_num -> list of entries
    leaf_entries = []
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if 'lookup_feature' in line:
                entry = parse_feature_entry(line)
                if entry:
                    feature_num = entry['feature_num']
                    if feature_num not in feature_entries:
                        feature_entries[feature_num] = []
                    feature_entries[feature_num].append(entry)
            elif 'lookup_leaf_id' in line:
                entry = parse_leaf_entry(line)
                if entry:
                    leaf_entries.append(entry)
    
    return feature_entries, leaf_entries

def merge_feature_entries(sep_features, hf_features):
    """Merge feature entries from both models."""
    merged_entries = []
    
    # Get all feature numbers
    all_features = set(sep_features.keys()) | set(hf_features.keys())
    
    for feature_num in sorted(all_features, key=int):
        print(f"Processing feature {feature_num}...")
        
        sep_entries = sep_features.get(feature_num, [])
        hf_entries = hf_features.get(feature_num, [])
        
        # Create a map of match_key -> (sep_code, hf_code)
        match_key_codes = {}
        
        # Process sepsis entries
        for entry in sep_entries:
            match_key = entry['match_key']
            sep_code = entry['code_val']
            if match_key not in match_key_codes:
                match_key_codes[match_key] = [None, None]
            match_key_codes[match_key][0] = sep_code
        
        # Process heart failure entries
        for entry in hf_entries:
            match_key = entry['match_key']
            hf_code = entry['code_val']
            if match_key not in match_key_codes:
                match_key_codes[match_key] = [None, None]
            match_key_codes[match_key][1] = hf_code
        
        # Generate merged entries
        priority = 0
        for match_key in sorted(match_key_codes.keys()):
            sep_code, hf_code = match_key_codes[match_key]
            
            # Default to 0 if code is missing for one model
            if sep_code is None:
                sep_code = "0"
            if hf_code is None:
                hf_code = "0"
            
            # Create merged entry with dual action
            merged_line = f"table_add SwitchIngress.lookup_feature{feature_num} extract_feature{feature_num}_dual {match_key} => {sep_code} {hf_code} {priority}"
            merged_entries.append(merged_line)
            priority += 1
        
        # Add empty line after each feature table
        merged_entries.append("")
    
    return merged_entries

def process_leaf_entries(leaf_entries, suffix):
    """Process leaf entries with given suffix."""
    processed = []
    
    for entry in leaf_entries:
        # Update table and action names with suffix
        table_name = entry['table_name'] + suffix
        action_name = entry['action_name'] + suffix
        
        # Reconstruct the line
        match_keys_str = ' '.join(entry['match_keys'])
        result_str = ' '.join(entry['result_parts'])
        
        new_line = f"table_add {table_name} {action_name} {match_keys_str} => {result_str}"
        processed.append(new_line)
    
    return processed

def main():
    # File paths
    sep_file = "tables/s1-commands-sep.txt"
    hf_file = "HF_2trees_5depth/s1-commands-hf.txt"
    output_file = "tables/s1-commands-merged.txt"
    
    print("Reading sepsis table entries...")
    sep_features, sep_leaves = read_table_file(sep_file)
    print(f"Found {len(sep_features)} feature tables and {len(sep_leaves)} leaf entries for sepsis")
    
    print("Reading heart failure table entries...")
    hf_features, hf_leaves = read_table_file(hf_file)
    print(f"Found {len(hf_features)} feature tables and {len(hf_leaves)} leaf entries for heart failure")
    
    print("Merging feature entries...")
    merged_features = merge_feature_entries(sep_features, hf_features)
    
    print("Processing leaf entries...")
    sep_leaf_entries = process_leaf_entries(sep_leaves, "_sep")
    hf_leaf_entries = process_leaf_entries(hf_leaves, "_hf")
    
    print(f"Writing merged table entries to {output_file}...")
    with open(output_file, 'w') as f:
        # Write header comment
        f.write("# Merged table entries for unified sepsis and heart failure detection\n")
        f.write("# Generated by merge_table_entries.py\n\n")
        
        # Write merged feature tables
        f.write("# Feature extraction tables (unified with dual actions)\n")
        for line in merged_features:
            f.write(line + '\n')
        
        f.write("\n# Sepsis model leaf/decision tables\n")
        for line in sep_leaf_entries:
            f.write(line + '\n')
        
        f.write("\n# Heart failure model leaf/decision tables\n")
        for line in hf_leaf_entries:
            f.write(line + '\n')
    
    print(f"Merge complete! Generated {len(merged_features)} feature entries, {len(sep_leaf_entries)} sepsis leaf entries, and {len(hf_leaf_entries)} heart failure leaf entries.")

if __name__ == "__main__":
    main()
