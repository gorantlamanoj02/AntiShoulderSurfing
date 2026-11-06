
import argparse
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


ROOT = Path(__file__).resolve().parents[2]

DETECTION_MODEL = (
    ROOT / "models" / "blaze_face_short_range.tflite"
)

RECOGNITION_MODEL = (
    ROOT / "data" / "authorized_user" / "face_model.yml"
)

SAMPLE_COUNT = 500
SAMPLE_INTERVAL = 0.1
FACE_SIZE = (150, 150)

# Experimental starting value, not a validated security threshold.
# Lower LBPH distance means a closer match.
MATCH_THRESHOLD = 65.0


def create_detector():
    options = mp.tasks.vision.FaceDetectorOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(DETECTION_MODEL)
        ),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        min_detection_confidence=0.5,
    )

    return mp.tasks.vision.FaceDetector.create_from_options(
        options
    )


def prepare_face(frame, bounding_box):
    height, width = frame.shape[:2]

    x1 = max(0, bounding_box.origin_x)
    y1 = max(0, bounding_box.origin_y)

    x2 = min(
        width,
        bounding_box.origin_x + bounding_box.width
    )
    y2 = min(
        height,
        bounding_box.origin_y + bounding_box.height
    )

    if x2 <= x1 or y2 <= y1:
        return None, None

    cropped = frame[y1:y2, x1:x2]

    if cropped.size == 0:
        return None, None

    gray = cv2.cvtColor(
        cropped,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.resize(gray, FACE_SIZE)
    gray = cv2.equalizeHist(gray)

    return gray, (x1, y1, x2, y2)


def detect_faces(detector, frame, timestamp_ms):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)

    image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb
    )

    result = detector.detect_for_video(
        image,
        timestamp_ms
    )

    return result.detections


def start_camera():
    camera = cv2.VideoCapture(
        0,
        cv2.CAP_AVFOUNDATION
    )

    if not camera.isOpened():
        raise RuntimeError(
            "Unable to open webcam. Check camera permissions."
        )

    return camera


def timestamp(start_time, previous):
    current = int(
        (time.monotonic() - start_time) * 1000
    )
    return max(current, previous + 1)


def register_user():
    print("Starting authorized-user registration...")
    print("Only the authorized user should be visible.")
    print("Move your head slightly between samples.")
    print("Press Q to cancel.")

    samples = []
    labels = []

    camera = start_camera()
    start_time = time.monotonic()
    last_sample_time = 0
    previous_timestamp = -1

    try:
        with create_detector() as detector:
            while len(samples) < SAMPLE_COUNT:
                success, frame = camera.read()

                if not success:
                    break

                frame = cv2.flip(frame, 1)

                current_timestamp = timestamp(
                    start_time,
                    previous_timestamp
                )
                previous_timestamp = current_timestamp

                detections = detect_faces(
                    detector,
                    frame,
                    current_timestamp
                )

                message = "Show exactly one face"

                if len(detections) == 1:
                    face, coords = prepare_face(
                        frame,
                        detections[0].bounding_box
                    )

                    if face is not None:
                        x1, y1, x2, y2 = coords

                        cv2.rectangle(
                            frame,
                            (x1, y1),
                            (x2, y2),
                            (0, 255, 0),
                            2
                        )

                        now = time.monotonic()

                        if (
                            now - last_sample_time
                            >= SAMPLE_INTERVAL
                        ):
                            samples.append(face)
                            labels.append(0)
                            last_sample_time = now

                        message = (
                            f"Capturing: "
                            f"{len(samples)}/{SAMPLE_COUNT}"
                        )

                elif len(detections) > 1:
                    message = (
                        "Multiple faces! Registration paused."
                    )

                cv2.putText(
                    frame,
                    message,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 255),
                    2
                )

                cv2.imshow(
                    "Authorized User Registration",
                    frame
                )

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("Registration cancelled.")
                    return

        if len(samples) != SAMPLE_COUNT:
            print("Not enough samples. Registration failed.")
            return

        print("Training facial recognition model...")

        recognizer = cv2.face.LBPHFaceRecognizer_create()

        recognizer.train(
            samples,
            np.array(labels, dtype=np.int32)
        )

        RECOGNITION_MODEL.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        recognizer.write(str(RECOGNITION_MODEL))

        print("Registration successful!")
        print(f"Saved model: {RECOGNITION_MODEL}")

    finally:
        camera.release()
        cv2.destroyAllWindows()


def verify_user():
    if not RECOGNITION_MODEL.exists():
        print("ERROR: No registered user model found.")
        print("Run registration first.")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(RECOGNITION_MODEL))

    camera = start_camera()

    start_time = time.monotonic()
    previous_timestamp = -1

    print("Identity verification started.")
    print("Press Q to exit.")

    try:
        with create_detector() as detector:
            while True:
                success, frame = camera.read()

                if not success:
                    break

                frame = cv2.flip(frame, 1)

                current_timestamp = timestamp(
                    start_time,
                    previous_timestamp
                )
                previous_timestamp = current_timestamp

                detections = detect_faces(
                    detector,
                    frame,
                    current_timestamp
                )

                unknown_count = 0

                for detection in detections:
                    face, coords = prepare_face(
                        frame,
                        detection.bounding_box
                    )

                    if face is None:
                        unknown_count += 1
                        continue

                    label, distance = recognizer.predict(face)
                    
                    is_authorized = (
                        label == 0
                        and distance <= MATCH_THRESHOLD
                    )

                    if is_authorized:
                        text = f"Authorized ({distance:.1f})"
                        color = (0, 255, 0)
                    else:
                        text = f"Unknown ({distance:.1f})"
                        color = (0, 0, 255)
                        unknown_count += 1

                    x1, y1, x2, y2 = coords

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        color,
                        2
                    )

                    cv2.putText(
                        frame,
                        text,
                        (x1, max(25, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        color,
                        2
                    )

                face_count = len(detections)

                if face_count > 1:
                    status = "WARNING: Multiple faces"
                    status_color = (0, 0, 255)

                elif unknown_count > 0:
                    status = "WARNING: Unknown face"
                    status_color = (0, 0, 255)

                elif face_count == 1:
                    status = "Authorized user detected"
                    status_color = (0, 255, 0)

                else:
                    status = "No face detected"
                    status_color = (0, 255, 255)

                cv2.putText(
                    frame,
                    f"Face count: {face_count}",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )

                cv2.putText(
                    frame,
                    status,
                    (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    status_color,
                    2
                )

                cv2.imshow(
                    "Anti-Shoulder-Surfing | Verification",
                    frame
                )

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Identity verification stopped.")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "mode",
        choices=["register", "verify"]
    )

    args = parser.parse_args()

    if not DETECTION_MODEL.exists():
        print(
            f"Missing detection model: {DETECTION_MODEL}"
        )
        return

    if not hasattr(cv2, "face"):
        print("OpenCV contrib face module is missing.")
        return

    if args.mode == "register":
        register_user()
    else:
        verify_user()


if __name__ == "__main__":
    main()
