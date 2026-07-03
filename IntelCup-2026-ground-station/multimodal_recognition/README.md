# 多模态独立识别原型

本目录只负责“识别验证”，暂时不接入地面站，也不会产生无人机控制指令。

## 当前范围

### 三种手势

- 张开手掌：`Open_Palm`
- 握拳：`Closed_Fist`
- 竖大拇指：`Thumb_Up`

手势识别会进行多帧稳定判断，默认置信度低于 65% 不会触发。程序优先使用 MediaPipe 自带手势分类器；如果分类器没有给出结果，但 21 个手部关键点已经稳定检测到，会启用骨架几何兜底判断，提高张开手掌、握拳、竖大拇指三种动作的触发率。触发提示只保留约 3 秒，避免旧结果一直停在屏幕上造成误解。

### 三点目视

- 左侧：`LEFT`
- 中间：`CENTER`
- 右侧：`RIGHT`

三点目视采用个人校准。首次运行时依次注视左、中、右圆点，每个点按一次空格并保持头部稳定。校准完成后只输出三个粗粒度区域，不尝试精确模拟鼠标。

当前版本采用“头部姿态 + 视线融合”方案：头部左偏/右偏是主要方向信号，眼睛视线只作为辅助修正。这样比单纯依赖虹膜位置更稳定。点头会输出 `CONFIRM`，摇头会输出 `CANCEL`，目前只做识别展示，不接入无人机控制。

目视窗口支持 `--laser` 视线捕捉器，会在画面上绘制类似“红眼激光”的双眼视线光束。当前激光默认跟随最终的头部/视线融合结果：头偏左就打向左侧，头偏右就打向右侧；纵向会跟随“相对平视基准”的头部上下姿态，抬头时光束上移，低头时光束下移。程序会自动捕捉首次有效人脸作为平视基准，也可以按 `C` 用当前头部姿态重新设定平视。

## 安装

双击工作区根目录下的：

```text
install_multimodal_deps.bat
```

安装脚本会创建独立的 `multimodal_recognition/.venv`，不会修改地面站和语音识别环境。首次启动识别器时会自动下载官方 MediaPipe Tasks 模型。

也可以手动执行：

```powershell
python -m pip install -r multimodal_recognition\requirements.txt
```

## 启动

手势：

```powershell
python multimodal_recognition\gesture_three.py --rotate 0 --min-confidence 0.65
```

目视：

```powershell
python multimodal_recognition\gaze_three_point.py --rotate 0 --min-confidence 0.62 --head-priority 0.72 --laser --laser-base-offset 0.02 --laser-vertical-scale 8.0
```

也可以双击：

```text
run_gesture_recognition.bat
run_gaze_recognition.bat
```

两个程序都使用 `Q` 或 `Esc` 退出。目视程序使用 `R` 重新校准。

## 摄像头方向

启动脚本通过 `--rotate` 适配摄像头横竖方向不一致的问题。

如果画面旋转方向反了，把启动脚本里的 `--rotate 90` 改成 `--rotate 270`。如果摄像头本来就是正的，改成 `--rotate 0`。

当前这台机器的脚本已调成 `--rotate 0`。如果换摄像头或换电脑后方向不对，再按实际画面调整。

## 窗口提示含义

- `Raw`：当前帧识别结果，低于置信度阈值会显示 `Unknown`。
- `Stable`：多帧稳定后的结果，只有稳定达到保持时间才会触发。
- `TRIGGER`：一次有效触发结果，默认约 3 秒后自动隐藏。
- 绿色点和橙色线：MediaPipe 检测到的手部关键点和骨架。

## 使用条件

- 操作者应位于摄像头正前方；
- 手势尽量在胸口到肩部高度展示，避免手掌过小；
- 目视识别时摄像头尽量靠近屏幕上边缘中央；
- 目视校准和使用期间保持坐姿、屏幕距离与摄像头位置稳定；
- 眼镜反光、侧脸、眯眼和强逆光会降低目视识别可靠性。

校准结果保存在 `gaze_calibration.json`。换人、换摄像头位置或换屏幕后建议按 `R` 重新校准。
