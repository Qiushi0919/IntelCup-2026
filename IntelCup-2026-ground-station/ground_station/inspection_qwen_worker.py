from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent Qwen3-VL worker for ground station.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", default="GPU")
    parser.add_argument("--max-image-side", type=int, default=448)
    parser.add_argument("--max-new-tokens", type=int, default=48)
    parser.add_argument("--mock", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipe = None
    generation_config = None
    if not args.mock:
        try:
            import numpy as np
            import openvino as ov
            import openvino_genai as ov_genai
            from PIL import Image

            emit({"type": "status", "status": "loading", "message": "正在加载Qwen3-VL到GPU"})
            cache_dir = args.model / ".gpu_compile_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            pipe = ov_genai.VLMPipeline(
                str(args.model.resolve()),
                args.device,
                CACHE_DIR=str(cache_dir),
            )
            generation_config = pipe.get_generation_config()
            generation_config.max_new_tokens = args.max_new_tokens
            generation_config.do_sample = False
        except Exception as exc:
            emit(
                {
                    "type": "fatal",
                    "message": f"Qwen加载失败：{type(exc).__name__}: {exc}",
                }
            )
            return 2
    else:
        Image = None
        np = None
        ov = None

    emit(
        {
            "type": "status",
            "status": "ready",
            "message": "Qwen3-VL GPU已就绪" if not args.mock else "Qwen模拟工作进程已就绪",
        }
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            request_id = str(request["request_id"])
            image_path = Path(request["image_path"])
            prompt = str(request["prompt"])
        except Exception as exc:
            emit({"type": "error", "request_id": "", "message": f"请求格式错误：{exc}"})
            continue

        started = time.perf_counter()
        try:
            if args.mock:
                time.sleep(0.15)
                text = "模拟分析：画面已完成巡检复核，未发现需要补充说明的高风险异常。"
            else:
                image = Image.open(image_path).convert("RGB")
                image.thumbnail(
                    (args.max_image_side, args.max_image_side),
                    Image.Resampling.LANCZOS,
                )
                image_array = np.asarray(image, dtype=np.uint8)[None, ...]
                result = pipe.generate(prompt, ov.Tensor(image_array), generation_config)
                text = result.texts[0].strip() if result.texts else "模型未返回文字结果。"
            emit(
                {
                    "type": "result",
                    "request_id": request_id,
                    "text": text,
                    "elapsed_s": round(time.perf_counter() - started, 3),
                }
            )
        except Exception as exc:
            emit(
                {
                    "type": "error",
                    "request_id": request_id,
                    "message": f"Qwen分析失败：{type(exc).__name__}: {exc}",
                    "elapsed_s": round(time.perf_counter() - started, 3),
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
