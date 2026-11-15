"""Backend API — see spec/api/frontend-backend.md.

The backend is a middleman: it asks the database for the chunks around the
requested circle, keeps the ones inside it and passes the result on. The
metrics themselves are computed by the pipeline.

Run:   python main.py                   (mock data, test/mock_data/*.csv)
       python main.py --data database   (the pipeline's database)
       BACKEND_DATA=database python main.py
"""

import argparse
import csv
import io

from flask import Flask, Response, jsonify, request

from src import config, features
from src.database import open_database
from src.query_validation import parse_query, parse_query_string


def create_app(database):
    app = Flask(__name__)
    app.json.sort_keys = False  # keep the field order from the spec

    @app.after_request
    def allow_cors(response):
        # Let the frontend call the API from another port during development.
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    def handle(feature, build_response):
        try:
            query = parse_query(request.get_json(silent=True), feature)

        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        
        return jsonify({"feature": feature, **build_response(query)})

    @app.post("/api/all")
    def api_all():
        def build(query):
            calendar  = features.calendar(database, query)
            anomalies = features.anomalies(database, query, calendar)
            return {
                "calendar": calendar,
                "anomalies": anomalies
            }
        
        return handle("all", build)

    @app.post("/api/hotspots")
    def api_hotspots():
        def build(query):
            hotspots = features.hotspots(database, query, limit=query["max_points"])
            return {
                "hotspots": [hotspot_to_json(h) for h in hotspots]
            }

        return handle("hotspots", build)

    @app.post("/api/calendar")
    def api_calendar():
        def build(query):
            calendar = features.calendar(database, query)
            return {
                "calendar": calendar
            }

        return handle("calendar", build)

    @app.post("/api/anomalies")
    def api_anomalies():
        def build(query):
            anomalies = features.anomalies(database, query)
            return {
                "anomalies": anomalies
            }

        return handle("anomalies", build)

    @app.get("/api/hotspots.csv")
    def api_hotspots_csv():
        """Every hotspot in the circle and period (no max_points), streamed as CSV."""
        try:
            query = parse_query_string(request.args, "hotspots_csv")

        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        hotspots = features.hotspots(database, query)
        return Response(
            hotspots_to_csv(hotspots),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment"}
        )

    return app


def hotspot_to_json(hotspot):
    """Same hotspot, with the date as an ISO-8601 string."""
    return {
        "lat": hotspot["lat"],
        "lon": hotspot["lon"],
        "date_time": hotspot["date_time"].isoformat(),
        "confidence_class": hotspot["confidence_class"]
    }


def hotspots_to_csv(hotspots):
    """CSV text, yielded in pieces as it is written, so a large export never sits in memory."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(config.HOTSPOTS_CSV_COLUMNS)

    for hotspot in hotspots:
        row = hotspot_to_json(hotspot)
        writer.writerow([row[column] for column in config.HOTSPOTS_CSV_COLUMNS])

        if buffer.tell() > config.CSV_STREAM_PIECE_BYTES:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()

    yield buffer.getvalue()


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        choices=config.DATA_OPTIONS,
        default=config.DATA,
        help="mock = CSV files, database = the pipeline's database (default: $BACKEND_DATA or mock)"
    )
    parser.add_argument(
        "--mock-dir",
        default=config.MOCK_DATA_DIR,
        help="folder with the mock CSV files (only for --data mock)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    try:
        database = open_database(args.data, mock_dir=args.mock_dir)

    except (FileNotFoundError, NotImplementedError, ValueError) as error:
        raise SystemExit(f"Cannot start with --data {args.data}: {error}")

    print(f"Data: {args.data}")
    app = create_app(database)
    app.run(host=config.HOST, port=config.PORT)
