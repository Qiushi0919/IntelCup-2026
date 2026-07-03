"""
实时语音识别（ASR）示例：
1) 从麦克风持续采集音频
2) 使用 WebRTC VAD 检测“有语音/无语音”
3) 把一段完整语音送入 OpenVINO 版 Whisper 做识别
4) 打印结果，并可选追加写入 JSONL 文件

这份脚本重点是“边听边识别”，而不是一次性识别整段音频文件。
"""

import argparse
import json
import re
import queue
import sys
import time
from dataclasses import dataclass
from typing import Deque, Iterable, Optional, Tuple

import numpy as np


def _lazy_import_audio():
    # 延迟导入：只有真正需要音频输入时才加载依赖，
    # 避免用户只运行 --help 或 --list-devices 时也必须安装全部包。
    import sounddevice as sd  # noqa: F401


def _lazy_import_vad():
    # 延迟导入 VAD 依赖，减少启动时的强耦合。
    import webrtcvad  # noqa: F401


def _lazy_import_openvino():
    # 延迟导入 OpenVINO，只有检查设备或加载模型时才需要。
    import openvino  # noqa: F401


def _lazy_import_hf():
    # 延迟导入 HuggingFace + Optimum 组件，避免无关场景的导入开销。
    import torch  # noqa: F401
    from optimum.intel.openvino import OVModelForSpeechSeq2Seq  # noqa: F401
    from transformers import AutoProcessor  # noqa: F401


def list_input_devices() -> None:
    """列出当前机器可用的录音设备（仅输入设备）。"""
    _lazy_import_audio()
    import sounddevice as sd

    devices = sd.query_devices()
    print("=== sounddevice devices ===")
    for idx, d in enumerate(devices):
        if int(d.get("max_input_channels", 0)) > 0:
            name = d.get("name", "")
            hostapi = d.get("hostapi", None)
            print(f"[{idx}] {name} (hostapi={hostapi}) max_input_channels={d.get('max_input_channels')}")


def ov_available_devices() -> Tuple[str, ...]:
    """返回 OpenVINO 可见设备列表，例如 ('CPU', 'GPU.0')。"""
    _lazy_import_openvino()
    from openvino import Core

    core = Core()
    devs = tuple(core.available_devices)
    return devs


@dataclass
class VadConfig:
    """VAD（语音活动检测）参数配置。"""

    sample_rate: int = 16000
    frame_ms: int = 20  # must be 10/20/30 for webrtcvad
    aggressiveness: int = 2  # 0..3
    min_speech_ms: int = 500
    silence_ms: int = 500
    max_segment_s: float = 15.0

    @property
    def frame_samples(self) -> int:
        """每帧包含多少采样点。"""
        return int(self.sample_rate * self.frame_ms / 1000)

    @property
    def frame_bytes(self) -> int:
        """每帧占用多少字节（int16 单声道 = 每采样 2 字节）。"""
        return self.frame_samples * 2  # int16 mono


class MicPcmStream:
    """
    Capture audio from microphone using sounddevice and expose as PCM16 bytes.
    """

    def __init__(self, device: Optional[int], sample_rate: int, block_samples: int):
        # 这里使用 sounddevice 的回调流模式：
        # 声卡每得到一块数据就触发 _callback，把数据放入队列。
        _lazy_import_audio()
        import sounddevice as sd

        self._sd = sd
        self._q: "queue.Queue[bytes]" = queue.Queue()
        self.sample_rate = sample_rate
        self.block_samples = block_samples
        self.device = device

        def _callback(indata, frames, time_info, status):
            # 回调是由 sounddevice 在线程中持续调用的。
            # indata 的 dtype 是 float32，范围通常在 [-1, 1]。
            if status:
                # Keep going; status is common on Windows depending on host API.
                pass
            x = indata.reshape(-1)
            # 防御性裁剪：避免偶发超范围导致 int16 溢出。
            x = np.clip(x, -1.0, 1.0)
            # 把 float32（-1~1）映射为 int16 PCM（-32768~32767）。
            pcm16 = (x * 32767.0).astype(np.int16)
            # 放入线程安全队列，主线程再从队列消费。
            self._q.put(pcm16.tobytes())

        self._stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=block_samples,
            device=device,
            callback=_callback,
        )

    def __enter__(self):
        # 支持 with 语法：进入上下文时启动录音流。
        self._stream.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        # 退出上下文时确保资源释放，避免设备被占用。
        try:
            self._stream.stop()
        finally:
            self._stream.close()

    def iter_pcm16(self) -> Iterable[bytes]:
        # 无限生成器：不断返回新的 PCM16 音频块。
        while True:
            yield self._q.get()


