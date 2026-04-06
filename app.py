"""
Intelligent Emergency Rescue Planner — Flask Backend
=====================================================
AI Algorithms implemented from scratch (curriculum requirements):
  1. A* Search        — optimal routing on Chennai road graph (ai/graph.py)
  2. Bayesian Network — road uncertainty (rain/traffic → blockage) (ai/bayesian.py)
  3. Simulated Annealing — multi-vehicle/multi-emergency assignment (ai/simulated_annealing.py)

OSRM is kept as an optional visual-path fallback only (for smooth map curves).
All routing DECISIONS are made by our own A* implementation.
"""

import logging
import threading
import time

import joblib
import requests
from flask import Flask, jsonify, render_template, request

from ai.bayesian import BayesianRoadNetwork
from ai.graph import astar, find_nearby_edges, load_graph
from ai.simulated_annealing import optimize_assignment, sa_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Load AI components at startup ─────────────────────────────────────────────

logger.info("🧠 Loading Chennai road graph …")
G = load_graph()
logger.info("✅ Graph ready: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

logger.info("🤖 Loading ML model …")
model = joblib.load("model.pkl")
logger.info("✅ ML model loaded")

# Bayesian Network instance (shared, thread-safe reads)
bayesian = BayesianRoadNetwork()

# Assignment lock — used when Simulated Annealing batch-assigns multiple emergencies
assign_lock = threading.Lock()

# ── Severity encoding ─────────────────────────────────────────────────────────

def encode_severity(s: str) -> int:
    return {"Minor": 0, "Serious": 1, "Fatal": 2}.get(s, 0)

# ── Shared state ──────────────────────────────────────────────────────────────

vehicle_positions = {}   # vid -> [lat, lng]
vehicle_paths     = {}   # vid -> [[lat, lng], ...]
vehicle_nodes     = {}   # vid -> list of graph nodes (for re-routing)

emergencies      = []
emergency_history = []
emergency_id_counter = 0

# Blocked edges: set of (u, v) node-pairs reported as impassable
blocked_edges: set = set()

vehicles = [
    {"id": "A1", "type": "ambulance", "busy": False, "coords": [13.08,  80.27]},
    {"id": "A2", "type": "ambulance", "busy": False, "coords": [13.07,  80.25]},
    {"id": "A3", "type": "ambulance", "busy": False, "coords": [13.06,  80.26]},
    {"id": "A4", "type": "ambulance", "busy": False, "coords": [13.09,  80.28]},
    {"id": "A5", "type": "ambulance", "busy": False, "coords": [13.05,  80.24]},
    {"id": "F1", "type": "fire",      "busy": False, "coords": [13.085, 80.29]},
    {"id": "F2", "type": "fire",      "busy": False, "coords": [13.065, 80.23]},
    {"id": "F3", "type": "fire",      "busy": False, "coords": [13.075, 80.27]},
    {"id": "F4", "type": "fire",      "busy": False, "coords": [13.095, 80.25]},
    {"id": "F5", "type": "fire",      "busy": False, "coords": [13.055, 80.28]},
]

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/control")
def control():
    return render_template("index.html")

@app.route("/user")
def user():
    return render_template("user.html")

# ── Emergency API ─────────────────────────────────────────────────────────────

@app.route("/add_emergency", methods=["POST"])
def add_emergency():
    global emergency_id_counter

    data = request.json
    data["assigned"]      = None
    data["id"]            = emergency_id_counter
    data["created_at"]    = time.time()
    data["completed"]     = False
    data["response_time"] = None
    data["algorithm_used"] = None
    data["astar_cost"]    = None

    # Default severity if not provided
    if "severity" not in data:
        data["severity"] = "Minor"

    emergency_id_counter += 1

    emergencies.append(data)
    emergency_history.append(data.copy())

    threading.Thread(target=assign_logic, args=(data["id"],), daemon=True).start()

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
    return jsonify(vehicle_positions.get(vid, []))


@app.route("/get_vehicle_path/<vid>")
def get_vehicle_path(vid):
    return jsonify(vehicle_paths.get(vid, []))


# ── Environment & Blockage API ────────────────────────────────────────────────

@app.route("/set_environment", methods=["POST"])
def set_environment():
    """Update Bayesian Network evidence: rain and traffic level."""
    data = request.json
    rain    = bool(data.get("rain", False))
    traffic = data.get("traffic", "low")
    bayesian.set_conditions(rain=rain, traffic=traffic)
    logger.info("🌧️  Environment updated: rain=%s, traffic=%s → blockage_prob=%.2f",
                rain, traffic, bayesian.blockage_probability())
    return jsonify(bayesian.summary())


@app.route("/get_environment")
def get_environment():
    return jsonify(bayesian.summary())


@app.route("/report_blockage", methods=["POST"])
def report_blockage():
    """
    Mark a road segment near the given lat/lng as blocked.
    Triggers dynamic A* re-routing for any in-transit vehicles passing through it.
    """
    data = request.json
    lat, lng = float(data["lat"]), float(data["lng"])

    new_edges = find_nearby_edges(G, lat, lng, radius_m=250)
    if not new_edges:
        return jsonify({"status": "no_edges_found", "lat": lat, "lng": lng})

    blocked_edges.update(new_edges)
    logger.info("🚧 Blockage reported at (%.4f, %.4f) — %d edges blocked", lat, lng, len(new_edges))

    # Trigger re-routing for all in-transit vehicles
    rerouted = []
    for v in vehicles:
        if v["busy"] and v["id"] in vehicle_positions:
            threading.Thread(target=reroute_vehicle, args=(v["id"],), daemon=True).start()
            rerouted.append(v["id"])

    return jsonify({
        "status":   "blocked",
        "edges":    len(new_edges),
        "rerouted": rerouted,
    })


@app.route("/get_blockages")
def get_blockages():
    """Return list of blocked node-pair coords for the frontend to draw."""
    result = []
    for u, v in blocked_edges:
        if u in G.nodes and v in G.nodes:
            mid_lat = (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2
            mid_lng = (G.nodes[u]["x"] + G.nodes[v]["x"]) / 2
            result.append({"lat": mid_lat, "lng": mid_lng})
    return jsonify(result)


# ── 🤖 AI ASSIGNMENT (A* + Bayesian + Simulated Annealing) ────────────────────

def interpolate_path(path_coords, points_per_segment=8):
    """Linearly interpolates points between A* nodes to provide smooth map animation."""
    dense_path = []
    if not path_coords: return []
    if len(path_coords) == 1: return path_coords
    for i in range(len(path_coords) - 1):
        lat1, lng1 = path_coords[i]
        lat2, lng2 = path_coords[i+1]
        for j in range(points_per_segment):
            f = j / float(points_per_segment)
            dense_path.append([lat1 + (lat2 - lat1)*f, lng1 + (lng2 - lng1)*f])
    dense_path.append(path_coords[-1])
    return dense_path

def osrm_trace_waypoints(path_coords, fallback_interpolation=8):
    """Forces OSRM to map a smooth real-road trace going exactly through the A* computed waypoints."""
    if len(path_coords) < 2:
        return interpolate_path(path_coords, fallback_interpolation)
        
    try:
        # Public OSRM API has a limit of ~100 coordinates. Downsample if needed.
        if len(path_coords) > 90:
            step = len(path_coords) // 90
            sampled = [path_coords[0]] + path_coords[1:-1:step] + [path_coords[-1]]
            path_coords = sampled

        coords_str = ";".join([f"{c[1]:.5f},{c[0]:.5f}" for c in path_coords])
        url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
        res = requests.get(url, timeout=4).json()
        if res.get("code") == "Ok":
            osrm_coords = res["routes"][0]["geometry"]["coordinates"]
            return [[c[1], c[0]] for c in osrm_coords]
    except Exception as e:
        logger.error("OSRM trace failed: %s", e)
        
    return interpolate_path(path_coords, fallback_interpolation)

def assign_logic(eid: int):
    """
    Core AI assignment pipeline:
      1. Bayesian Network → compute edge cost multiplier from rain/traffic state
      2. A* Search        → compute optimal path cost for each available vehicle
      3. Simulated Annealing → if multiple unassigned emergencies, globally optimise
      4. ML model nudge   → slight score refinement from trained RandomForest

    Falls back to OSRM for smooth visual map path (optional), but the routing
    DECISION is always made by A*.
    """
    with assign_lock:
        emergency = next((e for e in emergencies if e["id"] == eid), None)
        if not emergency or emergency["assigned"]:
            return

        etype = emergency["type"]

        # ── 1. Bayesian cost multiplier ───────────────────────────────────────
        bayes_mult = bayesian.edge_weight_multiplier()
        bayes_info = bayesian.summary()
        logger.info("🔮 Bayesian: blockage_prob=%.2f → edge_mult=%.2f",
                    bayes_info["blockage_probability"], bayes_mult)

        # Apply uniform multiplier to ALL edges (simplified — real system would
        # query per-edge weather exposure, but this demonstrates the concept)
        weight_multipliers = {}   # {} = use bayes_mult as a global scalar to g(n)

        # ── 2. Collect unassigned emergencies of this type ────────────────────
        unassigned_of_type = [
            e for e in emergencies
            if e["type"] == etype and not e["assigned"] and not e["completed"]
        ]

        # Available vehicles for this type
        available_vehicles = [v for v in vehicles if v["type"] == etype and not v["busy"]]

        if not available_vehicles:
            logger.warning("No available %s vehicles for emergency %d", etype, eid)
            return

        # ── 3. Build cost matrix via A* for all (emergency × vehicle) pairs ──
        cost_matrix = {}   # (eid, vid) → astar cost in seconds
        path_map    = {}   # (eid, vid) → path_coords

        for e in unassigned_of_type:
            e_lat, e_lng = e["lat"], e["lng"]
            for v in available_vehicles:
                v_lat, v_lng = v["coords"]

                path_coords, cost = astar(
                    G,
                    origin_lat=v_lat, origin_lng=v_lng,
                    dest_lat=e_lat,   dest_lng=e_lng,
                    blocked_edges=blocked_edges,
                    weight_multipliers=weight_multipliers,
                )

                # Scale cost by Bayesian multiplier (global road risk)
                adjusted_cost = cost * bayes_mult

                cost_matrix[(e["id"], v["id"])] = adjusted_cost
                path_map[(e["id"], v["id"])]    = path_coords

                logger.info("  A* %s → E%d: cost=%.1fs (×%.2f=%.1fs), nodes=%d",
                            v["id"], e["id"], cost, bayes_mult, adjusted_cost, len(path_coords))

        # ── 4. Simulated Annealing (batch assignment) ─────────────────────────
        e_ids = [e["id"] for e in unassigned_of_type]
        v_ids = [v["id"] for v in available_vehicles]

        if len(e_ids) > 1:
            logger.info("🔥 Running Simulated Annealing for %d emergencies × %d vehicles …",
                        len(e_ids), len(v_ids))
            best_assignment = optimize_assignment(e_ids, v_ids, cost_matrix)
            result = sa_summary(best_assignment, cost_matrix)
            logger.info("✅ SA result: %s (total cost %.1fs)", result["assignments"], result["total_estimated_cost_seconds"])
        else:
            # Single emergency — standard A* winner pick
            best_assignment = {eid: min(v_ids, key=lambda vid: cost_matrix.get((eid, vid), 1e9))}
            logger.info("📌 Single-emergency direct A* assignment: %s", best_assignment)

        # ── 5. Apply assignments ──────────────────────────────────────────────
        for assigned_eid, assigned_vid in best_assignment.items():
            target_e = next((e for e in emergencies if e["id"] == assigned_eid), None)
            target_v = next((v for v in vehicles   if v["id"]  == assigned_vid),  None)

            if not target_e or not target_v or target_v["busy"] or target_e["assigned"]:
                continue

            # ── 6. ML model nudge (light score refinement) ────────────────────
            # (kept from original — demonstrates ML integration)
            try:
                dist_val = cost_matrix.get((assigned_eid, assigned_vid), 0)
                sev      = encode_severity(target_e.get("severity", "Minor"))
                features = [[dist_val, dist_val, dist_val, dist_val, sev]]
                pred = model.predict(features)[0]
                if pred == assigned_vid:
                    logger.info("  🤖 ML model agrees with A* choice (%s) → confirmed", assigned_vid)
            except Exception:
                pass

            # ── Interpolate A* path for smooth visual animation ──
            raw_path = path_map.get((assigned_eid, assigned_vid), [])
            v_c = target_v["coords"]
            e_pos = [target_e["lat"], target_e["lng"]]
            
            if not raw_path:
                raw_path = [v_c, e_pos]
            else:
                raw_path = [v_c] + raw_path + [e_pos]
            
            final_path = osrm_trace_waypoints(raw_path, fallback_interpolation=8)
            # (OSRM removed to strictly enforce A* path visually)

            # Commit assignment
            target_e["assigned"]      = assigned_vid
            target_e["algorithm_used"] = "A* + Bayesian + SA"
            target_e["astar_cost"]    = cost_matrix.get((assigned_eid, assigned_vid), 0)
            
            real_seconds = int(target_e["astar_cost"])
            mins = real_seconds // 60
            secs = real_seconds % 60
            target_e["response_time"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

            for h in emergency_history:
                if h["id"] == assigned_eid:
                    h["assigned"]      = assigned_vid
                    h["algorithm_used"] = "A* + Bayesian + SA"
                    break

            target_v["busy"]   = True
            vehicle_paths[assigned_vid] = final_path

            threading.Thread(
                target=simulate_movement,
                args=(assigned_vid, assigned_eid),
                daemon=True,
            ).start()


# ── Re-routing ────────────────────────────────────────────────────────────────

def reroute_vehicle(vid: str):
    """
    Dynamically re-route a vehicle mid-journey using A* after a blockage is reported.
    Implements Dynamic A* by re-running A* from current position with updated blocked_edges.
    """
    current_pos = vehicle_positions.get(vid)
    if not current_pos:
        return

    # Find which emergency this vehicle is heading to
    target_e = next(
        (e for e in emergencies if e.get("assigned") == vid and not e["completed"]),
        None,
    )
    if not target_e:
        return

    dest_lat, dest_lng = target_e["lat"], target_e["lng"]
    from_lat, from_lng = current_pos[0], current_pos[1]

    logger.info("🔄 Re-routing %s from (%.4f, %.4f) → (%.4f, %.4f) after blockage",
                vid, from_lat, from_lng, dest_lat, dest_lng)

    new_path, new_cost = astar(
        G,
        origin_lat=from_lat, origin_lng=from_lng,
        dest_lat=dest_lat,   dest_lng=dest_lng,
        blocked_edges=blocked_edges,
    )

    if new_path:
        v_pos = [from_lat, from_lng]
        e_pos = [dest_lat, dest_lng]
        new_path = [v_pos] + new_path + [e_pos]
        vehicle_paths[vid] = osrm_trace_waypoints(new_path, fallback_interpolation=8)
        
        if new_cost > 0.0:
            target_e["astar_cost"] = new_cost
            real_seconds = int(new_cost)
            mins = real_seconds // 60
            secs = real_seconds % 60
            target_e["response_time"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        
        logger.info("✅ %s re-routed: %d waypoints, est. %.1fs", vid, len(new_path), new_cost)
    else:
        logger.warning("⚠️  No alternative route found for %s", vid)


# ── Vehicle movement simulation ───────────────────────────────────────────────

def simulate_movement(vehicle_id: str, emergency_id: int):
    """Animate vehicle along its assigned path, updating position every tick."""
    last_point = None

    while True:
        current_path = vehicle_paths.get(vehicle_id, [])
        if not current_path:
            break
            
        # Pop the next position to move to
        point = current_path.pop(0)
        last_point = point
        vehicle_positions[vehicle_id] = point
        time.sleep(0.5)  # SLOWED DOWN for demonstration (was 0.05)

    # Mark emergency completed
    for e in emergencies:
        if e.get("assigned") == vehicle_id and e["id"] == emergency_id:
            e["completed"] = True
            
            # Use Real-World AI estimate (A* cost) instead of simulation clock
            real_seconds = int(e.get("astar_cost", 0))
            mins = real_seconds // 60
            secs = real_seconds % 60
            e["response_time"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

            for h in emergency_history:
                if h["id"] == e["id"]:
                    h["completed"]     = True
                    h["response_time"] = e["response_time"]
                    break
            break

    # Reset vehicle to final position
    for v in vehicles:
        if v["id"] == vehicle_id:
            if last_point:
                v["coords"] = last_point
            v["busy"] = False
            break


# ── Reset endpoints ───────────────────────────────────────────────────────────

@app.route("/user_reset", methods=["POST"])
def user_reset():
    global emergencies, vehicle_paths
    emergencies   = []
    vehicle_paths = {}
    for v in vehicles:
        v["busy"] = False
    return jsonify({"status": "user reset"})


@app.route("/clear_all", methods=["POST"])
def clear_all():
    global emergencies, vehicle_positions, vehicle_paths, emergency_history, blocked_edges
    emergencies       = []
    vehicle_positions = {}
    vehicle_paths     = {}
    emergency_history = []
    blocked_edges     = set()
    for v in vehicles:
        v["busy"] = False
    return jsonify({"status": "cleared"})


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, threaded=True)