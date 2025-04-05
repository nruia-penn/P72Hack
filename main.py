from flask import Flask, jsonify
from models import db, TrafficEntry
from sqlalchemy import func
import csv
import os

app = Flask(__name__)
DB_PATH = 'instance/traffic.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///traffic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

PRICING = {
    ('Car', 0): 2.25,
    ('Car', 1): 9,
    ('Buses', 0): 3.6,
    ('Buses', 1): 14.4,
    ('Motorcycles', 0): 1.05,
    ('Motorcycles', 1): 4.5,
    ('Taxi', 0): 0.75,
    ('Taxi', 1): 0.75,
    ('Single Unit Trucks', 0): 3.6,
    ('Single Unit Trucks', 1): 14.4,
    ('Multi Unit Trucks', 0): 5.40,
    ('Multi Unit Trucks', 1): 21.60
}

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

from flask import request, jsonify
from datetime import datetime
from models import db, TrafficEntry

# @app.route('/filter', methods=['GET'])
# def get_filtered_data():
#     # Get query params
#     datetime_start_str = request.args.get('datetime_start')
#     datetime_end_str = request.args.get('datetime_end')
#     detection_group = request.args.get('detection_group')
#     vehicle_class = request.args.get('vehicle_class')

#     # Validate required fields
#     if not datetime_start_str or not datetime_end_str:
#         return jsonify({'error': 'datetime_start and datetime_end are required.'}), 400

#     try:
#         # Convert to datetime objects for comparison
#         datetime_start = datetime.strptime(datetime_start_str, "%Y-%m-%d %H:%M:%S")
#         datetime_end = datetime.strptime(datetime_end_str, "%Y-%m-%d %H:%M:%S")
#     except ValueError:
#         return jsonify({'error': 'Datetime must be in format YYYY-MM-DD HH:MM:SS'}), 400

#     # Start base query
#     query = TrafficEntry.query.filter(
#         TrafficEntry.datetime >= datetime_start_str,
#         TrafficEntry.datetime <= datetime_end_str
#     )

#     # Optional filters
#     if detection_group:
#         query = query.filter(TrafficEntry.detection_group == detection_group)

#     if vehicle_class:
#         query = query.filter(TrafficEntry.vehicle_class == vehicle_class)

#     # Execute and return
#     results = query.all()
#     ## total number per vehicle class
#     ## total number of vehicles
#     ## total price per vehicle class
#     ## total price


#     return jsonify([{
#         'id': e.id,
#         'datetime': e.datetime,
#         'is_peak': e.is_peak,
#         'vehicle_class': e.vehicle_class,
#         'detection_group': e.detection_group,
#         'crz_entries': e.crz_entries,
#         'excluded_roadway_entries': e.excluded_roadway_entries
#     } for e in results])


@app.route('/filter', methods=['GET'])
def get_filtered_data():
    datetime_start = request.args.get('datetime_start')
    datetime_end = request.args.get('datetime_end')
    detection_group = request.args.get('detection_group')
    vehicle_class_filter = request.args.get('vehicle_class')

    if not datetime_start or not datetime_end:
        return jsonify({'error': 'datetime_start and datetime_end are required'}), 400

    # Base query
    query = db.session.query(
        TrafficEntry.vehicle_class,
        TrafficEntry.is_peak,
        func.sum(TrafficEntry.crz_entries)
    ).filter(
        TrafficEntry.datetime >= datetime_start,
        TrafficEntry.datetime <= datetime_end
    )

    if detection_group:
        query = query.filter(TrafficEntry.detection_group == detection_group)

    if vehicle_class_filter:
        query = query.filter(TrafficEntry.vehicle_class == vehicle_class_filter)

    query = query.group_by(TrafficEntry.vehicle_class, TrafficEntry.is_peak)

    results = query.all()

    vehicle_counts = {}
    revenue_per_class = {}
    total_vehicles = 0
    total_revenue = 0

    for vehicle_class, is_peak, entry_sum in results:
        price_per = PRICING.get((vehicle_class, is_peak), 0)
        revenue = entry_sum * price_per

        # Update per-class stats
        vehicle_counts[vehicle_class] = vehicle_counts.get(vehicle_class, 0) + entry_sum
        revenue_per_class[vehicle_class] = revenue_per_class.get(vehicle_class, 0) + revenue

        total_vehicles += entry_sum
        total_revenue += revenue

    return jsonify({
        "vehicle_counts": vehicle_counts,
        "total_vehicles": total_vehicles,
        "revenue_per_class": revenue_per_class,
        "total_revenue": total_revenue
    })
    


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(DB_PATH):
            print("Database not found. Creating and loading data...")
            db.create_all()
            load_data_from_csv('cleaned_data.csv')
        else:
            print("Database exists. Skipping CSV import.")
    app.run(debug=True)