class VadSegmenter:
    """
    把连续 PCM 音频流切成“语音段”。

    核心逻辑：
    - 连续若干帧被判定为 speech -> 进入说话状态
    - 说话状态中累计静音达到阈值 -> 结束该段并产出
    - 同时设置最大段长，防止长时间不切段
    """

    def __init__(self, cfg: VadConfig):
        _lazy_import_vad()
        import webrtcvad

        if cfg.frame_ms not in (10, 20, 30):
            raise ValueError("frame_ms must be 10, 20, or 30 for webrtcvad")
        if not (0 <= cfg.aggressiveness <= 3):
            raise ValueError("vad aggressiveness must be 0..3")

        self.cfg = cfg
        self.vad = webrtcvad.Vad(cfg.aggressiveness)

        self._pcm_buf = bytearray()
        self._segment_buf = bytearray()
        self._in_speech = False
        self._segment_start_t: Optional[float] = None

        self._voiced_ms = 0
        self._silence_ms = 0

    def _frames_from_buffer(self) -> Iterable[bytes]:
        # 由于外部 push 进来的块大小不固定，先累积到 _pcm_buf，
        # 再按 frame_bytes 切成 VAD 所需固定帧长。
        fb = self.cfg.frame_bytes
        while len(self._pcm_buf) >= fb:
            frame = bytes(self._pcm_buf[:fb])
            del self._pcm_buf[:fb]
            yield frame

    def push_pcm16(self, pcm16_bytes: bytes, now_s: float) -> Iterable[Tuple[bytes, float, float]]:
        """
        Feed PCM16 bytes. Yield completed segments as (segment_pcm16_bytes, start_t, end_t).
        Times are wall-clock seconds from process start (monotonic reference).
        """
        # 新来的原始字节先并入内部缓冲区。
        self._pcm_buf.extend(pcm16_bytes)

        for frame in self._frames_from_buffer():
            # 对每一帧做语音活动检测（True 表示更像人在说话）。
            is_speech = self.vad.is_speech(frame, self.cfg.sample_rate)
            if is_speech:
                if not self._in_speech:
                    # 从“静音”切换到“说话”：开启新段。
                    self._in_speech = True
                    self._segment_start_t = now_s
                    self._segment_buf.clear()
                    self._voiced_ms = 0
                    self._silence_ms = 0
                self._voiced_ms += self.cfg.frame_ms
                self._silence_ms = 0
                self._segment_buf.extend(frame)
            else:
                if self._in_speech:
                    # 说话中遇到静音：先累计静音，再判断是否该截断。
                    self._silence_ms += self.cfg.frame_ms
                    self._segment_buf.extend(frame)  # keep a bit of tail silence

                    seg_dur_s = len(self._segment_buf) / 2 / self.cfg.sample_rate
                    hit_silence = self._silence_ms >= self.cfg.silence_ms
                    hit_max = seg_dur_s >= self.cfg.max_segment_s
                    if hit_silence or hit_max:
                        start_t = self._segment_start_t if self._segment_start_t is not None else now_s
                        end_t = now_s
                        seg = bytes(self._segment_buf)
                        # 注意：_reset 会清空 _voiced_ms，所以先保存旧值。
                        voiced_ms = self._voiced_ms
                        self._reset()
                        # 过滤过短语音（例如咳嗽、电流声、误触发）。
                        if voiced_ms >= self.cfg.min_speech_ms:
                            yield (seg, start_t, end_t)
                else:
                    # staying in silence
                    pass

    def flush(self, now_s: float) -> Iterable[Tuple[bytes, float, float]]:
        # 在程序结束时，把尚未闭合的一段语音“强制收尾”输出。
        if not self._in_speech:
            return []
        start_t = self._segment_start_t if self._segment_start_t is not None else now_s
        end_t = now_s
        seg = bytes(self._segment_buf)
        voiced_ms = self._voiced_ms
        self._reset()
        if voiced_ms >= self.cfg.min_speech_ms:
            return [(seg, start_t, end_t)]
        return []

    def _reset(self):
        # 重置为“等待下一段语音”的初始状态。
        self._in_speech = False
        self._segment_start_t = None
        self._segment_buf.clear()
        self._voiced_ms = 0
        self._silence_ms = 0


