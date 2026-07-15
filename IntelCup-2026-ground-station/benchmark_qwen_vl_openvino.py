from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import openvino as ov
import openvino_genai as ov_genai
import psutil
from PIL import Image


def _metric_value(value: Any) -> Any:
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    fields = {}
    for name in ("mean", "std"):
        if hasattr(value, name):
            fields[name] = float(getattr(value, name))
    return fields or str(value)


def _collect_perf_metrics(result: Any) -> dict[str, Any]:
    perf = result.perf_metrics
    names = (
        "get_load_time",
        "get_num_input_tokens",
        "get_num_generated_tokens",
        "get_ttft",
        "get_tpot",
        "get_throughput",
        "get_generate_duration",
        "get_inference_duration",
    )
    values = {}
    for name in names:
        try:
            values[name.removeprefix("get_")] = _metric_value(getattr(perf, name)())
        except Exception as exc:  # Keep the benchmark usable across GenAI releases.
            values[name.removeprefix("get_")] = f"unavailable: {exc}"
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Qwen3-VL INT4 with OpenVINO GenAI.")
    parser.add_argument("model", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument("--device", choices=("CPU", "GPU", "NPU"), default="GPU")
    parser.add_argument("--prompt", default="请用一句中文概括这张图片，并指出最显眼的内容。")
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--max-image-side", type=int, default=448)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    model_dir = args.model.resolve()
    image_path = args.image.resolve()
    core = ov.Core()
    available_devices = list(core.available_devices)
    if args.device not in available_devices:
        raise SystemExit(f"{args.device} is unavailable; OpenVINO sees {available_devices}")

    process = psutil.Process(os.getpid())
    stop_sampling = threading.Event()
    samples: list[dict[str, float]] = []

    def sample_resources() -> None:
        process.cpu_percent(None)
        while not stop_sampling.wait(0.2):
            memory = psutil.virtual_memory()
            samples.append(
                {
                    "rss_bytes": float(process.memory_info().rss),
                    "cpu_percent": float(process.cpu_percent(None)),
                    "system_available_bytes": float(memory.available),
                }
            )

    sampler = threading.Thread(target=sample_resources, daemon=True)
    sampler.start()
    cpu_start = process.cpu_times()
    wall_start = time.perf_counter()

    properties: dict[str, str] = {}
    if args.device == "GPU":
        cache_dir = model_dir / ".gpu_compile_cache"
        cache_dir.mkdir(exist_ok=True)
        properties["CACHE_DIR"] = str(cache_dir)

    load_start = time.perf_counter()
    pipeline = ov_genai.VLMPipeline(str(model_dir), args.device, **properties)
    load_seconds = time.perf_counter() - load_start
    rss_after_load = process.memory_info().rss

    image = Image.open(image_path).convert("RGB")
    image.thumbnail((args.max_image_side, args.max_image_side), Image.Resampling.LANCZOS)
    image_array = np.asarray(image, dtype=np.uint8)[None, ...]
    image_tensor = ov.Tensor(image_array)

    generation_config = pipeline.get_generation_config()
    generation_config.max_new_tokens = args.max_new_tokens
    generation_config.do_sample = False

    generate_start = time.perf_counter()
    result = pipeline.generate(args.prompt, image_tensor, generation_config)
    generate_seconds = time.perf_counter() - generate_start

    stop_sampling.set()
    sampler.join(timeout=2)
    cpu_end = process.cpu_times()
    wall_seconds = time.perf_counter() - wall_start

    report = {
        "device": args.device,
        "available_devices": available_devices,
        "model_dir": str(model_dir),
        "model_size_bytes": sum(path.stat().st_size for path in model_dir.glob("*") if path.is_file()),
        "image": {
            "path": str(image_path),
            "width": image.width,
            "height": image.height,
        },
        "max_new_tokens": args.max_new_tokens,
        "load_seconds": load_seconds,
        "generate_seconds": generate_seconds,
        "wall_seconds": wall_seconds,
        "rss_after_load_bytes": rss_after_load,
        "peak_rss_bytes": max((sample["rss_bytes"] for sample in samples), default=float(rss_after_load)),
        "minimum_system_available_bytes": min(
            (sample["system_available_bytes"] for sample in samples),
            default=float(psutil.virtual_memory().available),
        ),
        "peak_process_cpu_percent": max((sample["cpu_percent"] for sample in samples), default=0.0),
        "process_cpu_seconds": (cpu_end.user + cpu_end.system) - (cpu_start.user + cpu_start.system),
        "perf_metrics": _collect_perf_metrics(result),
        "text": result.texts[0] if result.texts else "",
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
