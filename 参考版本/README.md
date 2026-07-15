# IntelCup-2026 Workspace

这个文件夹把 IntelCup 相关内容集中放在一起：

- `IntelCup-2026/`：文档分支。
- `IntelCup-2026-ground-station/`：地面站、图传、火源识别和语音识别入口。
- `IntelCup-2026-aircraft-code/`：飞机代码与原始开发资料。
- `Intel项目/`：原始语音识别程序备份。

## 运行地面站

双击当前目录下的 `启动地面站.bat`。

## 语音识别

语音识别代码已经复制到：

```text
IntelCup-2026-ground-station/voice_asr/
```

地面站左侧“语音交互”窗口里可以启动或停止实时语音识别。首次使用前如缺少 OpenVINO、Transformers、Torch 等依赖，双击：

```text
IntelCup-2026-ground-station/install_voice_asr_deps.bat
```

首次运行 Whisper/OpenVINO 模型时会从 Hugging Face 下载模型，时间会比较长。
