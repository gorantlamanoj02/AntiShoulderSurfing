# Anti-Shoulder-Surfing Security System

This project monitors a workstation webcam, checks whether a face matches the
registered authorized user, and reports a sustained unknown face or multiple
faces to the incident dashboard. The report in
[FACE_DETECTION_REPORT.md](./FACE_DETECTION_REPORT.md) summarizes the recent
detection fix and its verification.

## Requirements

- macOS with webcam access
- Python 3.11 (the current project environment uses Python 3.11)
- The included face detection model at `models/blaze_face_short_range.tflite`
- An authorized-user model at `data/authorized_user/face_model.yml`

Grant camera access to the terminal or application running Python when macOS
prompts for it.

## Setup

Run these commands from the project root:

```bash
cd /Users/manoj/Documents/AntiShoulderSurfing
python3.11 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

Create a `.env` file in the project root if one does not already exist. Keep
this file private and do not commit it. It must define:

```dotenv
SECURITY_API_TOKEN=replace-with-a-private-value
SECURITY_SERVER_URL=http://127.0.0.1:5001
ENABLE_INTRUSION_SNAPSHOTS=true
```

`SECURITY_API_TOKEN` must be non-empty for the dashboard server to start.
Set `ENABLE_INTRUSION_SNAPSHOTS=true` to include incident images in dashboard
alerts. Snapshot upload can be disabled by setting it to `false`.

## Register the authorized user

The project currently includes a saved model. Re-register only when setting up
or changing the authorized user. Run:

```bash
cd /Users/manoj/Documents/AntiShoulderSurfing
./.venv/bin/python monitoring/recognition/face_identity.py register
```

Keep only the authorized user in the camera view during registration, follow
the on-screen instructions, and press `Q` to cancel.

To preview identity classification without starting protection or sending
alerts:

```bash
./.venv/bin/python monitoring/recognition/face_identity.py verify
```

## Start the dashboard and monitoring app

Open two terminal windows, both in the project root.

**Terminal 1 — incident logging dashboard:**

```bash
cd /Users/manoj/Documents/AntiShoulderSurfing
./.venv/bin/python incident_logging/server.py
```

Open the dashboard at <http://127.0.0.1:5001>.

**Terminal 2 — webcam monitoring and protection app:**

```bash
cd /Users/manoj/Documents/AntiShoulderSurfing
./.venv/bin/python monitoring/main.py
```

Click **Start Monitoring**. The app activates its privacy overlay when an
intrusion is confirmed. Press **Stop Monitoring** to stop camera monitoring;
close the dashboard server with `Ctrl+C`.

## Detection and alerts

- A face is classified as authorized using the LBPH model and the match
  threshold in `monitoring/recognition/face_identity.py`.
- One face classified as unknown must remain visible for 0.8 seconds before it
  is treated as an intrusion.
- Multiple detected faces must remain visible for 0.8 seconds before they are
  treated as an intrusion. After either condition is confirmed, three
  consecutive suspicious frames are required before the app captures evidence
  and sends the alert.
- The app encodes a camera frame as a JPEG. With snapshot uploads enabled, the
  dashboard stores and displays the image with the incident.
- Alerts are sent to `SECURITY_SERVER_URL`; its default is
  `http://127.0.0.1:5001`.

The LBPH threshold is a project setting that should be calibrated using
representative authorized and unauthorized faces. Face detection and identity
classification can be affected by lighting, camera quality, pose, distance,
and enrollment samples.

## Troubleshooting

- **Camera cannot be opened:** grant camera permission to the terminal or VS
  Code, close other apps using the camera, then restart monitoring.
- **Authorized-user model missing:** run the registration command above.
- **Dashboard server does not start:** check that `.env` exists and
  `SECURITY_API_TOKEN` is set to a non-empty value.
- **Alerts do not appear:** start the dashboard server first, check
  `SECURITY_SERVER_URL`, and confirm both processes can use the same project
  `.env` file.
- **Incident appears without a snapshot:** set
  `ENABLE_INTRUSION_SNAPSHOTS=true` in `.env`, then restart the app.
- **Authorized user is classified as unknown:** use the `verify` command to
  observe the result; improve registration samples and lighting, and calibrate
  the match threshold before relying on it.

## Related files

- [monitoring/main.py](./monitoring/main.py) — monitoring application and intrusion
  confirmation
- [monitoring/recognition/face_identity.py](./monitoring/recognition/face_identity.py)
  — face detection, registration, and identity verification
- [monitoring/networking/alert_sender.py](./monitoring/networking/alert_sender.py)
  — alert and optional snapshot submission
- [incident_logging/server.py](./incident_logging/server.py) — dashboard server and incident
  storage
