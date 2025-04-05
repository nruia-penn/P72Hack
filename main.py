from flask import Flask, jsonify, request
from models import db, TrafficEntry
from sqlalchemy import func
from datetime import datetime, timedelta
from collections import defaultdict
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
        TrafficEntry.datetime < datetime_end
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



# Mapping interval keys to number of 10-min blocks and animation duration in seconds
INTERVAL_CONFIG = {
    "10min":   {"blocks": 1, "duration": 3},
    "30min":   {"blocks": 3, "duration": 6},
    "1hr":     {"blocks": 6, "duration": 12},
    "3hr":     {"blocks": 18, "duration": 18},
    "6hr":     {"blocks": 36, "duration": 18},
    "1day":    {"blocks": 144, "duration": 20},
    "1week":   {"blocks": 1008, "duration": 30},
    "2week":   {"blocks": 2016, "duration": 60},
    "1month":  {"blocks": 4320, "duration": 120},
    "3month":  {"blocks": 12960, "duration": 180},
}


# @app.route('/realtime_series', methods=['GET'])
# def realtime_series():
#     # Parse parameters
#     interval_key = request.args.get("interval", "1hr")
#     start_str = request.args.get("datetime_start")
#     if not start_str or interval_key not in INTERVAL_CONFIG:
#         return jsonify({"error": "Missing or invalid datetime_start or interval"}), 400

#     try:
#         start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
#     except ValueError:
#         return jsonify({"error": "datetime_start must be in format YYYY-MM-DD HH:MM:SS"}), 400

#     config = INTERVAL_CONFIG[interval_key]
#     num_blocks = config["blocks"]
#     num_frames = config["duration"]  # Total number of frames in the animation
#     block_duration = timedelta(minutes=10)  # Each raw block lasts 10 minutes
#     interval_duration = block_duration * num_blocks  # Total real-time duration covered by raw data
#     end_time = start_time + interval_duration
#     print("end time is")
#     print(end_time)
#     print(start_time)

#     # Frame duration as a timedelta
#     frame_duration = timedelta(seconds=interval_duration.total_seconds() / num_frames)

#     # Step 1: Query all 10-min blocks in the range.
#     # We assume TrafficEntry.datetime is a datetime column.
#     rows = db.session.query(
#         TrafficEntry.vehicle_class,
#         TrafficEntry.is_peak,
#         TrafficEntry.datetime,
#         TrafficEntry.detection_group,
#         func.sum(TrafficEntry.crz_entries).label("vehicle_count")
#     ).filter(
#         TrafficEntry.datetime >= start_time,
#         TrafficEntry.datetime < end_time
#     ).group_by(
#         TrafficEntry.vehicle_class,
#         TrafficEntry.is_peak,
#         TrafficEntry.datetime,
#         TrafficEntry.detection_group
#     ).all()

#     # Step 2: Build a mapping from block start time to its data, organized by detection group.
#     # We store keys as datetime objects.
#     block_map = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"vehicles": 0, "revenue": 0})))
#     # Also keep a sorted list of block start times.
#     block_times = set()
#     for vclass, is_peak, dt, detection_group, count in rows:
#         price = PRICING.get((vclass, is_peak), 0)
#         block_map[dt][detection_group][vclass]["vehicles"] += count
#         block_map[dt][detection_group][vclass]["revenue"] += count * price
#         block_times.add(dt)

#     # Step 3: Prepare cumulative trackers per location.
#     cumulative = defaultdict(lambda: defaultdict(lambda: {"vehicles": 0, "revenue": 0}))
#     cumulative_total = defaultdict(lambda: {"vehicles": 0, "revenue": 0})
#     print(block_times)
#     print("done printing block times!!!")
#     frames = []

#     # For each frame, compute its time window and sum fractional contributions from overlapping 10-min blocks.
#     for i in range(num_frames):
#         frame_start = start_time + i * frame_duration
#         frame_end = frame_start + frame_duration

#         # Initialize frame data structure.
#         frame_data = {
#             "timestamp": frame_start.strftime("%Y-%m-%d %H:%M:%S"),
#             "scale": 1,
#             "locations": {}  # detection_group -> stats
#         }

#         # For each block that might overlap with this frame:

#         for btime in block_times:
#             if isinstance(btime, str):
#               btime = datetime.strptime(btime, "%Y-%m-%d %H:%M:%S")
#             block_start = btime
#             block_end = btime + block_duration

