import re

content = open('api.py', encoding='utf-8').read()

# Find and replace entire CONTRADICTIONS block
idx_start = content.find('CONTRADICTIONS = {')
idx_end   = content.find('\n}\n', idx_start) + 3

if idx_start == -1:
    print("ERROR: Could not find CONTRADICTIONS in api.py")
    exit(1)

old_block = content[idx_start:idx_end]
print("Found block, replacing...")

new_block = '''CONTRADICTIONS = {
    "natural":      ["artificial", "hydrogenated", "titanium dioxide",
                     "bha", "bht", "polysorbate", "carrageenan",
                     "vanillin", "palm oil", "maltodextrin"],
    "organic":      ["artificial", "hydrogenated", "bha",
                     "titanium dioxide", "maltodextrin", "palm oil", "vanillin"],
    "healthy":      ["high fructose corn syrup", "hydrogenated",
                     "nitrite", "nitrate", "bha", "artificial color",
                     "sugar", "palm oil", "corn syrup",
                     "dextrose", "glucose syrup", "sucrose"],
    "wholesome":    ["sugar", "palm oil", "hydrogenated",
                     "artificial", "corn syrup", "vanillin", "maltodextrin"],
    "pure":         ["artificial", "hydrogenated", "polysorbate",
                     "carrageenan", "bha", "vanillin", "maltodextrin"],
    "clean":        ["artificial", "hydrogenated", "bha",
                     "titanium dioxide", "carrageenan",
                     "palm oil", "vanillin", "maltodextrin"],
    "simple":       ["polysorbate", "carrageenan", "phosphate",
                     "disodium", "emulsifier", "vanillin", "maltodextrin"],
    "preservative-free": ["benzoate", "sorbate", "nitrite",
                          "bha", "bht", "sulphite", "sulfite"],
    "no artificial":  ["artificial color", "artificial flavor", "vanillin"],
    "no added sugar": ["sugar", "corn syrup", "high fructose",
                       "dextrose", "maltose", "glucose syrup", "sucrose"],
    "sugar-free":     ["sugar", "corn syrup", "high fructose",
                       "dextrose", "maltose"],
    "nutritious":     ["high fructose corn syrup", "maltodextrin",
                       "artificial flavor", "sugar", "palm oil"],
}
'''

content = content[:idx_start] + new_block + content[idx_end:]

# Also fix the contradiction-checking function to use plain 'in' instead of regex
# since we switched from regex patterns to plain strings
old_func = '''    contradictions = []
    for claim in claims:
        term = claim["term"]
        if term not in CONTRADICTIONS:
            continue
        for pattern in CONTRADICTIONS[term]:
            if re.search(pattern, ingredients_norm):
                contradictions.append({
                    "claim":      term,
                    "strength":   claim["strength"],
                    "ingredient": pattern.replace(r"\\b", "").strip(),
                })'''

new_func = '''    contradictions = []
    seen = set()
    for claim in claims:
        term = claim["term"]
        if term not in CONTRADICTIONS:
            continue
        for keyword in CONTRADICTIONS[term]:
            if keyword in ingredients_norm:
                key = (term, keyword)
                if key not in seen:
                    seen.add(key)
                    contradictions.append({
                        "claim":      term,
                        "strength":   claim["strength"],
                        "ingredient": keyword,
                    })'''

if old_func in content:
    content = content.replace(old_func, new_func)
    print("Also fixed contradiction-checking function.")
else:
    print("WARNING: Could not find contradiction function - may already be updated.")

open('api.py', 'w', encoding='utf-8').write(content)
print("SUCCESS - api.py patched!")