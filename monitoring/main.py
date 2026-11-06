
import sys
import time
import threading
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0, str(ROOT / "monitoring" / "recognition")
)
sys.path.insert(
    0, str(ROOT / "monitoring" / "protection")
)
sys.path.insert(
    0, str(ROOT / "monitoring" / "networking")
)

from alert_sender import send_security_alert

from face_identity import (
    create_detector,
    detect_faces,
    prepare_face,
    start_camera,
    timestamp,
    RECOGNITION_MODEL,
    DETECTION_MODEL,
    MATCH_THRESHOLD,
)

from screen_protector import PrivacyOverlay


class CameraWorker(QThread):

    status_updated = Signal(str)
    intrusion_detected = Signal(str, bytes)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True

        # Number of consecutive suspicious frames
        self.suspicious_frames = 0

        # Prevent duplicate alerts for one incident
        self.incident_active = False
        
        # Intrusion must remain visible long enough
        self.multiple_faces_since = None
        
        # Confirm multiple faces for 0.8 seconds
        self.MULTI_FACE_CONFIRM_SECONDS = 0.8
        
        # Remember when single-face recognition is uncertain
        self.unknown_face_since = None

        # Number of consecutive safe frames
        self.safe_frames = 0

    def stop(self):
        self.running = False

    def _classify_observation(self, face_count, unknown_count, now):
        if face_count >= 2:
            if self.multiple_faces_since is None:
                self.multiple_faces_since = now

            self.unknown_face_since = None

            elapsed = now - self.multiple_faces_since
            if elapsed >= self.MULTI_FACE_CONFIRM_SECONDS:
                return "Multiple faces detected"

        elif face_count == 1:
            self.multiple_faces_since = None

            if unknown_count > 0:
                if self.unknown_face_since is None:
                    self.unknown_face_since = now

                elapsed = now - self.unknown_face_since
                if elapsed >= self.MULTI_FACE_CONFIRM_SECONDS:
                    return "Unknown face detected"
            else:
                self.unknown_face_since = None

        else:
            self.multiple_faces_since = None
            self.unknown_face_since = None

        return None

    def run(self):
        camera = None

        try:
            recognizer = (
                cv2.face.LBPHFaceRecognizer_create()
            )
            recognizer.read(
                str(RECOGNITION_MODEL)
            )

            camera = start_camera()

            start_time = time.monotonic()
            previous_timestamp = -1

            with create_detector() as detector:

                while self.running:

                    success, frame = camera.read()

                    if not success:
                        self.error_occurred.emit(
                            "Camera frame capture failed"
                        )
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

                    face_count = len(detections)
                    unknown_count = 0

                    for detection in detections:

                        face, _ = prepare_face(
                            frame,
                            detection.bounding_box
                        )

                        if face is None:
                            unknown_count += 1
                            continue

                        label, distance = (
                            recognizer.predict(face)
                        )

                        authorized = (
                            label == 0
                            and distance <= MATCH_THRESHOLD
                        )

                        if not authorized:
                            unknown_count += 1

                    # Evaluate current observation
                    now = time.monotonic()
                    reason = self._classify_observation(
                        face_count,
                        unknown_count,
                        now
                    )

                    if reason is None:
                        if face_count >= 2:
                            self.status_updated.emit(
                                "Checking multiple-face detection..."
                            )
                        elif face_count == 1 and unknown_count > 0:
                            self.status_updated.emit(
                                "One face visible - identity uncertain"
                            )
                        elif face_count == 1:
                            self.status_updated.emit(
                                "Authorized user detected"
                            )
                        else:
                            self.status_updated.emit(
                                "No face detected"
                            )

                    # Intrusion confirmation
                    if reason is not None:

                        self.suspicious_frames += 1
                        self.safe_frames = 0

                        if (
                            self.suspicious_frames >= 3
                            and not self.incident_active
                        ):
                            self.incident_active = True

                            
                            # Capture the frame associated with
                            # this confirmed intrusion event.
                            snapshot_bytes = b""

                            # Limit image width to 640 pixels
                            height, width = frame.shape[:2]

                            if width > 640:
                                scale = 640 / width
                                snapshot_frame = cv2.resize(
                                    frame,
                                    (
                                        640,
                                        int(height * scale)
                                    )
                                )
                            else:
                                snapshot_frame = frame

                            # Encode as JPEG in memory
                            success, encoded = cv2.imencode(
                                ".jpg",
                                snapshot_frame,
                                [
                                    cv2.IMWRITE_JPEG_QUALITY,
                                    65
                                ]
                            )

                            if success:
                                snapshot_bytes = encoded.tobytes()

                            self.intrusion_detected.emit(
                                reason,
                                snapshot_bytes
                            )


                        self.status_updated.emit(
                            f"WARNING: {reason}"
                        )

                    elif face_count == 1 and unknown_count == 0:

                        self.suspicious_frames = 0
                        self.safe_frames += 1

                        self.status_updated.emit(
                            "Authorized user detected"
                        )

                        # Re-arm after 10 safe frames
                        if self.safe_frames >= 10:
                            self.incident_active = False

                    else:
                        self.suspicious_frames = 0
                        self.safe_frames = 0

                        self.status_updated.emit(
                            "No face detected"
                        )

        except Exception as error:
            self.error_occurred.emit(
                f"Monitoring error: {error}"
            )

        finally:
            if camera is not None:
                camera.release()


