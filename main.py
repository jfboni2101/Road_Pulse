from flask import Flask
from config import Config
from flask import render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from flask_openapi3 import Info
from flask_openapi3 import OpenAPI


appname = "IOT - sample14"

info = Info(title=appname, version="1.0.0")
app = OpenAPI(appname, info=info)
myconfig = Config
app.config.from_object(myconfig)

db = SQLAlchemy()

# myset=[]

class Sensorfeed(db.Model):
    id = db.Column('value_id', db.Integer, primary_key = True)
    value = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False,  default=datetime.utcnow)

    def __init__(self, value):
        self.value = value

@app.errorhandler(404)
def page_not_found(error):
    return 'Ops, I think you are looking for the wrong resource', 404


@app.route('/')
def testoHTML():
    if request.accept_mimetypes['application/json']:
        return jsonify({'text': 'I Love IoT'})
    else:
        return '<h1>I love IoT</h1>'


@app.route('/list', methods=['GET'])
def printList():
    myres = db.select(Sensorfeed).order_by(Sensorfeed.id.desc()).limit(2)
    filteredSet = db.session.execute(myres).scalars()

    return render_template('lista3.html', lista=filteredSet)
    #return render_template('lista2.html', lista=myset)


@app.route('/addToList/<val>', methods=['POST'])
def addToList(val):
    # myset.append(name)
    # return str(len(myset))

    sf = Sensorfeed(val)
    db.session.add(sf)
    db.session.commit()
    return str(sf.id)

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