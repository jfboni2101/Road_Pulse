# Creator: Boni Matteo
# University: Università degli Studi di Modena e Reggio Emilia - UNIMORE
# Course: Artificial Intelligence Engineering
# Subject: IOT and 3D Intelligent Systems

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
app.secret_key = app.config["SECRET_KEY"]
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
    count = db.Column(db.Integer, default=1)  # Number of detections
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
    role = db.Column(db.String(20), default='user')  # 'user' oppure 'admin' (Comune)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Calculating the distance between two coordinates (Haversine)
def haversine_distance(lat1, lon1, lat2, lon2):
    # Calculate distance in meters between two GPS coordinates
    r = 6371000  # Earth radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return r * c


# Find existing point within specified radius
def find_nearby_point(lat, lon, radius_meters=20):
    # 1 degree lat ≈ 111km, 1 degree lon ≈ 111km*cos(lat)
    # radius_meters = 20m = 0.00018 approximately
    delta_deg = radius_meters / 111000.0 * 1.5  # Safety margin

    # Query only points in the bounding box (MUCH faster)
    nearby_candidates = Sensorfeed.query.filter(
        Sensorfeed.latitude.between(lat - delta_deg, lat + delta_deg),
        Sensorfeed.longitude.between(lon - delta_deg, lon + delta_deg)
    ).all()

    for point in nearby_candidates:
        distance = haversine_distance(lat, lon, point.latitude, point.longitude)
        if distance <= radius_meters:
            return point

    return None


# State of the road calculation
def calculate_road_status(piezo_raw, x, y, z, baseline=1.0):

    # Calculating Modulus (Fold Independence)
    # We use x and y to ignore acceleration/braking, or all three for total accuracy
    modulo = sqrt(x ** 2 + y ** 2)

    # Calculation of the Delta
    mpu_delta = abs(modulo - baseline) * 100.0

    # Piezo normalization
    piezo_val = (piezo_raw / 1023.0) * 100.0

    # # Thresholds
    piezo_high = 30.0
    piezo_medium = 15.0
    mpu_high = 1400.0
    mpu_medium = 1000.0

    if piezo_val > piezo_high and mpu_delta > mpu_high:
        return "red"
    elif piezo_val > piezo_medium and mpu_delta > mpu_medium:
        return "orange"
    else:
        return "green"


# Calculate reliability based on number of detections
def get_confidence(count):
    if count >= 5:
        return "High"
    elif count >= 2:
        return "Medium"
    else:
        return "Low"


# Login required in order to do everything
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = session.get('user_id')
        user = db.session.get(User, user_id)
        if not user or user.role != 'admin':
            return "Access denied: Only municipalities can perform this operation", 403
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
            session['user_role'] = user.role
            logging.info(f"User Login: {username}")
            return redirect('/')
        else:
            logging.warning(f"Login attempt failed: {username}")
            return render_template('login.html', error="Incorrect credentials")

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
    print("Received:", raw)
    # return "OK", 200

    try:
        # Parsing like lat=44&long=10&dati=0,0
        params = parse_qs(raw)

        api_key = request.headers.get('X-API-KEY')
        if api_key != UPLOAD_SECRET:
            logging.warning(f"Attempted unauthorized access: {request.remote_addr}")
            return "Unauthorized access", 403

        # Retrieve parameters
        lat_list = params.get("lat", [])
        lon_list = params.get("long", [])
        dati_list = params.get("dati", [])

        # Each single data must be complete
        if not (lat_list and lon_list and dati_list):
            return "Incomplete data", 400

        lat = float(lat_list[0])
        lon = float(lon_list[0])
        dati = dati_list[0]

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return "Invalid coordinates", 400

        try:
            piezo_str, ax_str, ay_str, az_str = dati.split(",")
            piezo = float(piezo_str)
            ax_raw = float(ax_str)
            ay_raw = float(ay_str)
            az_raw = float(az_str)
        except ValueError:
            return "Incorrect data format", 400

        # Conversion to G
        x_g = ax_raw / 2048.0
        y_g = ay_raw / 2048.0
        z_g = az_raw / 2048.0

        # Calculate color of the point
        status = calculate_road_status(piezo, x_g, y_g, z_g)

        mpu_val_for_db = abs(sqrt(x_g ** 2 + y_g ** 2) - 1.0) * 100.0

        if status != "green":

            nearby = find_nearby_point(lat, lon, radius_meters=20)

            if nearby:
                # Update existing point
                nearby.count += 1

                nearby.latitude = (nearby.latitude * (nearby.count - 1) + lat) / nearby.count
                nearby.longitude = (nearby.longitude * (nearby.count - 1) + lon) / nearby.count

                nearby.piezo = max(nearby.piezo, piezo)  # Worst case
                nearby.mpu = max(nearby.mpu, mpu_val_for_db)
                if status == "red":
                    nearby.road_status = "red"

                nearby.timestamp = datetime.utcnow()

                logging.info(f"Update point (ID={nearby.id}, count={nearby.count})")
            else:
                # Create new point
                sf = Sensorfeed(lat, lon, piezo, mpu_val_for_db, status)
                db.session.add(sf)
                logging.info(f"New point created: {status}")

            db.session.commit()

        return f"OK - State of the road {status}", 200

    except Exception as e:
        logging.error(f"Upload error: {e}")
        return f"Data parsing error: {e}", 400


