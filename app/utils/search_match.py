from fuzzywuzzy import fuzz
from typing import List, Dict, Tuple
from typing import Any
def find_matching_products(product_name: str, cart_items: List[Dict], threshold: int = 70) -> List[Tuple[Dict, int]]:
    """
    Find products in cart that match the given name using fuzzy matching
    Returns list of (item, similarity_score) tuples
    """
    matches = []
    product_name_lower = product_name.lower().strip()

    for item in cart_items:
        if not isinstance(item, dict) or not item.get('name'):
            continue

        item_name = item.get('name', '').lower().strip()

        # Exact match
        if item_name == product_name_lower:
            matches.append((item, 100))
        # Fuzzy match
        else:
            similarity = fuzz.partial_ratio(product_name_lower, item_name)
            if similarity >= threshold:
                matches.append((item, similarity))

    # Sort by similarity score (highest first)
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def safe_type_conversion(value: Any, target_type: type, default: Any = 0):
    """Safely convert value to target type with fallback"""
    try:
        if value is None:
            return default
        return target_type(value)
    except (ValueError, TypeError):
        return default