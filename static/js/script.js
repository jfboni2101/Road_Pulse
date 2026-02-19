// Initialization of a map centered on Modena
var map = L.map('map').setView([44.6471, 10.9252], 11.5);

// OpenStreetMap Base Layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
}).addTo(map);


var roadLayer = L.layerGroup().addTo(map);


// Function to locate the user
function locateUser() {
    // Check if the browser allows geolocation
  if (navigator.geolocation) {
      // Asks the user for his location and whether he can acquire it of course
    navigator.geolocation.getCurrentPosition(
      function(position) {
        var lat = position.coords.latitude;
        var lon = position.coords.longitude;

        // Center the map on the user's location
        map.setView([lat, lon], 13);

        // Add a marker for the user
        L.marker([lat, lon]).addTo(map)
          .bindPopup("You are here!")
          .openPopup();
      },
      function(err) {
        console.warn("Geolocation error.", err);
      }
    );
  } else {
    console.warn("Geolocation not supported by the browser.");
  }
}


// Call the geolocation function
locateUser();


function toggleLegend() {
    const legend = document.getElementById('map-legend');
    // Bootstrap 'd-none' class toggle (display: none)
    if (legend.classList.contains('d-none')) {
        legend.classList.remove('d-none');
    } else {
        legend.classList.add('d-none');
    }
}


// Global function for deletion
function deletePoint(pointId) {
    if (confirm("Do you confirm that the repair has been made? The point will be removed from the map.")) {
        fetch(`/api/delete-point/${pointId}`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert("Intervention recorded successfully!!");
                    update_road_points(); // Reload points without page refresh
                    update_stats();       // Update counters
                } else {
                    alert("Error: " + data.message);
                }
            })
            .catch(err => alert("Error communicating with the server."));
    }
}


function update_stats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(stats => {
            // Inserts values from JSON into HTML elements
            document.getElementById('total-points').innerText = stats.total_points;
            document.getElementById('red-count').innerText = stats.red_count;
            document.getElementById('km-mapped').innerText = stats.estimated_km + " km";
        })
        .catch(err => console.error('Statistics loading error:', err));
}


// DB data loading
function update_road_points() {
    fetch('/api/roadpoints')
        .then(response => response.json())
        .then(data => {
            roadLayer.clearLayers();
            data.forEach(point => {
                let color;
                switch(point.status) {
                    case "red": color = 'red'; break;
                    case "orange": color = 'orange'; break;
                    default: color = 'green';
                }

                let marker = L.circleMarker([point.lat, point.lon], {
                    radius: 7, // Slightly larger to make clicking easier
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.8
                }).addTo(roadLayer);

                // Dynamic popup construction
                let popupContent = `
                    <div style="text-align: center;">
                        <b>Status:</b> ${point.status.toUpperCase()}<br>
                        <b>Reliability:</b> ${point.confidence}<br>
                        <small>${new Date(point.timestamp).toLocaleDateString()}</small>
                    </div>
                `;

                // If Admin, add delete button
                if (typeof userRole !== 'undefined' && userRole === 'admin') {
                    popupContent += `
                        <hr>
                        <button onclick="deletePoint(${point.id})" 
                                style="background:#dc3545; color:white; border:none; border-radius:4px; padding:5px 10px; width:100%; cursor:pointer;">
                            Mark as Repaired
                        </button>
                    `;
                }

                marker.bindPopup(popupContent);
            });
        })
        .catch(err => console.error('Point loading error:', err));
}


update_road_points();
update_stats();


setInterval(update_road_points, 600000);