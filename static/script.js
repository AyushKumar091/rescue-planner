// ─── State ────────────────────────────────────────────────────────────────────
let map;
let vehicleMarkers  = {};
let routeLines      = {};
let heatCircles     = {};
let emergencyMarkers= {};
let blockageMarkers = [];

let blockageModeActive = false;
let chart;

// Current environment state (mirrors the Bayesian Network server-side)
let envState = { rain: false, traffic: "low" };

// ─── Map init ─────────────────────────────────────────────────────────────────
window.onload = () => {
  map = L.map('map').setView([13.0827, 80.2707], 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  // Map click: either add emergency (normal mode) or report blockage
  map.on('click', onMapClick);

  loadVehicles();
  updateBayesianDisplay();
  setInterval(updateSystem, 600);
  setInterval(updateBayesianDisplay, 3000);
};

// ─── Map click handler ────────────────────────────────────────────────────────
async function onMapClick(e) {
  if (blockageModeActive) {
    await reportBlockage(e.latlng.lat, e.latlng.lng);
    toggleBlockageMode();   // exit blockage mode after one click
    return;
  }
  // Normal mode: handled by user.html only. Index.html has no emergency-add on click.
  // (dispatcher view — emergencies come from the user portal)
}

// ─── Load vehicles on startup ─────────────────────────────────────────────────
async function loadVehicles() {
  const vehicles = await fetch("/get_vehicles").then(r => r.json());

  vehicles.forEach(v => {
    const emoji = v.type === "ambulance" ? "🚑" : "🚒";
    const icon  = L.divIcon({
      html: `<div style="font-size:20px;filter:drop-shadow(0 0 3px #fff)">${emoji}</div>`,
      className: ""
    });
    vehicleMarkers[v.id] = L.marker(v.coords, { icon })
      .addTo(map)
      .bindTooltip(v.id, { permanent: true, className: "vehicle-label" });
  });
}

// ─── Bayesian Network display ─────────────────────────────────────────────────
async function updateBayesianDisplay() {
  try {
    const data = await fetch("/get_environment").then(r => r.json());
    document.getElementById("bayes-prob").textContent =
      (data.blockage_probability * 100).toFixed(0) + "%";
    document.getElementById("bayes-mult").textContent =
      "×" + data.edge_weight_multiplier;

    // Colour the blockage probability indicator by risk level
    const prob = data.blockage_probability;
    const el = document.getElementById("bayes-prob");
    el.style.color = prob > 0.6 ? "#ef4444" : prob > 0.35 ? "#facc15" : "#22c55e";
  } catch (_) {}
}

// ─── Environment toggles (Rain / Traffic) ─────────────────────────────────────
function setRain(on) {
  envState.rain = on;
  document.getElementById("btn-rain-on") .classList.toggle("active",  on);
  document.getElementById("btn-rain-off").classList.toggle("active", !on);
  pushEnvironment();
}

function setTraffic(level) {
  envState.traffic = level;
  document.getElementById("btn-traffic-low") .classList.toggle("active", level === "low");
  document.getElementById("btn-traffic-high").classList.toggle("active", level === "high");
  pushEnvironment();
}

async function pushEnvironment() {
  const res = await fetch("/set_environment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(envState)
  }).then(r => r.json());

  addAILog(`🌧️ Bayesian: rain=${envState.rain}, traffic=${envState.traffic} → prob ${(res.blockage_probability*100).toFixed(0)}%`);
  updateBayesianDisplay();
}

// ─── Blockage reporting ───────────────────────────────────────────────────────
function toggleBlockageMode() {
  blockageModeActive = !blockageModeActive;
  document.getElementById("blockageModeBar")?.remove();
  document.getElementById("blockageBar").classList.toggle("active", blockageModeActive);
  document.getElementById("blockageBtn").classList.toggle("btn-danger", blockageModeActive);
  document.getElementById("blockageBtn").classList.toggle("btn-warn",  !blockageModeActive);
  map.getContainer().style.cursor = blockageModeActive ? "crosshair" : "";
}

async function reportBlockage(lat, lng) {
  const res = await fetch("/report_blockage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng })
  }).then(r => r.json());

  // Place red blockage marker on map
  const bIcon = L.divIcon({
    html: `<div style="font-size:22px">🚧</div>`,
    className: ""
  });
  blockageMarkers.push(L.marker([lat, lng], { icon: bIcon }).addTo(map));

  const msg = `🚧 Blockage @ (${lat.toFixed(3)}, ${lng.toFixed(3)}) — ${res.edges || 0} edges. Re-routing: ${(res.rerouted||[]).join(", ") || "none"}`;
  addAILog(msg, "warn");
}

// ─── AI Decision Log ──────────────────────────────────────────────────────────
let lastAssigned = {};

function addAILog(msg, type = "") {
  const box = document.getElementById("aiLog");
  const line = document.createElement("div");
  line.className = "log-entry " + type;
  line.textContent = new Date().toLocaleTimeString() + " " + msg;
  box.prepend(line);
  // Keep last 12 entries
  while (box.children.length > 12) box.removeChild(box.lastChild);
}

