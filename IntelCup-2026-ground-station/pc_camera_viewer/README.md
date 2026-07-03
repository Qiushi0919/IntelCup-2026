# AMB82-Mini 电脑端监控

## 使用方法

1. 打开手机热点，并保持 AMB82-Mini 和电脑都连接到该热点。
2. 双击 `start_viewer.bat`。
3. 地面站建议使用 `auto` 自动搜索；独立监控器默认 RTSP 地址为 `rtsp://172.25.135.2:554`。

首次启动会自动安装运行环境，之后可直接打开。

## 功能

- H.264 RTSP 实时预览
- 1280×720、15 FPS、约 2 Mbps 图传
- 旧版 `/snapshot.jpg` 固件自动兼容
- 自动断线重连
- 截图
- MP4 录像
- 实时分辨率和 FPS

截图保存在 `captures`，录像保存在 `recordings`。

## 快捷键

- `S`：截图
- `R`：开始或停止录像
- `Esc`：退出

## 后续接入目标识别

在 `app.py` 的 `process_frame()` 中接入模型推理。该函数接收一帧 OpenCV
BGR 图像，并返回要显示的图像。可以在这里运行 YOLO、绘制检测框和输出目标坐标。

也可以直接把摄像头作为 Python 图像源：

```python
from amb82_camera import AMB82Camera

camera = AMB82Camera("auto")
ok, frame = camera.read()
```

`frame` 就是标准 OpenCV BGR `numpy.ndarray`，可直接送入 YOLO 或其他模型。
运行 `example_preview.py` 可测试低延迟预览，运行 `example_detection.py`
可作为目标识别程序的起点。
