from flask import Flask, render_template, request, jsonify
import threading
import time
import requests

app = Flask(__name__)

# ---------------- DATA ----------------

vehicle_positions = {}
vehicle_paths = {}

emergencies = []
emergency_history = []

emergency_id_counter = 0

vehicles = [
    {"id": "A1", "type": "ambulance", "busy": False, "coords": [13.08, 80.27]},
    {"id": "A2", "type": "ambulance", "busy": False, "coords": [13.07, 80.25]},
    {"id": "A3", "type": "ambulance", "busy": False, "coords": [13.06, 80.26]},
    {"id": "A4", "type": "ambulance", "busy": False, "coords": [13.09, 80.28]},
    {"id": "A5", "type": "ambulance", "busy": False, "coords": [13.05, 80.24]},
    {"id": "F1", "type": "fire", "busy": False, "coords": [13.085, 80.29]},
    {"id": "F2", "type": "fire", "busy": False, "coords": [13.065, 80.23]},
    {"id": "F3", "type": "fire", "busy": False, "coords": [13.075, 80.27]},
    {"id": "F4", "type": "fire", "busy": False, "coords": [13.095, 80.25]},
    {"id": "F5", "type": "fire", "busy": False, "coords": [13.055, 80.28]},
]

# ---------------- ROUTES ----------------

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/control")
def control():
    return render_template("index.html")

@app.route("/user")
def user():
    return render_template("user.html")

# ---------------- API ----------------

@app.route("/add_emergency", methods=["POST"])
def add_emergency():
    global emergency_id_counter

    data = request.json
    data["assigned"] = None
    data["id"] = emergency_id_counter
    data["created_at"] = time.time()
    data["completed"] = False
    data["response_time"] = None

    emergency_id_counter += 1

    emergencies.append(data)
    emergency_history.append(data.copy())

    threading.Thread(target=assign_logic, args=(data["id"],)).start()

    return jsonify({"id": data["id"]})


@app.route("/get_emergencies")
def get_emergencies():
    return jsonify(emergencies)


@app.route("/get_history")
def get_history():
    return jsonify(emergency_history)


@app.route("/get_vehicles")
def get_vehicles():
    return jsonify(vehicles)


@app.route("/get_vehicle_position/<vid>")
def get_vehicle_position(vid):
    return jsonify(vehicle_positions.get(vid, {}))


@app.route("/get_vehicle_path/<vid>")
def get_vehicle_path(vid):
    return jsonify(vehicle_paths.get(vid, []))


# ---------------- ASSIGNMENT ----------------

def assign_logic(eid):

    emergency = next((e for e in emergencies if e["id"] == eid), None)
    if not emergency:
        return

    best_vehicle = None
    best_time = float("inf")
    best_path = None

    for v in vehicles:
        if v["busy"] or v["type"] != emergency["type"]:
            continue

        start = v["coords"]
        end = [emergency["lat"], emergency["lng"]]

        url = f"http://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"

        try:
            res = requests.get(url).json()
            route = res["routes"][0]

            if route["duration"] < best_time:
                best_time = route["duration"]
                best_vehicle = v
                best_path = route["geometry"]["coordinates"]

        except:
            continue

    if not best_vehicle:
        return

    vid = best_vehicle["id"]

    emergency["assigned"] = vid

    for h in emergency_history:
        if h["id"] == eid:
            h["assigned"] = vid
            break

    best_vehicle["busy"] = True

    path = [[c[1], c[0]] for c in best_path]
    vehicle_paths[vid] = path

    threading.Thread(target=simulate_movement, args=(vid,)).start()


# ---------------- MOVEMENT ----------------

def simulate_movement(vehicle_id):

    path = vehicle_paths.get(vehicle_id, [])

    for point in path:
        vehicle_positions[vehicle_id] = point
        time.sleep(0.03)

    for e in emergencies:
        if e.get("assigned") == vehicle_id:

            e["completed"] = True
            e["response_time"] = round(time.time() - e["created_at"], 2)

            for h in emergency_history:
                if h["id"] == e["id"]:
                    h["completed"] = True
                    h["response_time"] = e["response_time"]
                    break

    for v in vehicles:
        if v["id"] == vehicle_id:
            v["coords"] = path[-1]
            v["busy"] = False


# ---------------- RESET ----------------

@app.route("/user_reset", methods=["POST"])
def user_reset():
    global emergencies, vehicle_paths

    emergencies = []
    vehicle_paths = {}

    for v in vehicles:
        v["busy"] = False

    return jsonify({"status": "user reset"})


@app.route("/clear_all", methods=["POST"])
def clear_all():
    global emergencies, vehicle_positions, vehicle_paths, emergency_history

    emergencies = []
    vehicle_positions = {}
    vehicle_paths = {}
    emergency_history = []

    for v in vehicles:
        v["busy"] = False

    return jsonify({"status": "cleared"})


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)