import os
import json
import pytest
from typing import Dict

def load_subroutines_config(filepath: str) -> Dict:
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load subroutines config: {e}")
        return {}

# Helper function to check the structure of each subroutine
def validate_subroutine_structure(subroutine: Dict):
    # Validate that 'SUB' exists and is a string
    assert "SUB" in subroutine, f"Missing 'SUB' key in subroutine {subroutine}"
    assert isinstance(subroutine["SUB"], str), f"'SUB' should be a string in subroutine {subroutine}"
    
    # Validate that 'VALUES' exists and is a dictionary
    assert "VALUES" in subroutine, f"Missing 'VALUES' key in subroutine {subroutine}"
    assert isinstance(subroutine["VALUES"], dict), f"'VALUES' should be a dictionary in subroutine {subroutine}"

    # Validate that 'IMPORT' exists in 'VALUES' and is a list of lists
    assert "IMPORT" in subroutine["VALUES"], f"Missing 'IMPORT' key in 'VALUES' of subroutine {subroutine}"
    assert isinstance(subroutine["VALUES"]["IMPORT"], list), f"'IMPORT' should be a list in subroutine {subroutine}"
    
    # Ensure that each item in 'IMPORT' is a list and has at least 2 elements (table_name and columns)
    for entry in subroutine["VALUES"]["IMPORT"]:
        assert isinstance(entry, list), f"Each entry in 'IMPORT' should be a list in subroutine {subroutine}"
        assert len(entry) >= 2, f"Each entry in 'IMPORT' should have at least 2 elements (table_name and columns) in subroutine {subroutine}"

# Test to load the configuration and validate the structure
def test_subroutine_config_structure():
    # Dynamically resolve the file path
    file_path = os.path.join(os.path.dirname(__file__), "subroutines_config.json")
    
    subroutine_config = load_subroutines_config(file_path)
    
    # Check if the configuration is empty or failed to load
    assert subroutine_config, "Subroutine config is empty or failed to load"

    # Expected subroutine keys
    expected_subroutines = [
        "bpm", "checkpoints", "osmon_sum", "queues_summary", "onstat-u", "replication",
        "cpu_by_app", "openbet_cpu_by_app", "db_check_info", "total_locks", "onstat-g_ntu",
        "buffer_k", "buffer_fast", "lru_overall", "vpcache", "onstat-g_prc", "lru_k",
        "onstat-l", "partition_summary", "onstat-g_seg"
    ]

    # Validate that all expected subroutines are present in the config
    for subroutine_key in expected_subroutines:
        assert subroutine_key in subroutine_config, f"Missing subroutine: {subroutine_key}"
        subroutine = subroutine_config[subroutine_key]
        validate_subroutine_structure(subroutine)
    
    print("All subroutines have the correct structure.")
