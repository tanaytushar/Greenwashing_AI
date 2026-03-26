import pandas as pd
import re

df = pd.read_csv("top_5000ingredients.csv")

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'\d+%', '', text)  # remove percentages
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # remove symbols
    text = text.strip()
    return text

df["ingredient"] = df["ingredient"].apply(clean_text)

df = df.drop_duplicates(subset=["ingredient"])

df.to_csv("cleaned_ingredients.csv", index=False)

print("Cleaned file saved successfully!")