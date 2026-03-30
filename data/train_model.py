import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib

# 📥 load your dataset
df = pd.read_csv("data.csv")

# 🎯 features + target
X = df[["dist_A1","dist_A2","time_A1","time_A2","severity"]]
y = df["best_vehicle"]

# 🔁 convert severity to numbers
X["severity"] = X["severity"].map({
    "Minor":0,
    "Serious":1,
    "Fatal":2
})

# split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# model
model = RandomForestClassifier()
model.fit(X_train, y_train)

# save
joblib.dump(model, "model.pkl")

print("Model trained & saved")