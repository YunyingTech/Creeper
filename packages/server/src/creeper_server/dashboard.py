"""Read-only SQLite result browser and JSON API."""

from pathlib import Path

from creeper_core.db_utils import DB
from creeper_core.settings import ROOT
from flask import Flask, jsonify, render_template, request


class Dashboard:
    def __init__(self, database_path=None):
        self.database_path = Path(database_path or ROOT / "data/creeper.sqlite3")
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent / "templates"))
        self.app.json.ensure_ascii = False
        with DB(self.database_path):
            pass

        @self.app.get("/")
        def index():
            return render_template("dashboard.html")

        @self.app.get("/api/results")
        def results():
            try:
                limit = int(request.args.get("limit", "50"))
                offset = int(request.args.get("offset", "0"))
                if not 1 <= limit <= 200 or offset < 0:
                    raise ValueError()
            except ValueError:
                return jsonify(error="limit 必须为 1–200，offset 必须为非负整数"), 400
            query = request.args.get("q", "").strip()
            if len(query) > 500:
                return jsonify(error="搜索词不能超过 500 个字符"), 400
            with DB(self.database_path) as database:
                return jsonify(database.list_results(limit=limit, offset=offset, query=query))

        @self.app.get("/api/stats")
        def stats():
            with DB(self.database_path) as database:
                return jsonify(database.stats())

        @self.app.get("/api/tasks")
        def tasks():
            with DB(self.database_path) as database:
                return jsonify(database.task_stats())

        @self.app.after_request
        def response_headers(response):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'self'; script-src 'self'; "
                "frame-ancestors 'none'; base-uri 'self'"
            )
            return response

    def run(self, host="127.0.0.1", port=5000):
        self.app.run(host=host, port=port, use_reloader=False, use_debugger=False)
