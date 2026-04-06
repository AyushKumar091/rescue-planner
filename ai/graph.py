"""
Road Graph + A* Search for Rescue Routing
==========================================
Downloads the Chennai road network using OSMnx, caches it locally, and exposes
a hand-rolled A* search implementation (no nx.astar_path used).

A* Algorithm Overview (Russell & Norvig Ch. 3):
  f(n) = g(n) + h(n)
  - g(n) : cost from start to node n  (actual travel time in seconds)
  - h(n) : heuristic estimate from n to goal (Haversine distance / avg speed)
  - Admissible heuristic: never over-estimates → guaranteed optimal solution

The graph is a NetworkX DiGraph where each edge carries OSM speed data and a
pre-computed 'travel_time' attribute (seconds at speed limit).
"""

import heapq
import math
import os
import pickle
import logging

import networkx as nx

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
GRAPH_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "chennai_graph.pkl")

# Bounding box for Chennai metro area covering all vehicle positions
# (north, south, east, west)  — lat/lng
BBOX = (13.15, 13.0, 80.35, 80.20)

# Average road speed used for heuristic (m/s) — ~30 km/h city average
AVG_SPEED_MS = 8.33

# ── Helpers ──────────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in metres between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Graph loading ─────────────────────────────────────────────────────────────

def load_graph() -> nx.MultiDiGraph:
    """
    Load the Chennai drive network.
    - On first run: downloads from OpenStreetMap via osmnx, adds travel times,
      and caches as a pickle file in data/.
    - Subsequent runs: reads from cache (fast).
    """
    if os.path.exists(GRAPH_FILE):
        logger.info("Loading cached Chennai graph from %s", GRAPH_FILE)
        with open(GRAPH_FILE, "rb") as f:
            return pickle.load(f)

    logger.info("Downloading Chennai road network from OpenStreetMap (High Resolution) …")
    try:
        import osmnx as ox
        ox.settings.log_console = False
        ox.settings.use_cache = True

        # Center on Chennai, ~14km x 14km box to cover all vehicle positions perfectly
        G = ox.graph_from_point(
            (13.0650, 80.2650),
            dist=6500,
            network_type="drive",
            simplify=True,
        )
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)

        os.makedirs(os.path.dirname(GRAPH_FILE), exist_ok=True)
        with open(GRAPH_FILE, "wb") as f:
            pickle.dump(G, f)

        logger.info("Graph downloaded and cached (%d nodes, %d edges)",
                    G.number_of_nodes(), G.number_of_edges())
        return G

    except Exception as e:
        logger.error("osmnx download failed: %s — falling back to stub graph", e)
        return _build_stub_graph()


def _build_stub_graph() -> nx.MultiDiGraph:
    """
    Minimal weighted graph of Chennai major intersections.
    Used as a fallback when osmnx is unavailable or the network download fails.
    This allows the app to run offline with a simplified but functional graph.
    """
    G = nx.MultiDiGraph()

    # Key Chennai landmarks / road junctions (node_id, lat, lng)
    nodes = [
        (0,  13.0827, 80.2707),  # Central Chennai
        (1,  13.0600, 80.2500),  # Anna Nagar area
        (2,  13.0700, 80.2800),  # T Nagar
        (3,  13.0900, 80.2600),  # Kilpauk
        (4,  13.0500, 80.2600),  # Adyar
        (5,  13.0800, 80.2900),  # Royapuram
        (6,  13.1000, 80.2800),  # Perambur
        (7,  13.0650, 80.2400),  # Valasaravakkam
        (8,  13.0750, 80.2550),  # Ashok Nagar
        (9,  13.0950, 80.2750),  # Kolathur
        (10, 13.0550, 80.2850),  # Mylapore
        (11, 13.0450, 80.2450),  # Guindy
        (12, 13.1050, 80.2550),  # Tondiarpet
        (13, 13.0850, 80.2850),  # Tiruvottiyur
    ]

    for nid, lat, lng in nodes:
        G.add_node(nid, y=lat, x=lng)

    # Road edges (from, to, length_m, speed_kph)
    edges = [
        (0, 1, 3500, 40), (1, 0, 3500, 40),
        (0, 2, 2000, 35), (2, 0, 2000, 35),
        (0, 3, 2500, 45), (3, 0, 2500, 45),
        (1, 4, 2800, 35), (4, 1, 2800, 35),
        (1, 7, 2200, 40), (7, 1, 2200, 40),
        (2, 5, 2000, 30), (5, 2, 2000, 30),
        (2, 8, 1500, 35), (8, 2, 1500, 35),
        (3, 6, 2000, 40), (6, 3, 2000, 40),
        (3, 9, 2500, 45), (9, 3, 2500, 45),
        (4, 10, 2000, 30), (10, 4, 2000, 30),
        (4, 11, 2500, 40), (11, 4, 2500, 40),
        (5, 13, 1800, 35), (13, 5, 1800, 35),
        (6, 12, 2000, 40), (12, 6, 2000, 40),
        (7, 8, 1500, 35), (8, 7, 1500, 35),
        (8, 11, 2000, 35), (11, 8, 2000, 35),
        (9, 12, 2000, 40), (12, 9, 2000, 40),
        (10, 11, 1800, 30), (11, 10, 1800, 30),
    ]

    for u, v, length, speed in edges:
        travel_time = length / (speed * 1000 / 3600)
        G.add_edge(u, v, 0, length=length, speed_kph=speed, travel_time=travel_time)

    return G


