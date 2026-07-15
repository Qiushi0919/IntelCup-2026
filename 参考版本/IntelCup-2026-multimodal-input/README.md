# Intel Cup 2026 · 多模态输入原型

当前分支：`multimodal-input`

这个分支主要维护两个独立识别功能，暂时只做识别展示，不直接接入无人机控制链路。

## 功能一：三手势识别

<img height="520" alt="68009a9a2b05ae38c17867f378dd17cf" src="https://github.com/user-attachments/assets/5ff89fac-7f15-4823-a2e9-80fd48256849" />


启动：

```text
run_gesture_recognition.bat
```

支持三种手势：

- 张开手掌：`Open Palm`
- 握拳：`Fist`
- 竖大拇指：`Thumb Up`

特点：

- 使用 MediaPipe 手部关键点识别；
- 优先采用官方手势分类结果；
- 当分类器不稳定时，使用 21 个手部骨架点进行几何兜底判断；
- 默认置信度阈值为 `0.65`；
- 窗口会显示 `Raw`、`Stable` 和 `TRIGGER`，便于调试稳定触发效果。

## 功能二：头部姿态 + 视线融合识别

<img height="520" alt="image" src="https://github.com/user-attachments/assets/f15f6d1e-a674-41ec-89ec-dbfcbd6a4da8" />


启动：

```text
run_gaze_recognition.bat
```

支持识别：

- 头偏左 / 视线偏左：`LEFT`
- 正脸 / 居中：`CENTER`
- 头偏右 / 视线偏右：`RIGHT`
- 点头：`CONFIRM`
- 摇头：`CANCEL`

特点：

- 头部姿态是主信号，眼睛视线作为辅助信号；
- 眼睛识别不到时，仍可依靠头部姿态输出方向；
- 红色“眼部激光”会跟随最终头部/视线融合结果；
- 激光横向跟随 `LEFT / CENTER / RIGHT`；
- 激光纵向跟随相对平视基准，启动后会自动捕捉首次有效人脸作为平视姿态；
- 如平视基准不准，可按 `C` 用当前头部姿态重新设定平视；
- 目视三点校准可按 `R` 重置。

当前默认参数：

```text
--rotate 0 --min-confidence 0.62 --head-priority 0.72 --laser --laser-base-offset 0.02 --laser-vertical-scale 8.0
```

如果激光仍然偏低，可以继续降低 `--laser-base-offset`；如果上下跟随不够明显，可以提高 `--laser-vertical-scale`。

## 安装依赖

首次使用请双击：

```text
install_multimodal_deps.bat
```

该脚本会创建独立虚拟环境：

```text
multimodal_recognition/.venv
```

并安装 MediaPipe 与 OpenCV。首次启动识别器时会自动下载所需模型文件。

## 目录说明

```text
multimodal_recognition/   多模态识别核心代码
run_gesture_recognition.bat
run_gaze_recognition.bat
install_multimodal_deps.bat
```

地面站主程序、语音识别和无人机代码仍保留在其它分支或目录中，本分支重点用于手势与头部/视线输入方案验证。
