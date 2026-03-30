import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# Load training data
df = pd.read_csv("data/training_data.csv")

# 🔥 FIX: convert severity to numeric
severity_map = {
    "Minor": 1,
    "Moderate": 2,
    "Major": 3,
    "Severe": 4
}

df["severity"] = df["severity"].map(severity_map)

# Drop rows where mapping failed
df = df.dropna()

# Features
X = df[["dist_A1", "dist_A2", "time_A1", "time_A2", "severity"]]

# Target
y = df["best_vehicle"]

# Train model
model = RandomForestClassifier()
model.fit(X, y)

# Save model
joblib.dump(model, "model.pkl")

print("✅ Model trained and saved!")