# 🚑 Intelligent Emergency Rescue Planner

An AI-driven emergency response simulation and dispatch system designed for the city of Chennai. This project replaces standard routing APIs with custom-built artificial intelligence algorithms to provide peak efficiency in rescue operations.

---

## 🌟 Overview

The **Intelligent Emergency Rescue Planner** is a full-stack application that simulates real-time emergency dispatching. It uses a custom-built road network graph of Chennai and implements three core AI algorithms to handle routing, environmental uncertainty, and multi-vehicle assignment optimization.

### Key Capabilities:
- **Optimal Routing:** Finds the fastest path for ambulances and fire trucks using a custom A* implementation.
- **Probabilistic Risk Assessment:** Uses Bayesian Networks to adjust routes based on real-time weather (rain) and traffic conditions.
- **Global Dispatch Optimization:** Employs Simulated Annealing to solve the "Multi-Emergency, Multi-Vehicle" assignment problem.
- **Dynamic Re-Routing:** If a road blockage is reported, vehicles in transit automatically calculate new detours.

---

## 🛠️ Technology Stack

- **Backend:** Python, Flask
- **AI/Math:** NetworkX (Graph theory), OSMnx (Mapping/GIS), Joblib (ML model loading), NumPy
- **Frontend:** HTML5, CSS3 (Vanilla), JavaScript (ES6+), Leaflet.js
- **Utilities:** Geopy (Coordinate math), Requests (APIs)

---

## 📂 Project Structure & Component Functions

### 1. Main Controller
- **`app.py`**: The central "brain" of the system. It manages the Flask server, maintains the state of all vehicles and emergencies in memory, and coordinates between the AI modules and the web interface.

### 2. AI Algorithms (`ai/` folder)
This directory contains the core mathematical logic implemented from scratch:
- **`ai/graph.py` (A* Search):** Responsible for the road network logic. It implements the **A* Search Algorithm** to find the shortest path between any two coordinates in Chennai by calculating travel time based on road weights and distances.
- **`ai/bayesian.py` (Bayesian Network):** Handles uncertainty. It uses a **Bayesian Belief Network** to calculate the probability of road blockages based on inputs like Rain and Traffic levels. This probability is converted into a "cost multiplier" that makes risky roads mathematically slower for the A* algorithm.
- **`ai/simulated_annealing.py` (Simulated Annealing):** Optimizes dispatching. When multiple emergencies occur simultaneously, this algorithm trial-runs thousands of vehicle-to-emergency permutations to find the configuration that results in the lowest overall city-wide response time.

### 3. User Interface (`templates/` & `static/`)
- **`templates/index.html`**: The **Dispatcher Dashboard**. Provides a high-level view of the city, real-time vehicle tracking, environment controls, and AI performance logs.
- **`templates/user.html`**: The **Citizen Portal**. A simple interface for users to report emergencies by clicking on the map.
- **`static/script.js`**: Manages the frontend animations, map rendering via Leaflet, and asynchronous communication (polling) with the backend.

### 4. Machine Learning & Data
- **`model.pkl`**: A trained **Random Forest** model that acts as a secondary verification step for vehicle selection, ensuring AI decisions align with historical efficiency patterns.
- **`data/`**: Stores the serialized road graph of Chennai for instant loading without needing to re-download from OpenStreetMap every time.

---

## 🧠 Core AI Logic Explained

### A* Search (Routing)
Instead of using a black-box API, we built A* from the ground up. It uses a **Heuristic function** (Straight-line distance) to prioritize nodes that are physically closer to the destination, ensuring the search is significantly faster than standard Dijkstra.

### Bayesian Network (Environmental Adaptation)
The system models conditional probabilities:
`P(Blockage | Traffic, Rain)`.
If `Rain = True`, the probability of traffic increases, which in turn increases the probability of a blockage. The system then inflates the "weight" of road segments, forcing the A* algorithm to find "detours" that are mathematically faster given the current risk.

### Simulated Annealing (Resource Allocation)
Dispatching is a "Combinatorial Optimization" problem. If 5 ambulances are available for 5 emergencies, there are 120 possible ways to assign them. Simulated Annealing explores these possibilities by "shuffling" assignments and accepting improvements, while occasionally accepting slightly worse assignments early on (the "Metropolis Criterion") to avoid getting stuck in a local optimum.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Pip (Python Package Manager)

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python app.py
   ```
4. Open your browser and navigate to:
   - **Dispatcher Dashboard:** `http://127.0.0.1:5000/control`
   - **User Portal:** `http://127.0.0.1:5000/user`

---

## 📊 Evaluation
The system tracks **Response Time** and **Algorithm Accuracy**. All routing decisions are logged in the terminal and visible on the dashboard "AI Engine" panel, showing the real-time cost calculations made by the A* and Bayesian modules.
