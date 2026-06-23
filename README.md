# Intel Cup 2026 · Ground Station

当前分支维护地面站、图传、火源识别和语音识别相关代码。

## 当前代码状态

- 图传：OK，支持 AMB82 RTSP / 快照回退，地面站界面可连接相机。
- 数传：待接入，当前飞控/任务状态仍使用模拟数据。
- 语音识别：OK，已接入 OpenVINO Whisper 实时识别，识别文本会进入候选指令流程。

## 运行截图

![地面站运行截图](docs/images/ground-station-runtime.png)

## 目录

```text
ground_station/      PyQt5 地面站、任务地图、告警与火源识别
voice_asr/           OpenVINO Whisper 实时语音识别
pc_camera_viewer/    AMB82 RTSP/快照读取与独立预览程序
wireless_camera/     AMB82 720p H.264 RTSP 固件
recovery_blink/      AMB82 恢复与硬件连通测试
```

## 快速启动

Windows 下双击：

```text
run_ground_station.bat
```

或在当前目录运行：

```powershell
python -m pip install -r ground_station\requirements.txt
python ground_station\main.py
```

## 语音识别

地面站会优先调用 Anaconda 的 `gluon` 环境运行实时语音识别：

```text
C:\Users\Qiushi\.conda\envs\gluon\python.exe
```

如果换机器后缺少依赖，可运行：

```text
install_voice_asr_deps.bat
```

首次加载 Whisper/OpenVINO 模型会从 Hugging Face 下载模型，耗时较长。
