# OpenVINO Whisper-large-v3 实时语音识别（Intel GPU）

本项目在 conda 环境 `gluon` 中运行：使用 **OpenVINO** 在 **Intel DK-2500（Intel® Graphics）GPU** 上加载 `OpenVINO/whisper-large-v3-int4-ov`，从麦克风实时采集音频，通过 **VAD 自动分段**并输出中文转写。

## 1. 环境准备（gluon）

在 Anaconda Prompt（或你配置的 PowerShell）中：

```bash
conda activate gluon
```

建议使用 Python 3.10/3.11。

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

说明：
- 本脚本用的是 **OpenVINO + Optimum Intel** 的 OpenVINO IR 模型，不依赖 CUDA。
- `torch` 在这里主要作为 `transformers.generate()` 的张量接口依赖（即使推理跑在 OpenVINO GPU 上也常会需要它）。

## 3. 运行（实时 + VAD 自动分段）

先列出音频输入设备：

```bash
python asr_realtime_openvino.py --list-devices
```

选择一个输入设备并运行（推荐显式指定 OpenVINO 设备为 GPU）：

```bash
python asr_realtime_openvino.py --device 0 --ov-device GPU
```

首次运行会从 Hugging Face 拉取模型（体积较大），请确保网络可用；后续会走本机缓存。

常用参数：
- `--vad-aggressiveness 0..3`：越大越“苛刻”（更容易把噪声判为静音）。
- `--silence-ms`：连续静音多久就结束当前语音段。
- `--min-speech-ms`：太短的段会被丢弃（减少误触发）。
- `--max-segment-s`：单段最长秒数（避免一直不切段）。
- `--min-rms`：低于该能量阈值的语音段直接跳过解码（抑制静默幻听）。
- `--suppress-text`：逗号分隔的短语黑名单（做归一化后比对并抑制输出，默认含 `谢谢大家`）。
- `--task transcribe|translate`：默认 `transcribe`。
- `--language zh`：本任务固定中文。
- `--save-jsonl out.jsonl`：把每段结果追加写入 JSONL。

## 4. GPU 校验与排查

脚本启动时会：
- 打印 `openvino.Core().available_devices`
- 选择你传入的 `--ov-device`（默认 `GPU`）

如果看不到 `GPU` 或报错：
- **驱动/运行时**：确认 Intel GPU 驱动与 OpenVINO 运行时已正确安装。
- **设备名**：有些环境里 GPU 设备名可能是 `GPU.0`，可尝试 `--ov-device GPU.0`。
- **先 CPU 验证功能**：`--ov-device CPU`，确认流程跑通后再回到 GPU 排查。

## 5. Windows 音频常见问题

如果 `--list-devices` 报错或看不到麦克风：
- **先确认系统录音权限**：Windows 设置里允许应用访问麦克风。
- **换一个 host API/设备**：设备列表里不同输入设备可能对应不同 host API。
- **用更保守的 VAD 参数**：例如 `--vad-aggressiveness 3 --min-speech-ms 500 --silence-ms 700`，降低环境噪声误触发。

如果你这台机器上 `sounddevice` 不好用（驱动/host API 兼容性问题），可以按同样的 CLI 约定把采集层替换为 PyAudio（项目目前默认未内置该分支，避免引入额外编译依赖）。

## 5. 输出形态

控制台按段输出，例如：

```
[segment=3][t=12.34s..15.02s][audio=2.68s][infer=0.91s] 你好，我在测试实时语音识别
```

