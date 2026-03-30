import pandas as pd
from geopy.geocoders import Nominatim
import time

# Load dataset
df = pd.read_csv("data/accident_prediction_india.csv")

# Get unique cities
unique_cities = df["City Name"].dropna().unique()

print(f"Total unique cities: {len(unique_cities)}")

# Initialize geocoder
geolocator = Nominatim(user_agent="rescue_app")

city_coords = {}

# Convert each unique city
for city in unique_cities:
    try:
        if city == "Unknown":
            continue

        location = geolocator.geocode(city + ", India")

        if location:
            city_coords[city] = (location.latitude, location.longitude)
            print(f"{city} → {location.latitude}, {location.longitude}")
        else:
            city_coords[city] = (None, None)

        time.sleep(1)

    except:
        city_coords[city] = (None, None)


# Map back to original dataset
latitudes = []
longitudes = []

for city in df["City Name"]:
    coords = city_coords.get(city, (None, None))
    latitudes.append(coords[0])
    longitudes.append(coords[1])

df["latitude"] = latitudes
df["longitude"] = longitudes

# Save processed file
df.to_csv("data/processed_data.csv", index=False)

print("✅ Done! processed_data.csv created")