class WhisperOvAsr:
    """封装 OpenVINO Whisper 的加载与推理。"""

    def __init__(self, model_id: str, ov_device: str, language: str, task: str):
        _lazy_import_hf()
        from optimum.intel.openvino import OVModelForSpeechSeq2Seq
        from transformers import AutoProcessor

        self.model_id = model_id
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = OVModelForSpeechSeq2Seq.from_pretrained(model_id, device=ov_device)

        self.language = language
        self.task = task

        # 强制解码提示：可固定语言/任务（转写 or 翻译），
        # 让输出更稳定并减少错误语言漂移。
        self.forced_decoder_ids = None
        try:
            self.forced_decoder_ids = self.processor.get_decoder_prompt_ids(language=language, task=task)
        except Exception:
            self.forced_decoder_ids = None

    def transcribe(self, audio_16k: np.ndarray) -> str:
        # processor 负责把原始波形转换成模型输入特征（梅尔谱等）。
        inputs = self.processor(
            audio_16k,
            sampling_rate=16000,
            return_tensors="pt",
        )

        gen_kwargs = {}
        if self.forced_decoder_ids is not None:
            gen_kwargs["forced_decoder_ids"] = self.forced_decoder_ids

        # Whisper 是生成式解码，这里走 generate。
        outputs = self.model.generate(inputs.input_features, **gen_kwargs)
        text = self.processor.batch_decode(outputs, skip_special_tokens=True)[0]
        return text.strip()


def pcm16_bytes_to_float32(pcm16_bytes: bytes) -> np.ndarray:
    """把 PCM16 字节流转为 float32 波形数组（范围约 -1~1）。"""
    x = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return x


def audio_rms(audio_f32: np.ndarray) -> float:
    """计算音频均方根能量（RMS），用于过滤低能量噪声段。"""
    if audio_f32.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio_f32), dtype=np.float32)))


def normalize_text_for_filter(text: str) -> str:
    """
    对识别文本做轻量归一化，便于做“固定误识别短语”过滤。
    例如把空格和常见标点去掉后再比对。
    """
    return re.sub(r"[\s,，。.!！？?、；;：:\"'“”‘’]+", "", text).strip()


