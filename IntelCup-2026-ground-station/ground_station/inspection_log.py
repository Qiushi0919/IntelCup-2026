from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2


class InspectionLogStore:
    """Append-only local journal for detector and Qwen-VL inspection events."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.image_root = root / "images"
        self.jsonl_path = root / "inspection_log.jsonl"
        self.markdown_path = root / "inspection_log.md"
        self.root.mkdir(parents=True, exist_ok=True)
        self.image_root.mkdir(parents=True, exist_ok=True)
        self._ensure_markdown_header()

    def create_entry(
        self,
        kind: str,
        trigger: str,
        summary: str,
        frame,
        flight_state: dict[str, Any],
        detections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now()
        event_id = now.strftime("%Y%m%d_%H%M%S_%f")
        screenshot = self._save_frame(event_id, now, frame)
        entry = {
            "id": event_id,
            "timestamp": now.isoformat(timespec="seconds"),
            "kind": kind,
            "trigger": trigger,
            "summary": summary,
            "flight_state": dict(flight_state),
            "detections": list(detections or []),
            "screenshot": str(screenshot) if screenshot else "",
            "qwen_status": "排队中",
            "qwen_analysis": "",
            "qwen_elapsed_s": 0.0,
        }
        self._append_json({"record_type": "event", "entry": entry})
        self._append_markdown_event(entry)
        return entry

    def update_analysis(
        self,
        entry: dict[str, Any],
        analysis: str,
        elapsed_s: float = 0.0,
        error: str = "",
    ) -> dict[str, Any]:
        updated = dict(entry)
        if error:
            updated["qwen_status"] = "分析失败"
            updated["qwen_analysis"] = error
        else:
            updated["qwen_status"] = "分析完成"
            updated["qwen_analysis"] = analysis.strip()
        updated["qwen_elapsed_s"] = round(float(elapsed_s), 3)
        self._append_json(
            {
                "record_type": "analysis",
                "id": updated["id"],
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "qwen_status": updated["qwen_status"],
                "qwen_analysis": updated["qwen_analysis"],
                "qwen_elapsed_s": updated["qwen_elapsed_s"],
            }
        )
        self._append_markdown_analysis(updated)
        return updated

    def load_entries(self, limit: int = 60) -> list[dict[str, Any]]:
        if not self.jsonl_path.exists():
            return []
        ordered_ids: list[str] = []
        entries: dict[str, dict[str, Any]] = {}
        try:
            lines = self.jsonl_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        for line in lines:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if record.get("record_type") == "event":
                entry = record.get("entry")
                if not isinstance(entry, dict) or not entry.get("id"):
                    continue
                event_id = str(entry["id"])
                entries[event_id] = entry
                ordered_ids.append(event_id)
            elif record.get("record_type") == "analysis":
                event_id = str(record.get("id", ""))
                if event_id not in entries:
                    continue
                for key in ("qwen_status", "qwen_analysis", "qwen_elapsed_s"):
                    if key in record:
                        entries[event_id][key] = record[key]
        selected = ordered_ids[-max(1, int(limit)) :]
        return [entries[event_id] for event_id in selected if event_id in entries]

    def _save_frame(self, event_id: str, now: datetime, frame) -> Path | None:
        if frame is None:
            return None
        day_dir = self.image_root / now.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        path = day_dir / f"inspection_{event_id}.jpg"
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            return None
        encoded.tofile(str(path))
        return path.resolve()

    def _append_json(self, record: dict[str, Any]) -> None:
        with self.jsonl_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _ensure_markdown_header(self) -> None:
        if self.markdown_path.exists() and self.markdown_path.stat().st_size > 0:
            return
        self.markdown_path.write_text(
            "# 无人机飞行巡检记录\n\n"
            "> 本文件由地面站持续追加。完整结构化数据见 inspection_log.jsonl。\n\n",
            encoding="utf-8",
        )

    def _append_markdown_event(self, entry: dict[str, Any]) -> None:
        state = entry.get("flight_state", {})
        screenshot = Path(entry["screenshot"]) if entry.get("screenshot") else None
        relative_image = ""
        if screenshot is not None:
            try:
                relative_image = screenshot.relative_to(self.root).as_posix()
            except ValueError:
                relative_image = screenshot.as_posix()
        lines = [
            f"## {entry['timestamp']} · {entry['kind']}",
            "",
            f"- 触发方式：{entry['trigger']}",
            f"- 识别结果：{self._markdown_safe(entry['summary'])}",
            "- 飞行状态："
            f"X {float(state.get('x', 0.0)):.1f} cm，"
            f"Y {float(state.get('y', 0.0)):.1f} cm，"
            f"高度 {float(state.get('altitude', 0.0)):.2f} m，"
            f"航向 {float(state.get('yaw', 0.0)):.1f}°，"
            f"阶段 {state.get('flight_phase', '未知')}",
            "- Qwen-VL：排队中",
            "",
        ]
        if relative_image:
            lines += [f"![巡检截图]({relative_image})", ""]
        self._append_markdown(lines)

    def _append_markdown_analysis(self, entry: dict[str, Any]) -> None:
        elapsed = float(entry.get("qwen_elapsed_s", 0.0))
        lines = [
            f"### Qwen-VL 更新 · {entry['id']}",
            "",
            f"- 状态：{entry.get('qwen_status', '未知')}",
            f"- 耗时：{elapsed:.2f} 秒",
            f"- 分析：{self._markdown_safe(entry.get('qwen_analysis', ''))}",
            "",
        ]
        self._append_markdown(lines)

    def _append_markdown(self, lines: list[str]) -> None:
        with self.markdown_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(lines) + "\n")

    @staticmethod
    def _markdown_safe(value: Any) -> str:
        return str(value).replace("|", "/").replace("\r", " ").replace("\n", " ")
