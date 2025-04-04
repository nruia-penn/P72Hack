from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class TrafficEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # From "Index"
    datetime = db.Column(db.String(100))
    time_period = db.Column(db.String(50))
    vehicle_class = db.Column(db.String(50))
    detection_group = db.Column(db.String(50))
    detection_region = db.Column(db.String(50))
    crz_entries = db.Column(db.Integer)
    excluded_roadway_entries = db.Column(db.Integer)
