import base64
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

SERVER_URL = os.getenv(
    "SECURITY_SERVER_URL",
    "http://127.0.0.1:5001"
)

API_TOKEN = os.getenv("SECURITY_API_TOKEN")



def send_security_alert(event, snapshot_bytes=None):
    """
    Send an intrusion event to the local Flask server.
    Optionally attach a JPEG snapshot.
    """

    if not API_TOKEN:
        print("[NETWORK] Missing API token")
        return False

    payload = {
        "workstation": "macOS-Laptop",
        "event": event
    }

    # Image capture is explicitly opt-in
    snapshots_enabled = (
        os.getenv(
            "ENABLE_INTRUSION_SNAPSHOTS", "false"
        ).lower() == "true"
    )

    if snapshots_enabled and snapshot_bytes:
        payload["snapshot_base64"] = (
            base64.b64encode(snapshot_bytes).decode("ascii")
        )

    request = Request(
        url=f"{SERVER_URL.rstrip('/')}/api/alert",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}"
        },
        method="POST"
    )

    try:
        with urlopen(request, timeout=3) as response:
            result = json.load(response)

            if (
                response.status == 201
                and result.get("success") is True
            ):
                print(
                    "[NETWORK] Alert saved: "
                    f"{result['incident']['id']}",
                    flush=True
                )
                return True

            return False

    except HTTPError as error:
        print(
            f"[NETWORK] HTTP error: {error.code}",
            flush=True
        )

    except URLError as error:
        print(
            f"[NETWORK] Connection error: {error.reason}",
            flush=True
        )

    except (TimeoutError, OSError, ValueError) as error:
        print(
            f"[NETWORK] Error: {error}",
            flush=True
        )

    return False

if __name__ == "__main__":
    send_security_alert("Multiple faces detected")
