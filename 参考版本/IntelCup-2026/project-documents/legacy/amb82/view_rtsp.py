#!/usr/bin/env python3
import argparse
import sys
import time
from urllib.parse import urlparse

try:
    import cv2
except ImportError:
    print("缺少 OpenCV。先运行：python3 -m pip install opencv-python")
    sys.exit(1)


def build_url(args):
    if args.url:
        return args.url
    if not args.ip:
        raise SystemExit("请提供 AMB82 的 IP，例如：python3 view_rtsp.py 192.168.1.154")
    return f"rtsp://{args.ip}:{args.port}{args.path}"


def main():
    parser = argparse.ArgumentParser(description="View AMB82-Mini RTSP camera stream.")
    parser.add_argument("ip", nargs="?", help="AMB82-Mini 的局域网 IP，例如 192.168.1.154")
    parser.add_argument("--port", default=554, type=int, help="RTSP 端口，官方单路示例默认 554")
    parser.add_argument("--path", default="", help="RTSP 路径；官方 StreamRTSPVideoOnly 通常为空")
    parser.add_argument("--url", help="完整 RTSP 地址，例如 rtsp://192.168.1.154:554")
    args = parser.parse_args()

    url = build_url(args)
    parsed = urlparse(url)
    if parsed.scheme != "rtsp":
        raise SystemExit(f"这不是 RTSP 地址：{url}")

    print(f"正在连接：{url}")
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        raise SystemExit(
            "连接失败。请确认电脑和 AMB82 在同一 Wi-Fi，IP/端口正确，且板子已经跑 RTSP 示例。"
        )

    window_name = "AMB82-Mini RTSP - press q or Esc to quit"
    last_frame_time = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            if time.time() - last_frame_time > 5:
                print("5 秒没有读到画面，正在继续等待；可按 q 退出。")
                last_frame_time = time.time()
            if cv2.waitKey(50) & 0xFF in (27, ord("q")):
                break
            continue

        last_frame_time = time.time()
        cv2.imshow(window_name, frame)
        if cv2.waitKey(1) & 0xFF in (27, ord("q")):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
