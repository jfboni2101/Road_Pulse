from flask import Flask
from flask import session, redirect, url_for
from config import Config
from flask import render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
from urllib.parse import parse_qs
from flask_openapi3 import Info
from flask_openapi3 import OpenAPI
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


# Caratteristiche programma
appname = "RoadPulse"
info = Info(title=appname, version="1.0.0")
app = OpenAPI(appname, info=info)
myconfig = Config
app.config.from_object(myconfig)
app.secret_key = "passwordDiProvaPerVedereSeFunzionaTutto"


# Creazione DB
db = SQLAlchemy()


# Tabella dati sensore DB
class Sensorfeed(db.Model):
    id = db.Column('value_id', db.Integer, primary_key=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    piezo = db.Column(db.Float)
    mpu = db.Column(db.Float)
    road_status = db.Column(db.String(10))
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __init__(self, lat, lon, piezo, mpu, status):
        self.latitude = lat
        self.longitude = lon
        self.piezo = piezo
        self.mpu = mpu
        self.road_status = status


# Tabella utenti DB
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Calcolo stato della strada
def calculate_road_status(vib_val, az_val, az_baseline=10.0):
    delta_az = abs(az_val - az_baseline)

    # Soglie delta
    piezo_high = 60
    piezo_medium = 30
    mpu_high = 3   # delta sopra 3 considerato grave
    mpu_medium = 1.5

    if vib_val > piezo_high and delta_az > mpu_high:
        return "rossa"
    elif vib_val > piezo_medium and delta_az > mpu_medium:
        return "gialla"
    else:
        return "verde"


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect('/')
        else:
            return render_template('login.html', error="Credenziali errate")

    return render_template('login.html')


@app.route('/')
@login_required
def testo_html():
    # if request.accept_mimetypes['application/json']:
    #     return jsonify({'text': 'I Love IoT'})
    # else:
    #     return '<h1>I love IoT</h1>'

    return render_template('index.html')


"""
@app.route('/list', methods=['GET'])
def print_list():
    myres = db.select(Sensorfeed).order_by(Sensorfeed.id.desc()).limit(2)
    filteredSet = db.session.execute(myres).scalars()

    return render_template('lista3.html', lista=filteredSet)
    # return render_template('lista2.html', lista=myset)
"""


# Caricamento dati critici della strada
@app.route('/upload', methods=['POST'])
def upload_data():
    raw = request.get_data(as_text=True)
    print("Ricevuto:", raw)
    # return "OK", 200

    try:
        # Parsing tipo lat=44&long=10&dati=0,0
        params = parse_qs(raw)

        lat = float(params.get("lat", [0])[0])
        lon = float(params.get("long", [0])[0])
        dati = params.get("dati", ["0,0"])[0]

        if lat == 0 or lon == 0 or dati == 0:
            return "Dati incompleti, niente aggiunto al DB", 400

        try:
            piezo_str, mpu_str = dati.split(",")
        except ValueError:
            return "Formato dati errato", 400

        piezo = float(piezo_str)
        mpu = float(mpu_str)

        # Calcola colore strada
        status = calculate_road_status(piezo, mpu)

        if status != "verde":
            # Controlla duplicato
            existing = Sensorfeed.query.filter_by(
                latitude=lat, longitude=lon
            ).first()

            if existing:
                # Salva nel DB
                existing.road_status = status
                existing.timestamp = datetime.utcnow()
                existing.piezo = piezo
                existing.mpu = mpu
            else:
                sf = Sensorfeed(lat, lon, piezo, mpu, status)
                db.session.add(sf)

            db.session.commit()

        return f"OK - Stato strada {status}", 200

    except Exception as e:
        print("Errore parsing dati: ", e)
        return f"Errore parsing dati: {e}", 400


# Retrieve dei dati critici registrati nel DB
@app.route('/api/roadpoints', methods=['GET'])
@login_required
def get_road_points():
    # 1. Interroga il database per tutti i punti registrati
    # Ordiniamo per ID in modo che i più recenti siano in cima (opzionale)
    all_points = db.session.execute(db.select(Sensorfeed)).scalars().all()

    # 2. Formatta i dati in una lista di dizionari JSON
    points_list = []
    for point in all_points:
        points_list.append({
            'lat': point.latitude,
            'lon': point.longitude,
            'status': point.road_status,
            # Includiamo il timestamp per i popup, convertito in ISO stringa
            'timestamp': point.timestamp.isoformat()
        })

    # 3. Restituisci la lista come risposta JSON
    return jsonify(points_list)


"""
@app.route('/add-to-list/<val>', methods=['POST'])
def add_to_list(val):
    myset.append(name)
    return str(len(myset))

    sf = Sensorfeed(val)
    db.session.add(sf)
    db.session.commit()
    return str(sf.id)
"""


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# Cancellazione punti del DB
@app.route('/delete-all', methods=['POST'])
def delete_all():
    Sensorfeed.query.delete()
    db.session.commit()

    db.session.execute(text("DELETE FROM sqlite_sequence WHERE name='sensorfeed';"))
    db.session.commit()

    return "Deleted", 200


# In caso di errore (pagina errata, ecc.)
@app.errorhandler(404)
def page_not_found(error):
    return f"<h1>{error}</h1>", 404


if __name__ == '__main__':
    db.init_app(app)
    if True:  # first time (?)
        with app.app_context():
            db.create_all()
            # Crea un utente di prova solo se non esiste già
            if not User.query.filter_by(username="Matteo").first():
                u = User(username="Matteo")
                u.set_password("Boni")
                db.session.add(u)
                db.session.commit()
                print(f"Utente {u.username} creato con ID {u.id}")

    app.run(host=app.config.get('FLASK_RUN_HOST', '0.0.0.0'),
            port=app.config.get('FLASK_RUN_PORT', 2101))
