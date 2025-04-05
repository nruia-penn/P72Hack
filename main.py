from flask import Flask, jsonify
from models import db, TrafficEntry
import csv
import os

app = Flask(__name__)
DB_PATH = 'instance/traffic.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///traffic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def load_data_from_csv(filepath):
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            entry = TrafficEntry(
                id=int(row['Index']),
                datetime=row['Datetime'],
                is_peak=row['Is Peak'],
                vehicle_class=row['Vehicle Class'],
                detection_group=row['Detection Group'],
                crz_entries=int(row['CRZ Entries']),
                excluded_roadway_entries=int(row['Excluded Roadway Entries'])
            )
            db.session.add(entry)
        db.session.commit()
        print("CSV data loaded into database.")

@app.route('/data', methods=['GET'])
def get_traffic_data():
    entries = TrafficEntry.query.limit(12).all()
    return jsonify([{
        'id': e.id,
        'datetime': e.datetime,
        'is_peak': e.is_peak,
        'vehicle_class': e.vehicle_class,
        'detection_group': e.detection_group,
        'crz_entries': e.crz_entries,
        'excluded_roadway_entries': e.excluded_roadway_entries
    } for e in entries])

if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(DB_PATH):
            print("🔧 Database not found. Creating and loading data...")
            db.create_all()
            load_data_from_csv('cleaned_data.csv')
        else:
            print("Database exists. Skipping CSV import.")
    app.run(debug=True)