#             # Compute the overlap between the block and the frame.
#             latest_start = max(frame_start, block_start)
#             earliest_end = min(frame_end, block_end)
#             overlap = (earliest_end - latest_start).total_seconds()

#             print("block_map keys:", list(block_map.keys())[:5])
#             print("frame_start:", frame_start, "frame_end:", frame_end)
#             print("block_start:", block_start, "block_end:", block_end)
#             print("overlap:", overlap)

#             if overlap <= 0:
#                 continue  # No overlap

#             fraction = overlap / block_duration.total_seconds()  # fraction of block that falls in this frame

#             # Add fractional data from this block.
#             for location, classes in block_map[btime].items():
#                 # Ensure location exists in frame data.
#                 if location not in frame_data["locations"]:
#                     frame_data["locations"][location] = {
#                         "current": {
#                             "total_vehicles": 0,
#                             "total_revenue": 0,
#                             "by_class": {}
#                         },
#                         # For cumulative, we use the value so far
#                         "cumulative": {
#                             "vehicles": cumulative_total[location]["vehicles"],
#                             "revenue": cumulative_total[location]["revenue"],
#                             "by_class": dict(cumulative[location])
#                         }
#                     }
#                 # Process each vehicle class in the block for this location.
#                 for vclass, data in classes.items():
#                     vehicles_contrib = data["vehicles"] * fraction
#                     revenue_contrib = data["revenue"] * fraction

#                     # Update current frame stats.
#                     loc_current = frame_data["locations"][location]["current"]
#                     loc_current["total_vehicles"] += vehicles_contrib
#                     loc_current["total_revenue"] += revenue_contrib
#                     if vclass not in loc_current["by_class"]:
#                         loc_current["by_class"][vclass] = {"vehicles": 0, "revenue": 0}
#                     loc_current["by_class"][vclass]["vehicles"] += vehicles_contrib
#                     loc_current["by_class"][vclass]["revenue"] += revenue_contrib

#                     # Update cumulative trackers.
#                     cumulative[location][vclass]["vehicles"] += vehicles_contrib
#                     cumulative[location][vclass]["revenue"] += revenue_contrib
#                     cumulative_total[location]["vehicles"] += vehicles_contrib
#                     cumulative_total[location]["revenue"] += revenue_contrib

#         # After processing all blocks, update the cumulative values in each location for this frame.
#         for location in frame_data["locations"]:
#             frame_data["locations"][location]["cumulative"] = {
#                 "vehicles": round(cumulative_total[location]["vehicles"], 2),
#                 "revenue": round(cumulative_total[location]["revenue"], 2),
#                 "by_class": {vclass: {"vehicles": round(vals["vehicles"], 2), 
#                                         "revenue": round(vals["revenue"], 2)}
#                              for vclass, vals in cumulative[location].items()}
#             }
#             # Also round the current frame's values.
#             curr = frame_data["locations"][location]["current"]
#             curr["total_vehicles"] = round(curr["total_vehicles"], 2)
#             curr["total_revenue"] = round(curr["total_revenue"], 2)
#             for vclass in curr["by_class"]:
#                 curr["by_class"][vclass]["vehicles"] = round(curr["by_class"][vclass]["vehicles"], 2)
#                 curr["by_class"][vclass]["revenue"] = round(curr["by_class"][vclass]["revenue"], 2)

#         frames.append(frame_data)

#     return jsonify(frames)


