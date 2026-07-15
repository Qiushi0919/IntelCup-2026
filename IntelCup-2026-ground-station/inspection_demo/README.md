# 飞行巡检识别 Demo（独立版）

这是一个暂不接入地面站的基础版本，用 USB 摄像头验证三类巡检目标：

- 人脸：只判断“画面中存在人脸”，使用 233 KB 的 OpenCV YuNet 模型；
- 文字：离线识别简体中文、英文与数字，使用 RapidOCR；
- 火源：复用地面站现有的真实明火规则和红色圆形模拟火源规则，并连续 3 帧确认。

Demo 使用独立 `.venv`，不会修改地面站、手势识别或 Qwen 的 Python 环境。OCR 在单独线程中低频运行；视频队列不积压旧帧，适合 8 GB 内存。

当前基础版优先保证开箱即用，三类识别均在 CPU 上运行：OCR 最多使用 4 个推理线程，完成一次后至少等待 3 秒再扫描；GPU 留给后续 Qwen 按需复核，NPU 留给正式接入地面站时的 OpenVINO 人脸/OCR 后端。这个 Demo 不会虚报已经调用 NPU。

## 一键运行

双击：

```text
run_demo.bat
```

第一次运行会安装依赖并下载 YuNet 小模型，之后可以离线启动。当前电脑已经准备好环境和模型。

窗口按键：

- `1`：开关人脸检测；
- `2`：开关中英文 OCR；
- `3`：开关火源检测；
- `O`：立即执行一次 OCR；
- `S`：保存巡检截图；
- `Q` 或 `Esc`：退出。

火源连续确认后会自动把事件画面保存到 `captures/`。该目录已被 Git 忽略。

首次 OCR 会在后台加载三个小模型，通常需要数秒；此时按退出键，窗口会先关闭，程序会等待这一轮扫描安全结束后完全退出。

## 命令行用法

USB 摄像头：

以下命令从 `IntelCup-2026-ground-station` 目录运行：

```powershell
inspection_demo\.venv\Scripts\python.exe -m inspection_demo.app --source 0
```

测试图片或视频：

```powershell
inspection_demo\.venv\Scripts\python.exe -m inspection_demo.app --source ground_station\examples\fire_test_scene.png
```

未来切换为无线图传时，识别模块不需要修改，只替换输入参数：

```powershell
inspection_demo\.venv\Scripts\python.exe -m inspection_demo.app --source rtsp://设备IP:554
```

无窗口回归测试：

```powershell
inspection_demo\.venv\Scripts\python.exe -m inspection_demo.self_test --camera
```

## 火源实物方案

基础比赛展示建议使用“哑光红色圆形模拟火源”：

1. 用黑色哑光底板减少反光；
2. 放置直径不同的红色圆片或磁贴；
3. 让摄像头画面中圆片直径至少约 8 像素；
4. 可在旁边加入 USB 供电的橙黄色闪烁 LED 增加展示效果，但红色圆片仍作为可靠识别目标；
5. 不建议在无人机附近使用真实明火。

当前规则会检查红色饱和度、面积、圆度和填充率，并连续 3 帧确认，适合制作简单、安全、可重复的实物场景。真实明火分支仍会检测明显的红橙黄火焰，但复杂环境下可能被暖色灯、夕阳或橙色物体干扰。

## 后续接入地面站

数据边界已经按后续集成设计：

```text
USB / 图片 / 视频 / RTSP
          ↓
OpenCVFrameSource.read() → 标准 BGR 帧
          ↓
InspectionEngine.process() → face / text / fire 通用结果
          ↓
当前 OpenCV 预览；后续 Qt 图传画布、事件中心和地图标点
```

无人机起飞、地面站切换到无线图传后，可直接把 `AMB82Camera` 的帧送给 `InspectionEngine`。基础 Demo 不逐帧调用 Qwen，GPU 留给后续按键触发的智能复核。

## 可扩展方向

1. **地图事件定位**：把识别框、无人机 GPS、高度、航向和时间绑定，在地图上生成 FACE/TEXT/FIRE 事件点。
2. **目标跟踪与去重**：同一个人脸、招牌或火源只生成一次事件，离开后再次出现才新增。
3. **事件证据包**：保存事件前后数秒视频、截图、位置和置信度，自动生成巡检报告。
4. **性别外观估计**：可增加 OpenVINO `age-gender-recognition-retail-0013`，但结果只能视为模型估计，航拍小脸误差较大。
5. **本地人员登记识别**：经本人授权后，用人脸特征模型与本地登记库匹配；陌生人只显示“未登记人员”，不上传云端。
6. **更多目标**：烟雾、人员跌倒、车辆、二维码、危险区域越界、安全帽/反光衣。
7. **Qwen 复核**：只在用户点击事件或置信度不足时，把单张关键帧交给 Qwen 生成中文解释，避免 8 GB 机器持续占用重模型。
8. **隐私模式**：实时打码未登记人脸，设置截图保留时间和一键清除。
