// Inizializzazione mappa centrata su Modena
var map = L.map('map').setView([44.7031, 10.6346], 11.5);

// Layer base OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
}).addTo(map);


var roadLayer = L.layerGroup().addTo(map);


// Funzione per localizzare l'utente
function locateUser() {
    // Controlla se il browser permette la geolocalizzazione
  if (navigator.geolocation) {
      // Chiede all'utente la sua posizione e se può accuisirla ovviamente
    navigator.geolocation.getCurrentPosition(
      function(position) {
        var lat = position.coords.latitude;
        var lon = position.coords.longitude;

        // Centra la mappa sulla posizione dell'utente
        map.setView([lat, lon], 13);

        // Aggiungi un marker per l'utente
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


// Chiamata alla funzione di geolocalizzazione
locateUser();


function toggleLegend() {
    const legend = document.getElementById('map-legend');
    // toggle della classe 'd-none' di Bootstrap (display: none)
    if (legend.classList.contains('d-none')) {
        legend.classList.remove('d-none');
    } else {
        legend.classList.add('d-none');
    }
}


// Funzione globale per l'eliminazione
function deletePoint(pointId) {
    if (confirm("Do you confirm that the repair has been made? The point will be removed from the map.")) {
        fetch(`/api/delete-point/${pointId}`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert("Intervento registrato con successo!");
                    update_road_points(); // Ricarica i punti senza refresh pagina
                    update_stats();       // Aggiorna i contatori
                } else {
                    alert("Errore: " + data.message);
                }
            })
            .catch(err => alert("Errore durante la comunicazione con il server."));
    }
}


function update_stats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(stats => {
            // Inserisce i valori dal JSON agli elementi HTML
            document.getElementById('total-points').innerText = stats.total_points;
            document.getElementById('red-count').innerText = stats.red_count;
            document.getElementById('km-mapped').innerText = stats.estimated_km + " km";
        })
        .catch(err => console.error('Statistics loading error:', err));
}


// caricamento dati DB
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
                    radius: 7, // Leggermente più grande per facilitare il click
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.8
                }).addTo(roadLayer);

                // COSTRUZIONE POPUP DINAMICO
                let popupContent = `
                    <div style="text-align: center;">
                        <b>Status:</b> ${point.status.toUpperCase()}<br>
                        <b>Reliability:</b> ${point.confidence}<br>
                        <small>${new Date(point.timestamp).toLocaleString()}</small>
                    </div>
                `;

                // SE ADMIN, AGGIUNGI TASTO ELIMINA
                if (typeof userRole !== 'undefined' && userRole === 'admin') {
                    popupContent += `
                        <hr>
                        <button onclick="deletePoint(${point.id})" 
                                style="background:#dc3545; color:white; border:none; border-radius:4px; padding:5px 10px; width:100%; cursor:pointer;">
                            Segna come Riparato
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