let map;
let emergencyMarkers = {};
let vehicleMarkers = {};
let routeLines = {};
let heatCircles = {};
let lastEmergencyCount = 0;

const emergencyIcon = L.icon({
    iconUrl: "https://cdn-icons-png.flaticon.com/512/595/595067.png",
    iconSize: [34,34]
});

window.onload = () => {

    map = L.map('map').setView([13.0827, 80.2707], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
    .addTo(map);

    setTimeout(() => map.invalidateSize(), 300);

    loadVehicles();
    setInterval(updateSystem, 500);
};

// 🚑 LOAD VEHICLES
async function loadVehicles(){

    let vehicles = await (await fetch("/get_vehicles")).json();

    vehicles.forEach(v=>{
        let iconHTML = v.type==="ambulance" ? "➕" : "🚒";

        let icon = L.divIcon({
            html:`<div style="font-size:22px;color:#38bdf8">${iconHTML}</div>`,
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

    // ✅ COUNTS
    document.getElementById("count").innerText = emergencies.length;

    let busy = vehicles.filter(v=>v.busy).length;
    document.getElementById("busy").innerText = busy;
    document.getElementById("free").innerText = vehicles.length - busy;

    // 🧹 CLEAR UI IF RESET
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
        document.getElementById("stats").innerHTML = `
        Completed: 0<br>
        Avg Response: 0s
        `;
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

    // 🚨 ACTIVE EMERGENCIES UI
    let emHTML = "";

    emergencies.forEach((e)=>{
        let status = e.completed ? "Completed" : "Active";

        emHTML += `
        <div class="card active-emergency">
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

    // 📊 STATS
    let completed = history.filter(e=>e.completed).length;
    let times = history.filter(e=>e.response_time).map(e=>e.response_time);

    let avg = 0;
    if(times.length){
        avg = (times.reduce((a,b)=>a+b,0)/times.length).toFixed(2);
    }

    document.getElementById("stats").innerHTML = `
    Completed: ${completed}<br>
    Avg Response: ${avg}s
    `;

    // 🚑 FETCH VEHICLE DATA (PARALLEL)
    let positions = await Promise.all(
        vehicles.map(v => fetch(`/get_vehicle_position/${v.id}`).then(r=>r.json()))
    );

    let paths = await Promise.all(
        vehicles.map(v => fetch(`/get_vehicle_path/${v.id}`).then(r=>r.json()))
    );

    vehicles.forEach((v, i) => {

        let pos = positions[i];
        let path = paths[i];

        // MOVE VEHICLE
        if(pos.length===2){
            vehicleMarkers[v.id].setLatLng(pos);
        }

        // DRAW ROUTE
        if(path.length){

            if(routeLines[v.id]){
                map.removeLayer(routeLines[v.id]);
            }

            routeLines[v.id] = L.polyline(path,{
                color:"#38bdf8",
                weight:3
            }).addTo(map);
        }
    });
}

// 🧹 RESET
async function clearAll(){
    await fetch("/clear_all",{method:"POST"});
    location.reload();
}