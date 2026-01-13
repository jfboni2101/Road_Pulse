from flask import session, redirect, url_for, render_template, request, jsonify, Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
from urllib.parse import parse_qs
from flask_openapi3 import Info, OpenAPI
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from math import radians, sin, cos, sqrt, atan2
import logging

# Setup logging
logging.basicConfig(
    filename='roadpulse.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# Program features
appname = "RoadPulse"
info = Info(title=appname, version="1.0.0")
app = OpenAPI(appname, info=info)
myconfig = Config
app.config.from_object(myconfig)
app.secret_key = "passwordDiProvaPerVedereSeFunzionaTutto"
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
UPLOAD_SECRET = app.config["UPLOAD_SECRET"]
DELETE_SECRET = app.config["DELETE_SECRET"]


# Creation DB
db = SQLAlchemy()


# DB Sensor Data Table
class Sensorfeed(db.Model):
    id = db.Column('value_id', db.Integer, primary_key=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    piezo = db.Column(db.Float)
    mpu = db.Column(db.Float)
    road_status = db.Column(db.String(10))
    count = db.Column(db.Integer, default=1)  # Numero rilevamenti
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __init__(self, lat, lon, piezo, mpu, status):
        self.latitude = lat
        self.longitude = lon
        self.piezo = piezo
        self.mpu = mpu
        self.road_status = status
        self.count = 1


# DB User Table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Calculating the distance between two coordinates (Haversine)
def haversine_distance(lat1, lon1, lat2, lon2):
    # Calculate distance in meters between two GPS coordinates
    R = 6371000  # Earth radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


# Find existing point within specified radius
def find_nearby_point(lat, lon, radius_meters=20):
    # Search for an existing point within X meters of the given coordinates
    all_points = Sensorfeed.query.all()

    for point in all_points:
        distance = haversine_distance(lat, lon, point.latitude, point.longitude)
        if distance <= radius_meters:
            return point

    return None


# State of the road calculation
def calculate_road_status(vib_val, az_val, az_baseline=10.0):
    delta_az = abs(az_val - az_baseline)

    # Soglie delta
    piezo_high = 60.0
    piezo_medium = 30.0
    mpu_high = 3.0
    mpu_medium = 1.5

    if vib_val > piezo_high and delta_az > mpu_high:
        return "rossa"
    elif vib_val > piezo_medium and delta_az > mpu_medium:
        return "gialla"
    else:
        return "verde"


# Calculate reliability based on number of detections
def get_confidence(count):
    if count >= 5:
        return "Alta"
    elif count >= 2:
        return "Media"
    else:
        return "Bassa"

# Login required in order to do everything
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            logging.info(f"Login utente: {username}")
            return redirect('/')
        else:
            logging.warning(f"Tentativo login fallito: {username}")
            return render_template('login.html', error="Credenziali errate")

    return render_template('login.html')

# Homepage
@app.route('/')
@login_required
def testo_html():
    return render_template('index.html')


# Loading critical road data
@app.route('/upload', methods=['POST'])
def upload_data():
    raw = request.get_data(as_text=True)
    print("Ricevuto:", raw)
    # return "OK", 200

    try:
        # Parsing like lat=44&long=10&dati=0,0
        params = parse_qs(raw)

        api_key = request.headers.get('X-API-KEY')
        if api_key != UPLOAD_SECRET:
            logging.warning(f"Tentativo accesso non autorizzato: {request.remote_addr}")
            return "Accesso negato", 403

        # Retrieve parameters
        lat_list = params.get("lat", [])
        lon_list = params.get("long", [])
        dati_list = params.get("dati", [])

        # Each single data must be complete
        if not (lat_list and lon_list and dati_list):
            return "Dati incompleti", 400

        lat = float(lat_list[0])
        lon = float(lon_list[0])
        dati = dati_list[0]

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return "Coordinate non valide", 400

        try:
            piezo_str, mpu_str = dati.split(",")
        except ValueError:
            return "Formato dati errato", 400

        piezo = float(piezo_str)
        mpu = float(mpu_str)

        # Calculate color of the point
        status = calculate_road_status(piezo, mpu)
        logging.info(f"Rilevamento: lat={lat:.6f}, lon={lon:.6f}, "
                     f"piezo={piezo}, mpu={mpu}, status={status}")

        if status != "verde":

            nearby = find_nearby_point(lat, lon, radius_meters=20)

            if nearby:
                # Update wxisting point
                nearby.count += 1
                nearby.piezo = max(nearby.piezo, piezo)  # Worst case
                nearby.mpu = max(nearby.mpu, mpu)
                nearby.road_status = calculate_road_status(nearby.piezo, nearby.mpu)
                nearby.timestamp = datetime.utcnow()

                logging.info(f"Punto aggiornato (ID={nearby.id}, count={nearby.count})")
            else:
                # Create new point
                sf = Sensorfeed(lat, lon, piezo, mpu, status)
                db.session.add(sf)
                logging.info(f"Nuovo punto creato: {status}")

            db.session.commit()

            # Controlla duplicato
            # existing = Sensorfeed.query.filter_by(
            #     latitude=lat, longitude=lon
            # ).first()

            # if existing:
                # Salva nel DB
                # existing.road_status = status
                # existing.timestamp = datetime.utcnow()
                # existing.piezo = piezo
                # existing.mpu = mpu
            # else:
                # sf = Sensorfeed(lat, lon, piezo, mpu, status)
                # db.session.add(sf)

            # db.session.commit()

        return f"OK - Stato strada {status}", 200

    except Exception as e:
        logging.error(f"Errore upload: {e}")
        return f"Errore parsing dati: {e}", 400


# Retrieve critical data recorded in the DB
@app.route('/api/roadpoints', methods=['GET'])
@login_required
def get_road_points():
    # Interroga il database per tutti i punti registrati
    # Ordiniamo per ID in modo che i più recenti siano in cima (opzionale)
    # all_points = db.session.execute(db.select(Sensorfeed)).scalars().all()

    # Parametro opzionale: days (default 30)
    days = request.args.get('days', default=30, type=int)

    # Only recent points
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent_points = Sensorfeed.query.filter(
        Sensorfeed.timestamp >= cutoff
    ).all()

    # Format data in a list of JSON dictionaries
    points_list = []
    for point in recent_points:
        age_days = (datetime.utcnow() - point.timestamp).days

        points_list.append({
            'lat': point.latitude,
            'lon': point.longitude,
            'status': point.road_status,
            'count': point.count,
            'confidence': get_confidence(point.count),
            'age_days': age_days,
            'timestamp': point.timestamp.isoformat()
        })

    # Return the list as a JSON response
    logging.info(f"Richiesta roadpoints: {len(points_list)} punti inviati")
    return jsonify(points_list)


# API: System statistic
@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    total = Sensorfeed.query.count()
    red = Sensorfeed.query.filter_by(road_status='rossa').count()
    yellow = Sensorfeed.query.filter_by(road_status='gialla').count()

    # Estimate mapped km (1 point per 20m on average)
    estimated_km = (total * 20) / 1000

    # Last update
    last_point = Sensorfeed.query.order_by(Sensorfeed.timestamp.desc()).first()
    last_update = last_point.timestamp.isoformat() if last_point else None

    return jsonify({
        'total_points': total,
        'red_count': red,
        'yellow_count': yellow,
        'estimated_km': round(estimated_km, 1),
        'last_update': last_update
    })


# Logout from the website
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# Delete DB point
@app.route('/delete-all', methods=['POST'])
def delete_all():

    api_key = request.headers.get('X-API-KEY')
    if api_key != UPLOAD_SECRET:
        logging.warning(f"Tentativo delete non autorizzato: {request.remote_addr}")
        return "Accesso negato", 403

    count = Sensorfeed.query.count()
    Sensorfeed.query.delete()
    db.session.commit()

    db.session.execute(text("DELETE FROM sqlite_sequence "
                            "WHERE name='sensorfeed';"))
    db.session.commit()

    logging.warning(f"Database svuotato: {count} punti eliminati")
    return "Deleted", 200


# In case of error (incorrect page, etc.)
@app.errorhandler(404)
def page_not_found(error):
    return f"<h1>{error}</h1>", 404


if __name__ == '__main__':
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Crea un utente di prova solo se non esiste già
        if not User.query.filter_by(username="Matteo").first():
            u = User(username="Matteo")
            u.set_password("Boni")
            db.session.add(u)
            db.session.commit()
            print(f"Utente {u.username} creato con ID {u.id}")

    logging.info("Server RoadPulse avviato")
    app.run(host=app.config.get('FLASK_RUN_HOST', '127.0.0.1'),
            port=app.config.get('FLASK_RUN_PORT', 2101))
