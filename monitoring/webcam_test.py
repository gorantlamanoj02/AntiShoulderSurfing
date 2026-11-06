import cv2

def main():
    print("Starting Anti-Shoulder-Surfing System...")
    print("Initializing macOS webcam...")

    camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

    if not camera.isOpened():
        print("ERROR: Webcam could not be opened.")
        print("Check macOS camera permissions.")
        return

    print("Webcam initialized successfully!")
    print("Press Q to exit.")

    try:
        while True:
            success, frame = camera.read()

            if not success:
                print("ERROR: Failed to capture frame.")
                break

            # Flip image to behave like a mirror
            frame = cv2.flip(frame, 1)

            # Add an application heading
            cv2.putText(
                frame,
                "Anti-Shoulder-Surfing System",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            # Display webcam feed
            cv2.imshow("Workstation Security - Camera", frame)

            # Exit using Q key
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Webcam stopped successfully.")


if __name__ == "__main__":
    main()