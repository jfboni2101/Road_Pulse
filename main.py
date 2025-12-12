from flask import Flask
from config import Config
from flask import render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from urllib.parse import parse_qs
from flask_openapi3 import Info
from flask_openapi3 import OpenAPI


appname = "RoadPulse"

info = Info(title=appname, version="1.0.0")
app = OpenAPI(appname, info=info)
myconfig = Config
app.config.from_object(myconfig)

db = SQLAlchemy()

# myset=[]

class Sensorfeed(db.Model):
    id = db.Column('value_id', db.Integer, primary_key = True)
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

def calculate_road_status(vib_val, az_val, az_baseline=10.0):
    delta_az = abs(az_val - az_baseline)

    # soglie delta
    PIEZO_HIGH = 60
    PIEZO_MEDIUM = 30
    MPU_HIGH = 3   # delta sopra 3 considerato grave
    MPU_MEDIUM = 1.5

    if vib_val > PIEZO_HIGH and delta_az > MPU_HIGH:
        return "rossa"
    elif vib_val > PIEZO_MEDIUM or delta_az > MPU_MEDIUM:
        return "gialla"
    else:
        return "verde"


@app.errorhandler(404)
def page_not_found(error):
    return '<h1>Ops, I think you are looking for the wrong resource</h1>', 404

@app.route('/')
def testoHTML():
    # if request.accept_mimetypes['application/json']:
    #     return jsonify({'text': 'I Love IoT'})
    # else:
    #     return '<h1>I love IoT</h1>'

    return render_template('index.html')


@app.route('/list', methods=['GET'])
def printList():
    myres = db.select(Sensorfeed).order_by(Sensorfeed.id.desc()).limit(2)
    filteredSet = db.session.execute(myres).scalars()

    return render_template('lista3.html', lista=filteredSet)
    #return render_template('lista2.html', lista=myset)

@app.route('/upload', methods=['POST'])
def upload_data():
    raw = request.get_data(as_text=True)
    print("Ricevuto:", raw)
    return "OK", 200

    """
    try:
        # Parsing tipo lat=44&long=10&dati=0,0
        params = parse_qs(raw)

        lat = float(params.get("lat", [0])[0])
        lon = float(params.get("long", [0])[0])
        dati = params.get("dati", ["0,0"])[0]

        if lat in (None, '') or lon in (None, '') or dati in (None, ''):
            return "Dati incompleti, niente aggiunto al DB", 401

        piezo_str, mpu_str = dati.split(",")
        piezo = float(piezo_str)
        mpu = float(mpu_str)

        # Calcola colore strada
        status = calculate_road_status(piezo, mpu)

        # Salva nel DB
        sf = Sensorfeed(lat, lon, piezo, mpu, status)
        db.session.add(sf)
        db.session.commit()

        return f"OK - Stato strada {status}", 200

    except Exception as e:
        print("Errore parsing dati: ", e)
        return f"Errore parsing dati: {e}", 400
    """
@app.route('/api/roadpoints', methods=['GET'])
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

# @app.route('/addToList/<val>', methods=['POST'])
# def addToList(val):
    # myset.append(name)
    # return str(len(myset))

    # sf = Sensorfeed(val)
    # db.session.add(sf)
    # db.session.commit()
    # return str(sf.id)

@app.route('/deleteAll', methods=['POST'])
def deleteAll():
    Sensorfeed.query.delete()
    db.session.commit()

    return "Deleted", 200


if __name__ == '__main__':
    db.init_app(app)
    if True:  # first time (?)
        with app.app_context():
            db.create_all()

    app.run(host=app.config.get('FLASK_RUN_HOST', '0.0.0.0'),
            port=app.config.get('FLASK_RUN_PORT', 211))