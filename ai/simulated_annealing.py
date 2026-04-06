"""
Simulated Annealing for Multi-Vehicle, Multi-Emergency Optimization
===================================================================
When multiple emergencies are reported simultaneously, a greedy nearest-vehicle
approach gives suboptimal results. This module uses Simulated Annealing (a local
search meta-heuristic from the AI curriculum) to find the globally optimal
mapping of vehicles to emergencies.

Algorithm:
  1. Start with a greedy initial assignment.
  2. Repeatedly generate a neighbor state by swapping two assignments.
  3. Accept the neighbor if it improves cost, or probabilistically accept a worse
     neighbor (with probability e^(-delta/T)) to escape local optima.
  4. Cool the temperature and repeat until convergence.

Reference: Russell & Norvig, "Artificial Intelligence: A Modern Approach",
           Chapter 4 — Local Search Algorithms.
"""

import random
import math


def _total_cost(assignment: dict, cost_matrix: dict) -> float:
    """Sum A* path costs across all emergency→vehicle assignments."""
    return sum(
        cost_matrix.get((eid, vid), 1e9)
        for eid, vid in assignment.items()
    )


def _greedy_init(emergency_ids: list, vehicle_ids: list, cost_matrix: dict) -> dict:
    """Build an initial assignment greedily (nearest available vehicle)."""
    assignment = {}
    used = set()
    for eid in emergency_ids:
        best_vid = None
        best_cost = float("inf")
        for vid in vehicle_ids:
            if vid in used:
                continue
            c = cost_matrix.get((eid, vid), float("inf"))
            if c < best_cost:
                best_cost = c
                best_vid = vid
        if best_vid:
            assignment[eid] = best_vid
            used.add(best_vid)
    return assignment


def optimize_assignment(
    emergency_ids: list,
    vehicle_ids: list,
    cost_matrix: dict,
    initial_temp: float = 1000.0,
    cooling_rate: float = 0.995,
    max_iterations: int = 800,
) -> dict:
    """
    Simulated Annealing optimizer for emergency→vehicle assignment.

    Parameters
    ----------
    emergency_ids : list of emergency IDs needing assignment
    vehicle_ids   : list of available vehicle IDs (same type, not busy)
    cost_matrix   : dict mapping (emergency_id, vehicle_id) → A* path cost (seconds)
    initial_temp  : starting temperature (controls initial acceptance of worse states)
    cooling_rate  : multiplicative cooling factor per iteration (< 1.0)
    max_iterations: maximum SA iterations

    Returns
    -------
    dict: {emergency_id: vehicle_id} — globally optimal assignment found
    """

    # Edge case: nothing to assign
    if not emergency_ids or not vehicle_ids:
        return {}

    # ── Greedy initial state ──────────────────────────────────────────────────
    current = _greedy_init(emergency_ids, vehicle_ids, cost_matrix)
    if not current:
        return {}

    current_cost = _total_cost(current, cost_matrix)
    best = current.copy()
    best_cost = current_cost

    temperature = initial_temp
    eids = list(current.keys())

    # ── Annealing loop ────────────────────────────────────────────────────────
    for iteration in range(max_iterations):

        # Need at least 2 assignments to swap
        if len(eids) < 2:
            break

        # Generate neighbor: swap vehicle assignments of two random emergencies
        e1, e2 = random.sample(eids, 2)
        neighbor = current.copy()
        neighbor[e1], neighbor[e2] = neighbor[e2], neighbor[e1]

        neighbor_cost = _total_cost(neighbor, cost_matrix)
        delta = neighbor_cost - current_cost

        # Accept if better, or probabilistically accept if worse
        if delta < 0 or random.random() < math.exp(-delta / max(temperature, 1e-10)):
            current = neighbor
            current_cost = neighbor_cost

            # Track global best
            if current_cost < best_cost:
                best_cost = current_cost
                best = current.copy()

        # Cool down
        temperature *= cooling_rate

    return best


def sa_summary(best: dict, cost_matrix: dict) -> dict:
    """Helper to return a readable SA result summary."""
    total = _total_cost(best, cost_matrix)
    return {
        "assignments": best,
        "total_estimated_cost_seconds": round(total, 2),
        "algorithm": "Simulated Annealing"
    }
