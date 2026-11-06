
import cv2
import mediapipe as mp
import numpy as np
import time
from pathlib import Path


# Project configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "blaze_face_short_range.tflite"

MIN_CONFIDENCE = 0.5


def main():
    if not MODEL_PATH.exists():
        print(f"ERROR: Model not found: {MODEL_PATH}")
        return

    # MediaPipe Tasks classes
    BaseOptions = mp.tasks.BaseOptions
    FaceDetector = mp.tasks.vision.FaceDetector
    FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
    RunningMode = mp.tasks.vision.RunningMode

    options = FaceDetectorOptions(
        base_options=BaseOptions(
            model_asset_path=str(MODEL_PATH)
        ),
        running_mode=RunningMode.VIDEO,
        min_detection_confidence=MIN_CONFIDENCE,
    )

    # Open macOS webcam
    camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

    if not camera.isOpened():
        print("ERROR: Webcam cannot be opened.")
        return

    print("Face detection system started.")
    print("Press Q to exit.")

    start_time = time.monotonic()
    previous_timestamp = -1

    try:
        with FaceDetector.create_from_options(options) as detector:

            while True:
                success, frame = camera.read()

                if not success:
                    print("ERROR: Unable to read camera frame.")
                    break

                # Mirror image for easy visualization
                frame = cv2.flip(frame, 1)

                # Convert OpenCV BGR to RGB
                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                rgb_frame = np.ascontiguousarray(rgb_frame)

                # Convert to MediaPipe image
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame
                )

                # Timestamps must increase between frames
                timestamp_ms = max(
                    int((time.monotonic() - start_time) * 1000),
                    previous_timestamp + 1
                )
                previous_timestamp = timestamp_ms

                # Run face detection
                result = detector.detect_for_video(
                    mp_image,
                    timestamp_ms
                )

                face_count = len(result.detections)

                # Draw face bounding boxes
                for detection in result.detections:
                    bbox = detection.bounding_box

                    x = bbox.origin_x
                    y = bbox.origin_y
                    w = bbox.width
                    h = bbox.height

                    confidence = (
                        detection.categories[0].score
                        if detection.categories
                        else 0.0
                    )

                    cv2.rectangle(
                        frame,
                        (x, y),
                        (x + w, y + h),
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        f"Face: {confidence:.2f}",
                        (max(0, x), max(25, y - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

                # Determine visual status
                if face_count >= 2:
                    status = "WARNING: Multiple Faces Detected"
                    status_color = (0, 0, 255)
                elif face_count == 1:
                    status = "Single Face Detected"
                    status_color = (0, 255, 0)
                else:
                    status = "No Face Detected"
                    status_color = (0, 255, 255)

                # Show face count
                cv2.putText(
                    frame,
                    f"Faces Detected: {face_count}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2
                )

                # Show status
                cv2.putText(
                    frame,
                    status,
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    status_color,
                    2
                )

                cv2.imshow(
                    "Anti-Shoulder-Surfing | Face Detection",
                    frame
                )

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Face detection stopped.")


if __name__ == "__main__":
    main()