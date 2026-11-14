"""Backend API — see spec/api/frontend-backend.md.

Run:   python main.py                         (uses data/hotspots.csv)
       python main.py --data test/mock_hotspots.csv
"""

import argparse

from flask import Flask, jsonify, request

from src import config, features
from src.loader import load_hotspots
from src.validation import parse_query


def create_app(hotspots):
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
        selected = features.select(hotspots, query)
        return jsonify({"feature": feature, **build_response(selected, query)})

    @app.post("/api/all")
    def api_all():
        def build(selected, query):
            calendar = features.calendar(selected, query)
            return {"calendar": calendar, "anomalies": features.anomalies(calendar)}
        return handle("all", build)

    @app.post("/api/hotspots")
    def api_hotspots():
        return handle("hotspots", lambda selected, query: {
            "hotspots": features.hotspots(selected, query["max_points"])})

    @app.post("/api/calendar")
    def api_calendar():
        return handle("calendar", lambda selected, query: {
            "calendar": features.calendar(selected, query)})

    @app.post("/api/anomalies")
    def api_anomalies():
        return handle("anomalies", lambda selected, query: {
            "anomalies": features.anomalies(features.calendar(selected, query))})

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=config.DATA_FILE, help="hotspots CSV file")
    args   = parser.parse_args()

    try:
        hotspots = load_hotspots(args.data)
    except FileNotFoundError:
        raise SystemExit(f"Data file not found: {args.data}\n"
                         "For mock data run: python test/generate_mock_data.py\n"
                         "then: python main.py --data test/mock_hotspots.csv")

    app = create_app(hotspots)
    app.run(host=config.HOST, port=config.PORT)
