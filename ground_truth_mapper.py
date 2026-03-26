# ground_truth_mapper.py

FDA_GRAS = {
    "water": "safe",
    "salt": "safe",
    "sugar": "moderately high",
    "flour": "safe",
    "milk": "safe",
    "egg": "safe",
    "butter": "moderately high", # saturated fat
    "cheese": "moderately high", # saturated fat
    "cream": "moderately high", # saturated fat
    "palm oil": "hazardous", # highly processed, environmental impact
    "citric acid": "safe",
    "lactic acid": "safe",
    "monosodium glutamate": "moderately high",
    "aspartame": "moderately high",
    "sucralose": "moderately high",
    "high fructose corn syrup": "hazardous",
    "titanium dioxide": "hazardous",
    "bha": "hazardous",
    "bht": "hazardous",
    "partially hydrogenated oil": "hazardous",
    "hydrogenated oil": "hazardous",
    "nitrite": "hazardous",
    "nitrate": "hazardous",
    "artificial color": "hazardous",
    "caramel color": "hazardous",
    "carrageenan": "moderately high",
    "maltodextrin": "moderately high",
    "polysorbate": "moderately high"
}

E_NUMBERS = {
    "e330": "citric acid",
    "e270": "lactic acid",
    "e621": "monosodium glutamate",
    "e951": "aspartame",
    "e955": "sucralose",
    "e171": "titanium dioxide",
    "e320": "bha",
    "e321": "bht",
    "e250": "nitrite", # Sodium nitrite
    "e251": "nitrate", # Sodium nitrate
    "e252": "nitrate", # Potassium nitrate
    "e407": "carrageenan",
    "e432": "polysorbate", # Polysorbate 20
    "e433": "polysorbate", # Polysorbate 80
    "e434": "polysorbate", # Polysorbate 40
    "e435": "polysorbate", # Polysorbate 60
    "e436": "polysorbate", # Polysorbate 65
    "e150a": "caramel color",
    "e150b": "caramel color",
    "e150c": "caramel color",
    "e150d": "caramel color",
}

def get_ground_truth(ingredient_name):
    # Check E-number synonym mapping first
    ingredient_name = ingredient_name.lower().strip()
    
    # Simple check if the whole ingredient is just an E-number
    if ingredient_name in E_NUMBERS:
        canonical_name = E_NUMBERS[ingredient_name]
    else:
        # Check if the ingredient contains an E-number (e.g., "citric acid (e330)")
        canonical_name = ingredient_name
        for e_num, name in E_NUMBERS.items():
            if e_num in ingredient_name:
                canonical_name = name
                break

    # Check for direct FDA GRAS overrides
    for key, risk_level in FDA_GRAS.items():
        if str(key) in canonical_name:
            return risk_level
            
    return None # Return None if no hardcoded rule applies