// ─── Smooth movement ──────────────────────────────────────────────────────────
function smoothMove(marker, from, to, duration = 450) {
  let start = null;
  function step(ts) {
    if (!start) start = ts;
    const t = Math.min((ts - start) / duration, 1);
    marker.setLatLng([
      from[0] + (to[0] - from[0]) * t,
      from[1] + (to[1] - from[1]) * t,
    ]);
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ─── Icons ────────────────────────────────────────────────────────────────────
const emergencyIcon = L.icon({
  iconUrl: "https://cdn-icons-png.flaticon.com/512/595/595067.png",
  iconSize: [30, 30]
});

// ─── Main update loop ─────────────────────────────────────────────────────────
async function updateSystem() {
  const [emergencies, vehicles, history] = await Promise.all([
    fetch("/get_emergencies").then(r => r.json()),
    fetch("/get_vehicles").then(r => r.json()),
    fetch("/get_history").then(r => r.json()),
  ]);

  // Alert bar
  document.getElementById("alertBar").textContent =
    emergencies.length > 0 ? `🚨 ${emergencies.length} active emergencies` : "No active alerts";

  // Stats
  document.getElementById("count").textContent = emergencies.length;
  const busy = vehicles.filter(v => v.busy).length;
  document.getElementById("busy").textContent = busy;
  document.getElementById("free").textContent = vehicles.length - busy;

  // Clean up if reset
  if (emergencies.length === 0) {
    for (const id in emergencyMarkers) { map.removeLayer(emergencyMarkers[id]); }
    emergencyMarkers = {};
    for (const id in routeLines) { map.removeLayer(routeLines[id]); }
    routeLines = {};
    for (const id in heatCircles) { map.removeLayer(heatCircles[id]); }
    heatCircles = {};
    blockageMarkers.forEach(m => map.removeLayer(m));
    blockageMarkers = [];
    document.getElementById("emList").innerHTML = "";
    document.getElementById("historyList").innerHTML = "";
  }

  // Heatmap for history
  history.forEach(e => {
    if (!heatCircles[e.id]) {
      heatCircles[e.id] = L.circle([e.lat, e.lng], {
        radius: 100, color: "#ef4444", fillOpacity: 0.08, weight: 1
      }).addTo(map);
    }
  });

  // Emergency markers
  emergencies.forEach(e => {
    if (!emergencyMarkers[e.id]) {
      emergencyMarkers[e.id] = L.marker([e.lat, e.lng], { icon: emergencyIcon })
        .bindPopup(`<b>Emergency E${e.id}</b><br>Type: ${e.type}<br>Severity: ${e.severity || "?"}`)
        .addTo(map);
    }
  });

  // AI log: announce new assignments
  emergencies.forEach(e => {
    if (e.assigned && lastAssigned[e.id] !== e.assigned) {
      lastAssigned[e.id] = e.assigned;
      addAILog(`✅ E${e.id} → ${e.assigned} via ${e.algorithm_used || "AI"} (cost: ${e.astar_cost ? e.astar_cost.toFixed(0)+"s" : "?"})`);
    }
  });

  // Active emergencies list
  document.getElementById("emList").innerHTML = emergencies.map(e => `
    <div style="font-size:12px;padding:6px 0;border-bottom:1px solid #1e293b">
      <b>E${e.id}</b> → <span style="color:#38bdf8">${e.assigned || "--"}</span>
      <span style="color:#94a3b8;margin-left:8px;font-size:10px">${e.response_time ? 'ETA: ' + e.response_time : ''}</span>
      <span style="float:right;color:${e.completed ? "#22c55e" : "#facc15"}">${e.completed ? "✅" : "⏳"}</span>
    </div>`).join("");

  // History list
  document.getElementById("historyList").innerHTML = history.slice().reverse().slice(0, 6).map(e => `
    <div style="font-size:11px;padding:4px 0;border-bottom:1px solid #1e293b;color:#94a3b8">
      E${e.id} → ${e.assigned || "--"} ⏱️ ${e.response_time ? e.response_time : "--"}
    </div>`).join("");

  // Vehicle list
  document.getElementById("vehList").innerHTML = vehicles.map(v => `
    <div style="font-size:12px;padding:4px 0;display:flex;align-items:center">
      <span class="dot ${v.busy ? "dot-busy" : "dot-free"}"></span>
      ${v.type === "ambulance" ? "🚑" : "🚒"} <b>${v.id}</b>
      <span style="margin-left:auto;font-size:11px;color:${v.busy ? "#facc15" : "#22c55e"}">${v.busy ? "busy" : "free"}</span>
    </div>`).join("");

  // Doughnut chart
  const completed = history.filter(e => e.completed).length;
  const pending   = history.length - completed;
  if (!chart) {
    chart = new Chart(document.getElementById("chart"), {
      type: "doughnut",
      data: {
        labels: ["Completed", "Pending"],
        datasets: [{ data: [completed, pending], backgroundColor: ["#22c55e", "#ef4444"], borderWidth: 0 }]
      },
      options: {
        plugins: { legend: { labels: { color: "#e2e8f0", font: { size: 11 } } } }
      }
    });
  } else {
    chart.data.datasets[0].data = [completed, pending];
    chart.update();
  }

  // Vehicle positions and route lines
  const positions = await Promise.all(
    vehicles.map(v => fetch(`/get_vehicle_position/${v.id}`).then(r => r.json()))
  );
  const paths = await Promise.all(
    vehicles.map(v => fetch(`/get_vehicle_path/${v.id}`).then(r => r.json()))
  );

  vehicles.forEach((v, i) => {
    const pos  = positions[i];
    const path = paths[i];

    if (pos && pos.length === 2) {
      const cur  = vehicleMarkers[v.id].getLatLng();
      smoothMove(vehicleMarkers[v.id], [cur.lat, cur.lng], pos);
    }

    if (path && path.length > 0) {
      if (routeLines[v.id]) map.removeLayer(routeLines[v.id]);
      routeLines[v.id] = L.polyline(path, {
        color: v.type === "ambulance" ? "#38bdf8" : "#f97316",
        weight: 3,
        dashArray: "6 4",
        opacity: 0.8
      }).addTo(map);
    }
  });
}

// ─── Reset ────────────────────────────────────────────────────────────────────
async function clearAll() {
  await fetch("/clear_all", { method: "POST" });
  lastAssigned = {};
  location.reload();
}