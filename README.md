# Intel Cup 2026 · 地面站代码

本分支只维护地面站及无线图传相关代码。

## 目录

```text
ground_station/      PyQt5 地面站、任务地图、告警与火源识别
pc_camera_viewer/    AMB82 RTSP/快照读取与独立预览程序
wireless_camera/     AMB82 720p H.264 RTSP 固件
recovery_blink/      AMB82 恢复与硬件连通测试
```

## 快速启动

```powershell
python -m pip install -r ground_station\requirements.txt
python ground_station\main.py
```

Windows 也可以双击：

```text
ground_station\start_ground_station.bat
```

## 当前能力

- 1280×720、15 FPS、H.264 RTSP 图传；
- 旧版 JPEG 快照自动回退；
- 火源识别、连续帧确认和消息中心闪烁；
- 35% / 50% / 65% 三档镜头桶形畸变校正；
- 无人机状态、任务地图、安全命令和多模态交互 UI。

复制 `wireless_camera/network_config.example.h` 为 `network_config.h`
后再填写本地 Wi-Fi。真实网络配置不会提交到 Git。

其他资料位于：

- `documents`：方案与参考文档；
- `aircraft-code`：F260-T432 飞机代码。
