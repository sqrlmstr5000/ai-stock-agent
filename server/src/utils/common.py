from typing import Dict, List, Optional, Tuple, Annotated
# Custom merge function for concurrent dict updates that doesn't overwrite previous keys
def merge_dict_results(old_dict: Dict, new_dict: Dict) -> Dict:
    """Merges two dictionaries without overwriting existing keys."""
    result = old_dict.copy()
    for key, value in new_dict.items():
        if key not in result:
            result[key] = value
    return result

# Take latest value for scalar fields
def take_latest_value(old_value, new_value):
    """Simply returns the new value, overwriting the old one."""
    return new_value