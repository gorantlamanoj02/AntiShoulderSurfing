# Face Detection and Alerting Report

## Summary

The monitoring flow detected multiple faces, but it did not treat one
persistently unknown face as an intrusion. For a single face, the code showed
an “identity uncertain” status and did not set an intrusion reason. As a
result, it could fail to activate protection, capture a snapshot, or send an
alert when the person in view was not the enrolled user.

## Change made

In `monitoring/main.py`, a single face classified as unknown now becomes an
`Unknown face detected` event after it remains visible for 0.8 seconds. The
existing 0.8-second persistence requirement for multiple faces remains in
place. Confirmed intrusion events continue through the existing flow that
activates the privacy overlay, captures a JPEG frame, and sends the alert.
Three consecutive suspicious frames are required after the 0.8-second
observation confirmation before the incident is emitted.

The dashboard server accepts both `Unknown face detected` and
`Multiple faces detected`. Snapshot upload is controlled by
`ENABLE_INTRUSION_SNAPSHOTS`; it is enabled in the current local configuration.

## Recognition observations

The enrolled model and detection model loaded successfully in the project's
Python environment. Running the detector and recognizer on the five incident
JPEGs already stored in the project found one face per image. The model
predicted label `0` for each, with LBPH distances from 69.4 to 87.5. The
current authorization threshold is 65.0, so those images would be classified
as unknown by the current identity check.

These are incident images, not verified labeled examples of both the
authorized user and other people. They do not establish an appropriate
replacement threshold. The threshold was therefore left unchanged; calibrate
it using representative known-authorized and known-unauthorized samples.

## Verification performed

- Python syntax compilation passed for the monitoring and face recognition
  modules.
- Focused checks confirmed that unknown and multiple-face observations do not
  trigger before 0.8 seconds and do trigger after that duration.
- Confirmed both generated event strings are accepted by the dashboard server.
- Confirmed the configured local environment enables snapshot uploads.
- A live webcam session and end-to-end live dashboard alert were not tested.

## Run commands

See [README.md](./README.md) for environment setup, authorized-user
registration, dashboard startup, monitoring startup, and troubleshooting
commands.