# Retrieve critical data recorded in the DB
@app.route('/api/roadpoints', methods=['GET'])
@login_required
def get_road_points():
    # Query the database for all registered points
    # We sort by ID so that the most recent ones are at the top
    # all_points = db.session.execute(db.select(Sensorfeed)).scalars().all()

    # Parametro opzionale: days (default 30)
    days = request.args.get('days', default=30, type=int)

    # Only recent points
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent_points = Sensorfeed.query.all()

    # Format data in a list of JSON dictionaries
    points_list = []
    for point in recent_points:
        age_days = (datetime.utcnow() - point.timestamp).days

        points_list.append({
            'id': point.id,
            'lat': point.latitude,
            'lon': point.longitude,
            'status': point.road_status,
            'count': point.count,
            'confidence': get_confidence(point.count),
            'age_days': age_days,
            'timestamp': point.timestamp.isoformat()
        })

    # Return the list as a JSON response
    logging.info(f"Request roadpoints: {len(points_list)} points sent")
    return jsonify(points_list)


# System statistic
@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    total = Sensorfeed.query.count()
    red = Sensorfeed.query.filter_by(road_status='red').count()
    orange = Sensorfeed.query.filter_by(road_status='orange').count()

    # Estimate mapped km (1 point per 20m on average)
    estimated_km = (total * 20) / 1000

    # Last update
    last_point = Sensorfeed.query.order_by(Sensorfeed.timestamp.desc()).first()
    last_update = last_point.timestamp.isoformat() if last_point else None

    return jsonify({
        'total_points': total,
        'red_count': red,
        'orange_count': orange,
        'estimated_km': round(estimated_km, 1),
        'last_update': last_update
    })


@app.route('/api/delete-point/<int:point_id>', methods=['POST'])
@login_required
@admin_required
def delete_single_point(point_id):
    user = db.session.get(User, session['user_id'])

    point = db.session.get(Sensorfeed, point_id)
    if point:
        db.session.delete(point)
        db.session.commit()
        logging.info(f"ID point {point_id} deleted by admin {user.username}")
        return jsonify({"status": "success", "message": "Point removed"})

    return jsonify({"status": "error", "message": "Point not found"}), 404


# Delete DB point
@app.route('/delete-all', methods=['POST'])
def delete_all():

    api_key = request.headers.get('X-API-KEY')
    if api_key != DELETE_SECRET:
        logging.warning(f"Unauthorized delete attempt: {request.remote_addr}")
        return "Access denied", 403

    count = Sensorfeed.query.count()
    Sensorfeed.query.delete()
    db.session.commit()

    db.session.execute(text("DELETE FROM sqlite_sequence "
                            "WHERE name='sensorfeed';"))
    db.session.commit()

    logging.warning(f"Database cleared: {count} points deleted")
    return "Deleted", 200


# Logout from the website
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# In case of error (incorrect page, etc.)
@app.errorhandler(404)
def page_not_found(error):
    return f"<h1>{error}</h1>", 404


if __name__ == '__main__':
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Create a test user only if it doesn't already exist
        # Create STANDARD USER (B2C)
        if not User.query.filter_by(username="user").first():
            u = User(username="user", role="user")
            u.set_password("user")
            db.session.add(u)
            print(f"Standard user {u.username} created.")

        # 2. Create MUNICIPALITY USER (B2G / Admin)
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="admin")
            admin.set_password("admin")
            db.session.add(admin)
            print(f"Admin user {admin.username} created.")

        db.session.commit()

    logging.info("RoadPulse Server Started")
    app.run(host=app.config.get('FLASK_RUN_HOST', '127.0.0.1'),
            port=app.config.get('FLASK_RUN_PORT', 2101))
