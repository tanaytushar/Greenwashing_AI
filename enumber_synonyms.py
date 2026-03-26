from ground_truth_mapper import E_NUMBERS
import re

def normalize_enumbers(ingredient_string: str) -> str:
    """Replace E-numbers with their common names."""
    ing = ingredient_string.lower()
    for enum, name in E_NUMBERS.items():
        # Match E-number with basic word boundaries
        pattern = r'\b' + re.escape(enum) + r'\b'
        ing = re.sub(pattern, name, ing)
    return ing
