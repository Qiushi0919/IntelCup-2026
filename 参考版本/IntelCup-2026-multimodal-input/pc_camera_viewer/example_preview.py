import time

import cv2
import numpy as np

from amb82_camera import AMB82Camera


WINDOW_NAME = "AMB82-Mini"
cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

with AMB82Camera(
    "auto",
    timeout=8.0,
    reconnect_delay=0.5,
    poll_interval=0.5,
) as camera:
    last_frame = None
    last_status_time = 0.0

    while True:
        ok, frame = camera.read_latest()
        if ok:
            last_frame = frame

        display = last_frame
        if display is None:
            display = np.full((360, 640, 3), 255, dtype=np.uint8)
            cv2.putText(
                display,
                "Waiting for AMB82-Mini...",
                (115, 185),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (30, 30, 30),
                2,
            )

        status = "ONLINE" if camera.connected else "RECONNECTING"
        color = (0, 220, 0) if camera.connected else (0, 0, 255)
        cv2.putText(
            display,
            f"{camera.fps:.2f} FPS  {camera.source_kind.upper()}  {status}",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )
        cv2.imshow(WINDOW_NAME, display)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break

        # Clicking the title-bar X destroys the native window. Without this
        # check, the next imshow() call would create the window again.
        try:
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break

        now = time.monotonic()
        if not camera.connected and now - last_status_time >= 5.0:
            print("Reconnecting:", camera.last_error or "waiting for camera")
            last_status_time = now

        time.sleep(0.005)

cv2.destroyAllWindows()
