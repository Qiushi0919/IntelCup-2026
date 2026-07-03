import cv2

from amb82_camera import AMB82Camera


def detect_objects(frame):
    """
    在这里接入 YOLO 等模型。

    例如：
        results = model(frame)
        return results[0].plot()
    """
    return frame


with AMB82Camera("auto") as camera:
    while True:
        ok, frame = camera.read(timeout=3)
        if not ok:
            continue

        result_frame = detect_objects(frame)
        cv2.imshow("Object Detection", result_frame)

        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
            break

cv2.destroyAllWindows()
