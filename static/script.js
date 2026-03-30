let map;
let vehicleMarkers = {};
let routeLines = {};
let heatCircles = {};
let emergencyMarkers = {};
let lastEmergencyCount = 0;

let chart;

// 🔥 SMOOTH MOVEMENT FUNCTION
function smoothMove(marker, from, to, duration = 400) {
    let start = null;

    function animate(timestamp) {
        if (!start) start = timestamp;
        let progress = timestamp - start;
        let t = Math.min(progress / duration, 1);

        let lat = from[0] + (to[0] - from[0]) * t;
        let lng = from[1] + (to[1] - from[1]) * t;

        marker.setLatLng([lat, lng]);

        if (t < 1) {
            requestAnimationFrame(animate);
        }
    }

    requestAnimationFrame(animate);
}

const emergencyIcon = L.icon({
    iconUrl: "https://cdn-icons-png.flaticon.com/512/595/595067.png",
    iconSize: [34,34]
});

window.onload = () => {

    map = L.map('map').setView([13.0827, 80.2707], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
    .addTo(map);

    loadVehicles();
    setInterval(updateSystem, 500);
};

// 🚑 LOAD VEHICLES
async function loadVehicles(){
    let vehicles = await (await fetch("/get_vehicles")).json();

    vehicles.forEach(v=>{
        let iconHTML = v.type==="ambulance" ? "🚑" : "🚒";

        let icon = L.divIcon({
            html:`<div style="font-size:20px">${iconHTML}</div>`,
            className:""
        });

        vehicleMarkers[v.id] = L.marker(v.coords,{icon:icon})
        .addTo(map)
        .bindTooltip(v.id,{permanent:true});
    });
}

// 🔁 MAIN LOOP
async function updateSystem(){

    let [emergencies, vehicles, history] = await Promise.all([
        fetch("/get_emergencies").then(r=>r.json()),
        fetch("/get_vehicles").then(r=>r.json()),
        fetch("/get_history").then(r=>r.json())
    ]);

    // 🔔 ALERT BAR
    if(emergencies.length > 0){
        document.getElementById("alertBar").innerText =
        `🚨 ${emergencies.length} active emergencies`;
    } else {
        document.getElementById("alertBar").innerText = "No active alerts";
    }

    // 📊 COUNTS
    document.getElementById("count").innerText = emergencies.length;

    let busy = vehicles.filter(v=>v.busy).length;
    document.getElementById("busy").innerText = busy;
    document.getElementById("free").innerText = vehicles.length - busy;

    // 🧹 RESET CLEANUP
    if(emergencies.length === 0){
        for(let id in emergencyMarkers){
            map.removeLayer(emergencyMarkers[id]);
        }
        emergencyMarkers = {};

        for(let id in routeLines){
            map.removeLayer(routeLines[id]);
        }
        routeLines = {};

        for(let id in heatCircles){
            map.removeLayer(heatCircles[id]);
        }
        heatCircles = {};

        document.getElementById("emList").innerHTML = "";
        document.getElementById("historyList").innerHTML = "";
    }

    // 🔥 HEATMAP
    history.forEach(e=>{
        if(!heatCircles[e.id]){
            heatCircles[e.id] = L.circle([e.lat, e.lng], {
                radius: 80,
                color: "red",
                fillOpacity: 0.1
            }).addTo(map);
        }
    });

    // 🚨 EMERGENCY MARKERS
    emergencies.forEach(e=>{
        if(!emergencyMarkers[e.id]){
            emergencyMarkers[e.id] = L.marker([e.lat,e.lng],{
                icon: emergencyIcon
            }).addTo(map);
        }
    });

    // 🚨 ACTIVE UI
    let emHTML = "";
    emergencies.forEach((e)=>{
        let status = e.completed ? "Completed" : "Active";

        emHTML += `
        <div class="card">
            <b>E${e.id}</b> → ${e.assigned || "--"}<br>
            <small>${status}</small>
        </div>`;
    });
    document.getElementById("emList").innerHTML = emHTML;

    // 📜 HISTORY UI
    let hHTML = "";
    history.forEach((e)=>{
        let time = e.response_time ? `${e.response_time}s` : "--";

        hHTML += `
        <div class="card">
            <b>E${e.id}</b> → ${e.assigned || "--"}<br>
            ⏱️ ${time}
        </div>`;
    });
    document.getElementById("historyList").innerHTML = hHTML;

    // 🚑 VEHICLE PANEL
    let vHTML = "";
    vehicles.forEach(v=>{
        let status = v.busy ? "busy" : "available";

        vHTML += `
        <div class="card">
            🚑 ${v.id} <span class="${status}">${status}</span>
        </div>`;
    });
    document.getElementById("vehList").innerHTML = vHTML;

    // 📊 CHART
    let completed = history.filter(e=>e.completed).length;
    let pending = history.length - completed;

    if(!chart){
        chart = new Chart(document.getElementById("chart"), {
            type: "doughnut",
            data: {
                labels: ["Completed", "Pending"],
                datasets: [{
                    data: [completed, pending],
                    backgroundColor: ["#22c55e","#ef4444"]
                }]
            }
        });
    } else {
        chart.data.datasets[0].data = [completed, pending];
        chart.update();
    }

    // 🚑 VEHICLE MOVEMENT (SMOOTH)
    let positions = await Promise.all(
        vehicles.map(v => fetch(`/get_vehicle_position/${v.id}`).then(r=>r.json()))
    );

    let paths = await Promise.all(
        vehicles.map(v => fetch(`/get_vehicle_path/${v.id}`).then(r=>r.json()))
    );

    vehicles.forEach((v, i)=>{

        let pos = positions[i];
        let path = paths[i];

        let marker = vehicleMarkers[v.id];

        if(pos.length === 2){

            let current = marker.getLatLng();
            let from = [current.lat, current.lng];
            let to = pos;

            smoothMove(marker, from, to, 400);
        }

        if(path.length){

            if(routeLines[v.id]){
                map.removeLayer(routeLines[v.id]);
            }

            routeLines[v.id] = L.polyline(path,{
                color:"#38bdf8",
                weight:4
            }).addTo(map);
        }
    });
}

// 🧹 RESET
async function clearAll(){
    await fetch("/clear_all",{method:"POST"});
    location.reload();
}