@app.route('/realtime_series', methods=['GET'])
def realtime_series():
    interval_key = request.args.get("interval", "1hr")
    start_str = request.args.get("datetime_start")

    if not start_str or interval_key not in INTERVAL_CONFIG:
        return jsonify({"error": "Missing or invalid datetime_start or interval"}), 400

    try:
        start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"error": "datetime_start must be in format YYYY-MM-DD HH:MM:SS"}), 400

    config = INTERVAL_CONFIG[interval_key]
    num_blocks = config["blocks"]
    num_frames = config["duration"]
    block_duration = timedelta(minutes=10)
    interval_duration = block_duration * num_blocks
    end_time = start_time + interval_duration

    # Query 10-minute blocks in range
    rows = db.session.query(
        TrafficEntry.vehicle_class,
        TrafficEntry.is_peak,
        TrafficEntry.datetime,
        TrafficEntry.detection_group,
        func.sum(TrafficEntry.crz_entries).label("vehicle_count")
    ).filter(
        TrafficEntry.datetime >= start_time.strftime("%Y-%m-%d %H:%M:%S"),
        TrafficEntry.datetime < end_time.strftime("%Y-%m-%d %H:%M:%S")
    ).group_by(
        TrafficEntry.vehicle_class,
        TrafficEntry.is_peak,
        TrafficEntry.datetime,
        TrafficEntry.detection_group
    ).all()

    block_map = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"vehicles": 0, "revenue": 0})))
    all_block_times = set()

    for vclass, is_peak, dt, location, count in rows:
        key = (vclass, is_peak)
        price = PRICING.get(key, 0)
        block_map[dt][location][vclass]["vehicles"] += count
        block_map[dt][location][vclass]["revenue"] += count * price
        all_block_times.add(dt)

    all_block_times = sorted(all_block_times)
    blocks_per_frame = num_blocks / num_frames
    frames = []

    cumulative = defaultdict(lambda: defaultdict(lambda: {"vehicles": 0, "revenue": 0}))
    cumulative_total = defaultdict(lambda: {"vehicles": 0, "revenue": 0})

    for i in range(num_frames):
        frame_start = start_time + timedelta(seconds=i)
        frame_data = {
            "timestamp": frame_start.strftime("%Y-%m-%d %H:%M:%S"),
            "scale": 1,
            "locations": {}
        }

        start_idx = int(i * blocks_per_frame)
        end_idx = int((i + 1) * blocks_per_frame)
        fractional = (i + 1) * blocks_per_frame - end_idx
        # Always pull the block the frame overlaps with
        block_index = int(i * blocks_per_frame)
        print(block_index)
        print(i)
        print(blocks_per_frame)
        print("new block index")
        if block_index < len(all_block_times):
            block_time = all_block_times[block_index]
            portion = blocks_per_frame  # portion of block assigned to each frame
            frame_fraction = min(1.0, portion)  # cap at 1.0 just in case

            for location, classes in block_map[block_time].items():
                if location not in frame_data["locations"]:
                    frame_data["locations"][location] = {
                        "current": {
                            "total_vehicles": 0,
                            "total_revenue": 0,
                            "by_class": {}
                        }
                    }

                for vclass, data in classes.items():
                    vcount = data["vehicles"] * frame_fraction
                    vrevenue = data["revenue"] * frame_fraction

                    frame_data["locations"][location]["current"]["total_vehicles"] += vcount
                    frame_data["locations"][location]["current"]["total_revenue"] += vrevenue

                    if vclass not in frame_data["locations"][location]["current"]["by_class"]:
                        frame_data["locations"][location]["current"]["by_class"][vclass] = {"vehicles": 0, "revenue": 0}
                    frame_data["locations"][location]["current"]["by_class"][vclass]["vehicles"] += vcount
                    frame_data["locations"][location]["current"]["by_class"][vclass]["revenue"] += vrevenue

                    cumulative[location][vclass]["vehicles"] += vcount
                    cumulative[location][vclass]["revenue"] += vrevenue
                    cumulative_total[location]["vehicles"] += vcount
                    cumulative_total[location]["revenue"] += vrevenue

        # Finalize cumulative and round values after updating all data
        for location in frame_data["locations"]:
            cumulative_by_class = {
                vclass: {
                    "vehicles": round(cumulative[location][vclass]["vehicles"], 2),
                    "revenue": round(cumulative[location][vclass]["revenue"], 2)
                } for vclass in cumulative[location]
            }

            frame_data["locations"][location]["cumulative"] = {
                "vehicles": round(cumulative_total[location]["vehicles"], 2),
                "revenue": round(cumulative_total[location]["revenue"], 2),
                "by_class": cumulative_by_class
            }

            # Round current
            curr = frame_data["locations"][location]["current"]
            curr["total_vehicles"] = round(curr["total_vehicles"], 2)
            curr["total_revenue"] = round(curr["total_revenue"], 2)
            for vclass in curr["by_class"]:
                curr["by_class"][vclass]["vehicles"] = round(curr["by_class"][vclass]["vehicles"], 2)
                curr["by_class"][vclass]["revenue"] = round(curr["by_class"][vclass]["revenue"], 2)

        frames.append(frame_data)

    return jsonify(frames)


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(DB_PATH):
            print("Database not found. Creating and loading data...")
            db.create_all()
            load_data_from_csv('cleaned_data.csv')
        else:
            print("Database exists. Skipping CSV import.")
    app.run(debug=True)