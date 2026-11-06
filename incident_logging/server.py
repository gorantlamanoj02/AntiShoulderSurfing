import base64
import binascii
from io import BytesIO
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from flask import abort, send_from_directory
import os
import hmac
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_socketio import SocketIO

ROOT = Path(__file__).resolve().parent

# Load shared project configuration
load_dotenv(ROOT.parent / ".env")

DB_PATH = ROOT / "database" / "incidents.db"
SNAPSHOT_DIR = ROOT / "database" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
HTML_PATH = ROOT / "dashboard" / "index.html"

API_TOKEN = os.environ.get("SECURITY_API_TOKEN")

if not API_TOKEN:
    raise RuntimeError(
        "Set SECURITY_API_TOKEN before starting the server."
    )

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins=None
)

ALLOWED_EVENTS = {
    "Unknown face detected",
    "Multiple faces detected",
    "Camera monitoring failure",
}



def initialize_database():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with sqlite3.connect(DB_PATH) as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                workstation TEXT NOT NULL,
                event TEXT NOT NULL,
                snapshot_path TEXT
            )
        """)

        # Migrate the database created in Step 7
        existing_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(incidents)"
            ).fetchall()
        }

        if "snapshot_path" not in existing_columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN snapshot_path TEXT
            """)

    print("Incident database initialized.")


def get_incidents():
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT
                id,
                timestamp,
                workstation,
                event,
                snapshot_path
            FROM incidents
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()

    incidents = []

    for row in rows:
        incident = dict(row)

        incident["snapshot_url"] = (
            f"/api/snapshots/{incident['id']}"
            if incident["snapshot_path"]
            else None
        )

        incidents.append(incident)

    return incidents

@app.route("/")
def dashboard():
    return send_file(HTML_PATH)


@app.route("/api/health")
def health():
    return jsonify({"status": "online"})


@app.route("/api/incidents")
def incidents():
    return jsonify(get_incidents())

def save_snapshot(encoded_snapshot):
    """
    Validate a Base64 image and store a small JPEG.
    Returns its generated filename.
    """

    if not isinstance(encoded_snapshot, str):
        raise ValueError("Invalid snapshot data")

    # Limit encoded image size
    if len(encoded_snapshot) > 700_000:
        raise ValueError("Snapshot is too large")

    try:
        image_bytes = base64.b64decode(
            encoded_snapshot,
            validate=True
        )

        if len(image_bytes) > 500_000:
            raise ValueError("Snapshot exceeds size limit")

        with Image.open(BytesIO(image_bytes)) as image:
            if image.width * image.height > 2_000_000:
                raise ValueError("Image dimensions too large")

            # Re-encode the image rather than trusting
            # the original uploaded file bytes.
            clean_image = image.convert("RGB")
            clean_image.thumbnail((640, 640))

            filename = f"incident_{uuid4().hex}.jpg"

            destination = SNAPSHOT_DIR / filename

            clean_image.save(
                destination,
                format="JPEG",
                quality=75
            )

            destination.chmod(0o600)

        return filename

    except (
        binascii.Error,
        ValueError,
        OSError,
        UnidentifiedImageError
    ) as error:
        raise ValueError(
            f"Invalid snapshot: {error}"
        ) from error


@app.route("/api/alert", methods=["POST"])
def receive_alert():

    authorization = request.headers.get(
        "Authorization", ""
    )

    expected = f"Bearer {API_TOKEN}"

    if not hmac.compare_digest(
        authorization,
        expected
    ):
        return jsonify({
            "error": "Unauthorized"
        }), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid JSON"
        }), 400

    event = data.get("event")
    workstation = data.get(
        "workstation", "macOS-Laptop"
    )

    if event not in ALLOWED_EVENTS:
        return jsonify({
            "error": "Invalid event"
        }), 400

    if (
        not isinstance(workstation, str)
        or not workstation
        or len(workstation) > 64
    ):
        return jsonify({
            "error": "Invalid workstation"
        }), 400

    snapshot_path = None

    if "snapshot_base64" in data:
        try:
            snapshot_path = save_snapshot(
                data["snapshot_base64"]
            )
        except ValueError as error:
            return jsonify({
                "error": str(error)
            }), 400

    timestamp = datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")

    try:
        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.execute("""
                INSERT INTO incidents (
                    timestamp,
                    workstation,
                    event,
                    snapshot_path
                )
                VALUES (?, ?, ?, ?)
            """, (
                timestamp,
                workstation,
                event,
                snapshot_path
            ))

            incident_id = cursor.lastrowid

    except Exception:
        # Avoid leaving orphan images
        if snapshot_path:
            (SNAPSHOT_DIR / snapshot_path).unlink(
                missing_ok=True
            )
        raise

    incident = {
        "id": incident_id,
        "timestamp": timestamp,
        "workstation": workstation,
        "event": event,
        "snapshot_url": (
            f"/api/snapshots/{incident_id}"
            if snapshot_path
            else None
        )
    }

    socketio.emit(
        "security_alert",
        incident
    )

    print(
        f"SECURITY INCIDENT: {incident_id}",
        flush=True
    )

    return jsonify({
        "success": True,
        "incident": incident
    }), 201

@app.route("/api/snapshots/<int:incident_id>")
def get_snapshot(incident_id):

    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute("""
            SELECT snapshot_path
            FROM incidents
            WHERE id = ?
        """, (incident_id,)).fetchone()

    if row is None or not row[0]:
        abort(404)

    return send_from_directory(
        SNAPSHOT_DIR,
        row[0],
        mimetype="image/jpeg"
    )

if __name__ == "__main__":
    initialize_database()

    print("Starting security dashboard...")
    print("Open http://127.0.0.1:5001")

    socketio.run(
        app,
        host="127.0.0.1",
        port=5001,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
