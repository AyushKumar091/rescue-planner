import pandas as pd
import requests
import time

# Load processed dataset
df = pd.read_csv("data/processed_data.csv")

# Sample a few rows (IMPORTANT - keep small first)
df = df.dropna(subset=["latitude", "longitude"]).head(50)

# Define fixed vehicle locations (example: Chennai area)
vehicles = {
    "A1": (13.0827, 80.2707),
    "A2": (13.07, 80.25)
}

training_data = []

# OSRM function
def get_travel_time(start, end):
    url = f"http://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=false"
    response = requests.get(url).json()

    if response["routes"]:
        duration = response["routes"][0]["duration"] / 60  # minutes
        distance = response["routes"][0]["distance"] / 1000  # km
        return distance, duration
    return None, None


# Build dataset
for index, row in df.iterrows():
    accident = (row["latitude"], row["longitude"])
    severity = row.get("Accident Severity", 1)

    results = {}

    for vid, vcoords in vehicles.items():
        dist, time_taken = get_travel_time(vcoords, accident)

        if dist is None:
            continue

        results[vid] = {
            "distance": dist,
            "time": time_taken
        }

        time.sleep(1)

    if len(results) < 2:
        continue

    # Extract features
    dist_A1 = results["A1"]["distance"]
    dist_A2 = results["A2"]["distance"]
    time_A1 = results["A1"]["time"]
    time_A2 = results["A2"]["time"]

    # Label = fastest vehicle
    best_vehicle = "A1" if time_A1 < time_A2 else "A2"

    training_data.append([
        dist_A1, dist_A2,
        time_A1, time_A2,
        severity,
        best_vehicle
    ])

# Save dataset
columns = ["dist_A1", "dist_A2", "time_A1", "time_A2", "severity", "best_vehicle"]
train_df = pd.DataFrame(training_data, columns=columns)

train_df.to_csv("data/training_data.csv", index=False)

print("✅ Training dataset created!")