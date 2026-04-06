"""
Bayesian Network for Road Uncertainty Estimation
================================================
Models the probabilistic relationship between weather, traffic, and road blockage.

Network structure:
    Rain (yes/no) --> Traffic (low/high) --> Blockage (true/false)

All CPTs (Conditional Probability Tables) are defined explicitly — no external
Bayesian library is used. This is a scratch implementation to demonstrate the
theoretical concept from the course curriculum.
"""


class BayesianRoadNetwork:
    """
    A simple hand-rolled Bayesian Network with three nodes:
      - Rain   : whether it is raining        → P(Rain=yes) = 0.3
      - Traffic: congestion level              → P(Traffic=high | Rain)
      - Blockage: whether a road may be blocked → P(Blockage | Traffic)

    Usage:
        bn = BayesianRoadNetwork()
        bn.set_conditions(rain=True, traffic="high")
        prob = bn.blockage_probability()      # e.g. 0.72
        mult = bn.edge_weight_multiplier()    # e.g. 2.44  (used in A* edge costs)
    """

    # ── Priors ────────────────────────────────────────────────────────────────
    P_RAIN = {
        True: 0.30,   # 30% chance of rain
        False: 0.70,
    }

    # ── CPT: P(Traffic = high | Rain) ────────────────────────────────────────
    P_TRAFFIC_HIGH_GIVEN_RAIN = {
        True:  0.80,   # if raining → 80% chance of high traffic
        False: 0.30,   # if not raining → 30% chance of high traffic
    }

    # ── CPT: P(Blockage = True | Traffic) ───────────────────────────────────
    P_BLOCKAGE_GIVEN_TRAFFIC_HIGH = {
        True:  0.72,   # high traffic → 72% chance of road blockage
        False: 0.15,   # low traffic  → 15% chance of road blockage
    }

    def __init__(self):
        # Current observed environment state
        self.rain: bool = False
        self.traffic: str = "low"   # "low" or "high"

    def set_conditions(self, rain: bool, traffic: str):
        """Update the observed evidence nodes."""
        self.rain = bool(rain)
        self.traffic = traffic.lower()

    def blockage_probability(self, rain: bool = None, traffic: str = None) -> float:
        """
        Compute P(Blockage = True) given observed Rain and Traffic.

        If no arguments are passed, uses the internally stored state.
        This performs direct CPT lookup (exact inference on this simple network).
        """
        r = rain if rain is not None else self.rain
        t = traffic if traffic is not None else self.traffic

        is_high_traffic = (t == "high")
        return self.P_BLOCKAGE_GIVEN_TRAFFIC_HIGH[is_high_traffic]

    def joint_blockage_probability(self) -> float:
        """
        Compute P(Blockage = True) marginalizing over unobserved Traffic.
        Used when only rain state is known (full Bayesian inference).

        P(Blockage) = Σ_traffic P(Blockage | Traffic) * P(Traffic | Rain)
        """
        p_high = self.P_TRAFFIC_HIGH_GIVEN_RAIN[self.rain]
        p_low = 1 - p_high

        p_blockage = (
            self.P_BLOCKAGE_GIVEN_TRAFFIC_HIGH[True]  * p_high +
            self.P_BLOCKAGE_GIVEN_TRAFFIC_HIGH[False] * p_low
        )
        return round(p_blockage, 4)

    def edge_weight_multiplier(self) -> float:
        """
        Returns a cost multiplier for A* edge weights based on blockage probability.

        Mapping: probability 0.0 → multiplier 1.0 (no extra cost)
                 probability 1.0 → multiplier 3.5 (3.5x travel time penalty)

        This dynamically adjusts A* to prefer safer (lower blockage risk) roads.
        """
        prob = self.blockage_probability()
        multiplier = 1.0 + 2.5 * prob
        return round(multiplier, 3)

    def summary(self) -> dict:
        """Return current Bayesian state for API/frontend consumption."""
        return {
            "rain": self.rain,
            "traffic": self.traffic,
            "blockage_probability": self.blockage_probability(),
            "joint_blockage_probability": self.joint_blockage_probability(),
            "edge_weight_multiplier": self.edge_weight_multiplier(),
        }