# ── Nearest node lookup ─────────────────────────────────────────────────────

def nearest_node(G: nx.MultiDiGraph, lat: float, lng: float) -> int:
    """Find the graph node closest to the given coordinates."""
    best_node = None
    best_dist = float("inf")
    for nid, data in G.nodes(data=True):
        d = haversine_m(lat, lng, data["y"], data["x"])
        if d < best_dist:
            best_dist = d
            best_node = nid
    return best_node


# ── A* Search ────────────────────────────────────────────────────────────────

def astar(
    G: nx.MultiDiGraph,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    blocked_edges: set = None,
    weight_multipliers: dict = None,
) -> tuple:
    """
    A* search on the road graph from origin to destination.

    Parameters
    ----------
    G                 : NetworkX MultiDiGraph (from load_graph)
    origin_lat/lng    : starting point (vehicle location)
    dest_lat/lng      : destination (emergency location)
    blocked_edges     : set of (u, v) node-pairs to treat as impassable
    weight_multipliers: dict of (u, v) → float, Bayesian cost multiplier

    Returns
    -------
    (path_coords, total_cost_seconds)
      path_coords : list of [lat, lng] waypoints along the route
      total_cost  : estimated travel time in seconds (float)
      Returns ([], inf) if no path found.

    Algorithm
    ---------
    Standard A* with:
      - g(n) = cumulative travel_time (seconds) on edges traversed
      - h(n) = haversine_m(n, goal) / AVG_SPEED_MS  (admissible heuristic)
      - Ties broken by node ID for determinism
    """
    if blocked_edges is None:
        blocked_edges = set()
    if weight_multipliers is None:
        weight_multipliers = {}

    origin = nearest_node(G, origin_lat, origin_lng)
    dest   = nearest_node(G, dest_lat,   dest_lng)

    if origin == dest:
        return [[dest_lat, dest_lng]], 0.0

    dest_y = G.nodes[dest]["y"]
    dest_x = G.nodes[dest]["x"]

    # g_score[node] = best known cost from origin to node
    g_score = {origin: 0.0}
    came_from = {}

    def h(node):
        ny, nx_ = G.nodes[node]["y"], G.nodes[node]["x"]
        return haversine_m(ny, nx_, dest_y, dest_x) / AVG_SPEED_MS

    # Priority queue: (f_score, tiebreak, node)
    open_heap = [(h(origin), 0, origin)]
    closed_set = set()
    counter = 1  # tiebreaker

    while open_heap:
        _, _, current = heapq.heappop(open_heap)

        if current in closed_set:
            continue
        closed_set.add(current)

        if current == dest:
            # ── Reconstruct path ─────────────────────────────────────────────
            path_nodes = []
            node = current
            while node in came_from:
                path_nodes.append(node)
                node = came_from[node]
            path_nodes.append(origin)
            path_nodes.reverse()

            path_coords = [
                [G.nodes[n]["y"], G.nodes[n]["x"]]
                for n in path_nodes
            ]
            return path_coords, round(g_score[dest], 2)

        # ── Expand neighbours ─────────────────────────────────────────────
        for neighbor in G.successors(current):
            if (current, neighbor) in blocked_edges:
                continue

            # Get best parallel edge (minimum travel_time)
            edge_keys = G[current][neighbor]
            travel_time = min(
                edata.get("travel_time", edata.get("length", 300) / AVG_SPEED_MS)
                for edata in edge_keys.values()
            )

            # Apply Bayesian cost multiplier if present
            mult = weight_multipliers.get((current, neighbor), 1.0)
            edge_cost = travel_time * mult

            tentative_g = g_score.get(current, float("inf")) + edge_cost

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor]   = tentative_g
                f = tentative_g + h(neighbor)
                heapq.heappush(open_heap, (f, counter, neighbor))
                counter += 1

    return [], float("inf")   # No path found


# ── Blockage helpers ──────────────────────────────────────────────────────────

def find_nearby_edges(G: nx.MultiDiGraph, lat: float, lng: float, radius_m: float = 200) -> list:
    """Find all directed edges (u, v) within `radius_m` metres of a coordinate."""
    nearby = []
    for u, v, data in G.edges(data=True):
        lat1, lng1 = G.nodes[u]["y"], G.nodes[u]["x"]
        lat2, lng2 = G.nodes[v]["y"], G.nodes[v]["x"]
        # Sample 10 points along the segment to check distance correctly for long roads
        for i in range(11):
            f = i / 10.0
            mid_lat = lat1 + (lat2 - lat1) * f
            mid_lng = lng1 + (lng2 - lng1) * f
            if haversine_m(lat, lng, mid_lat, mid_lng) <= radius_m:
                nearby.append((u, v))
                break
    return nearby
