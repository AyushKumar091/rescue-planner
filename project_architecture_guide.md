# Presentation Guide: Emergency Rescue Planner

This document provides a simple, structured overview of the entire project. It is designed to help you quickly explain the project's folder structure, the core files, and the "how and why" of the artificial intelligence algorithms you implemented to your faculty.

---

## 📁 System Folder & File Structure

Here is a breakdown of every folder and what exactly those files do:

### 1. The Main Server
*   `app.py`: Think of this as the "Brain Controller". It is a Python Flask backend. It holds the entire simulation in memory (tracking every single vehicle and active emergency). It listens to the web dashboard and actively manages what the AI should do.

### 2. The Custom AI Module (`ai/` folder)
This folder is the core of your project. It contains the actual curriculum-based AI algorithms built from scratch:
*   `ai/graph.py`: **(A* Search Algorithm)** This file is responsible for downloading the actual map of Chennai using Python mathematically. It contains the logic that allows an ambulance to physically search the road map and find the fastest route to an emergency.
*   `ai/bayesian.py`: **(Bayesian Network)** This file handles uncertainty. It contains the probabilistic mathematics that translates UI toggles (like Rain or Traffic) into a numerical penalty multiplier to make the A* search avoid risky roads.
*   `ai/simulated_annealing.py`: **(Simulated Annealing)** This file wakes up only when *multiple* emergencies happen exactly at the same time. It mathematically optimizes which ambulance should go to which emergency to get the fastest average response time across the entire city.

### 3. The User Interface (`templates/` and `static/`)
*   `templates/index.html` & `templates/user.html`: These are the visual web pages. `user.html` allows a citizen to place an emergency on the map. `index.html` is the heavy-duty Dispatcher Dashboard that shows the real-time simulation, Bayesian controls, analytics, and AI logs.
*   `static/script.js`: This is the frontend logic. It talks to `app.py` continuously in the background, updating the animations of the vehicles moving on the map and pushing your UI button clicks back to the Python server.

### 4. Machine Learning & Data (`ml_model/` and `data/`)
*   `ml_model/model.pkl`: A trained Random Forest Machine Learning model. After the math algorithms pick an ambulance, it acts as a lightweight secondary confirmation step to ensure the mathematical choice aligns with historical dispatch patterns.
*   `data/chennai_graph.pkl`: A locally saved copy of the Chennai OpenStreetMap road network. Because downloading an entire city takes a few seconds over the internet, we save it here so the simulation boots up instantly next time.

---

## 🧠 Answering Faculty Questions (The "How & Why")

Use these simple explanations if your faculty asks you how the core algorithms function under the hood:

### How does the ambulance find the best route? (A* Search)
"We built the **A\* (A-Star) Search Algorithm** in Python. Instead of using a Google Maps black-box API, `ai/graph.py` mathematically explores the Chennai road intersections. It calculates the actual physical time it takes to drive down a road based on speed limits. To make it extremely fast, it uses a 'heuristic' which estimates the remaining straight-line distance, ensuring it always calculates towards the destination instead of checking random dead-end roads."

### How do you handle bad weather? (Bayesian Network)
"We built a **Bayesian Belief Network** (`ai/bayesian.py`) to handle environmental uncertainty mathematically. We created a conditional probability chain where `Rain causes Traffic` and `Traffic causes Blockages`. When the user toggles 'Rain ON', the code outputs a continuous risk penalty (like 2.5x). It multiplies the travel time of every road in the A* graph by 2.5x. Instantly, all roads become mathematically 'slower', causing the A* algorithm to automatically search for entirely different, theoretically safer detour routes."

### How do you dispatch vehicles to multiple simultaneous emergencies? (Simulated Annealing)
"We used **Simulated Annealing** (`ai/simulated_annealing.py`) to solve the global optimization problem. If 5 emergencies happen, simply sending the closest ambulance to the first incident might ruin the response time for the fourth incident. Our code takes all active emergencies and available ambulances and randomly swaps their assignments. If the total city-wide response time drops, it keeps the swap. Because of a math trick called a 'cooling schedule', it will occasionally accept a *worse* swap just to ensure it doesn't get stuck in a bad pattern. After evaluating permutations, it finds the absolute perfect dispatch assignments for all 5 emergencies simultaneously."

### What happens if a road is suddenly blocked? (Dynamic Re-Routing)
"We implemented **Dynamic Re-Routing** right inside `app.py`. We added a 'Report Blockage' button on the dashboard. When clicked, Python mathematically isolates the exact road segment closest to the click and deletes it from the internal A* mathematical graph. Instantly, any ambulance currently on its way through that specific road is completely stopped, and forced to re-run the A* algorithm from its exact current GPS coordinates. It then seamlessly veers off its original path and takes the new detour."