class SecurityApplication(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Anti-Shoulder-Surfing Security System"
        )
        self.resize(550, 340)

        self.overlay = PrivacyOverlay()
        self.worker = CameraWorker()

        self.worker.status_updated.connect(
            self.update_status
        )

        self.worker.intrusion_detected.connect(
            self.activate_protection
        )

        self.worker.error_occurred.connect(
            self.handle_error
        )

        self.build_interface()

    def build_interface(self):

        layout = QVBoxLayout()
        layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.setSpacing(20)

        heading = QLabel(
            "Automated Workstation Security"
        )

        heading.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        heading.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        self.status_label = QLabel(
            "System ready"
        )

        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.status_label.setStyleSheet(
            "font-size: 16px;"
        )

        self.start_button = QPushButton(
            "Start Monitoring"
        )

        self.start_button.clicked.connect(
            self.start_monitoring
        )

        self.stop_button = QPushButton(
            "Stop Monitoring"
        )

        self.stop_button.clicked.connect(
            self.stop_monitoring
        )

        self.stop_button.setEnabled(False)

        layout.addWidget(heading)
        layout.addWidget(self.status_label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        self.setLayout(layout)

    def start_monitoring(self):

        if self.worker.isRunning():
            return

        if not DETECTION_MODEL.exists():
            self.handle_error(
                "Face detection model is missing"
            )
            return

        if not RECOGNITION_MODEL.exists():
            self.handle_error(
                "Register the authorized user first"
            )
            return

        # Create a fresh worker for each session
        self.worker = CameraWorker()

        self.worker.status_updated.connect(
            self.update_status
        )

        self.worker.intrusion_detected.connect(
            self.activate_protection
        )

        self.worker.error_occurred.connect(
            self.handle_error
        )

        self.worker.finished.connect(
            self.monitoring_finished
        )

        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.status_label.setText(
            "Monitoring started"
        )

    def stop_monitoring(self):

        if self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        self.monitoring_finished()

    def monitoring_finished(self):

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def update_status(self, status):

        self.status_label.setText(status)
    
    
    
    def activate_protection(self, reason, snapshot_bytes):
        print(
            f"[SECURITY] Intrusion detected: {reason}",
            flush=True
        )

        self.status_label.setText(
            f"Protection activated: {reason}"
        )

        # Screen protection takes priority
        self.overlay.activate()

        # Alert transmission is asynchronous
        def send_alert_task():
            try:
                success = send_security_alert(
                    reason,
                    snapshot_bytes
                )

                if success:
                    print(
                        "[NETWORK] Alert and evidence processed",
                        flush=True
                    )
                else:
                    print(
                        "[NETWORK] Alert transmission failed",
                        flush=True
                    )

            except Exception as error:
                print(
                    f"[NETWORK] Error: {error}",
                    flush=True
                )

        threading.Thread(
            target=send_alert_task,
            daemon=True
        ).start()



    def handle_error(self, error):

        print(f"ERROR: {error}")

        self.status_label.setText(error)

        # Fail closed for runtime monitoring failures.
        # The overlay is still dismissible in demo mode.
        if self.worker.isRunning():
            self.overlay.activate()

    def closeEvent(self, event):

        self.stop_monitoring()
        self.overlay.close()
        event.accept()


def main():

    app = QApplication(sys.argv)

    window = SecurityApplication()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