def main():
    # 1) 命令行参数定义
    parser = argparse.ArgumentParser(description="Real-time ASR with OpenVINO Whisper-large-v3 (VAD segmentation).")

    parser.add_argument("--list-devices", action="store_true", help="List audio input devices and exit.")
    parser.add_argument("--device", type=int, default=None, help="Audio input device index (sounddevice).")

    parser.add_argument("--model-id", type=str, default="OpenVINO/whisper-large-v3-int4-ov")
    parser.add_argument("--ov-device", type=str, default="GPU", help="OpenVINO device: GPU / GPU.0 / CPU ...")

    parser.add_argument("--language", type=str, default="zh", help="Whisper language (fixed for this task).")
    parser.add_argument("--task", type=str, default="transcribe", choices=["transcribe", "translate"])

    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--frame-ms", type=int, default=20, choices=[10, 20, 30])
    parser.add_argument("--vad-aggressiveness", type=int, default=2, choices=[0, 1, 2, 3])
    parser.add_argument("--min-speech-ms", type=int, default=300)
    parser.add_argument("--silence-ms", type=int, default=500)
    parser.add_argument("--max-segment-s", type=float, default=15.0)
    parser.add_argument(
        "--min-rms",
        type=float,
        default=0.008,
        help="Skip ASR on very low-energy segments (helps avoid silence hallucinations).",
    )
    parser.add_argument(
        "--suppress-text",
        type=str,
        default="谢谢大家",
        help="Comma-separated phrases to suppress from output after normalization.",
    )

    parser.add_argument("--save-jsonl", type=str, default=None, help="Append results to a JSONL file path.")

    # 2) 解析参数
    args = parser.parse_args()

    # 工具模式：只列设备，不启动主流程。
    if args.list_devices:
        list_input_devices()
        return

    # 当前脚本流程固定为 16kHz，以减少重采样带来的复杂度。
    if args.sample_rate != 16000:
        print("This script currently expects 16kHz end-to-end. Please use --sample-rate 16000.", file=sys.stderr)
        sys.exit(2)

    print("=== OpenVINO available devices ===")
    devs = ov_available_devices()
    print(", ".join(devs) if devs else "(none)")

    if args.ov_device not in devs and args.ov_device.split(".")[0] not in devs:
        print(
            f"WARNING: requested --ov-device={args.ov_device} not in available_devices. "
            "OpenVINO may still resolve it, but if it fails try --ov-device CPU or GPU.0",
            file=sys.stderr,
        )

    # 3) 加载 ASR 模型（通常最耗时的一步）
    print("Loading model...")
    asr = WhisperOvAsr(
        model_id=args.model_id,
        ov_device=args.ov_device,
        language=args.language,
        task=args.task,
    )
    print("Model loaded.")

    # 4) 初始化 VAD 分段器
    vad_cfg = VadConfig(
        sample_rate=args.sample_rate,
        frame_ms=args.frame_ms,
        aggressiveness=args.vad_aggressiveness,
        min_speech_ms=args.min_speech_ms,
        silence_ms=args.silence_ms,
        max_segment_s=args.max_segment_s,
    )
    segmenter = VadSegmenter(vad_cfg)

    # 麦克风回调每次读取约 200ms 音频：
    # 块太小会增加 Python 调度开销，块太大又会提高延迟。
    block_samples = vad_cfg.frame_samples * 10  # 200ms blocks -> lower overhead, still responsive
    t0 = time.perf_counter()

    segment_idx = 0
    print("Listening... (Ctrl+C to stop)")
    suppress_phrases = {
        normalize_text_for_filter(x)
        for x in args.suppress_text.split(",")
        if normalize_text_for_filter(x)
    }

    # 可选：把每条识别结果追加到 jsonl 文件，便于后续分析。
    jsonl_fp = None
    if args.save_jsonl:
        jsonl_fp = open(args.save_jsonl, "a", encoding="utf-8")

    try:
        # 5) 主循环：采集 -> 分段 -> 识别 -> 输出
        with MicPcmStream(device=args.device, sample_rate=vad_cfg.sample_rate, block_samples=block_samples) as mic:
            for pcm_chunk in mic.iter_pcm16():
                now = time.perf_counter() - t0
                for seg_pcm, seg_start, seg_end in segmenter.push_pcm16(pcm_chunk, now_s=now):
                    # 模型输入需要 float32 波形
                    audio_f32 = pcm16_bytes_to_float32(seg_pcm)
                    seg_rms = audio_rms(audio_f32)
                    # 低能量段大多是静音底噪，直接跳过可显著减少“谢谢大家”类幻听。
                    if seg_rms < args.min_rms:
                        continue

                    infer_t0 = time.perf_counter()
                    text = asr.transcribe(audio_f32)
                    infer_s = time.perf_counter() - infer_t0
                    norm_text = normalize_text_for_filter(text)
                    if not norm_text or norm_text in suppress_phrases:
                        continue
                    segment_idx += 1

                    # 计算该语音段的实际音频时长（秒）
                    audio_s = len(seg_pcm) / 2 / vad_cfg.sample_rate
                    print(
                        f"[segment={segment_idx}]"
                        f"[t={seg_start:.2f}s..{seg_end:.2f}s]"
                        f"[audio={audio_s:.2f}s]"
                        f"[infer={infer_s:.2f}s][rms={seg_rms:.4f}] {text}"
                    )

                    if jsonl_fp is not None:
                        # 记录结构化字段，方便后续做统计或回放。
                        rec = {
                            "segment": segment_idx,
                            "t_start_s": float(seg_start),
                            "t_end_s": float(seg_end),
                            "audio_s": float(audio_s),
                            "infer_s": float(infer_s),
                            "text": text,
                            "model_id": args.model_id,
                            "ov_device": args.ov_device,
                            "language": args.language,
                            "task": args.task,
                            "vad": {
                                "frame_ms": vad_cfg.frame_ms,
                                "aggressiveness": vad_cfg.aggressiveness,
                                "min_speech_ms": vad_cfg.min_speech_ms,
                                "silence_ms": vad_cfg.silence_ms,
                                "max_segment_s": vad_cfg.max_segment_s,
                            },
                        }
                        jsonl_fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        jsonl_fp.flush()
    except KeyboardInterrupt:
        # 用户 Ctrl+C 时静默退出，不打印长堆栈。
        pass
    finally:
        # 确保文件句柄关闭，避免数据未落盘。
        if jsonl_fp is not None:
            jsonl_fp.close()


if __name__ == "__main__":
    main()

