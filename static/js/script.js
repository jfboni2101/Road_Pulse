// Inizializzazione mappa centrata su Modena
var map = L.map('map').setView([44.7031, 10.6346], 11.5);

// Layer base OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
}).addTo(map);

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
        console.warn("Errore geolocalizzazione, si resta centrati su Modena:", err);
      }
    );
  } else {
    console.warn("Geolocalizzazione non supportata dal browser.");
  }
}

// Chiamata alla funzione di geolocalizzazione
locateUser();


// Caricamento strade Reggio Emilia
// fetch('https://geoserver.comune.re.it/geoserver/geo_re/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=geo_re:SIT_ARCHISTRADE&outputFormat=application/json')
  // .then(response => response.json())
  // .then(data => {
    // L.geoJSON(data, {
      // style: { color: 'green', weight: 3 }
    // }).addTo(map);
  // })
  // .catch(err => console.error('Errore caricamento strade:', err));


var roadLayer = L.layerGroup().addTo(map);


// caricamento dati DB
function update_road_points() {
    fetch('/api/roadpoints')
        .then(response => response.json())
        .then(data => {
            roadLayer.clearLayers(); // rimuove i marker precedenti
            data.forEach(point => {
                let color;
                switch(point.status) {
                    case "rossa": color = 'red'; break;
                    case "gialla": color = 'orange'; break;
                    default: color = 'green';
                }
                let marker = L.circleMarker([point.lat, point.lon], {
                    radius: 5,
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.7
                }).addTo(roadLayer);
                marker.bindPopup(`Stato strada: ${point.status}<br>Timestamp: ${new Date(point.timestamp).toLocaleString()}`);
            });
        })
        .catch(err => console.error('Errore caricamento punti dal DB:', err));
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
        .catch(err => console.error('Errore caricamento statistiche:', err));
}

update_road_points();
update_stats();

setInterval(update_road_points, 600000);