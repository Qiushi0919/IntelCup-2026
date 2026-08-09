try:
    import ujson as json
except ImportError:
    import json


DEFAULT_PATH = "/sdcard/configs/gimbal_lab_thresholds.json"
MAX_THRESHOLDS = 30


class ThresholdStore:
    """Persistent named LAB thresholds."""

    def __init__(self, path=DEFAULT_PATH):
        self.path = path

    def load(self):
        try:
            with open(self.path, "r") as file:
                raw = json.load(file)
        except Exception:
            return []
        if not isinstance(raw, list):
            return []

        result = []
        for item in raw:
            try:
                values = [int(value) for value in item["values"]]
                if len(values) != 6:
                    continue
                values[0] = max(0, min(100, values[0]))
                values[1] = max(0, min(100, values[1]))
                for index in range(2, 6):
                    values[index] = max(-128, min(127, values[index]))
                result.append({
                    "id": int(item["id"]),
                    "name": str(item["name"]),
                    "values": values,
                })
            except Exception:
                pass
        return result[:MAX_THRESHOLDS]

    def save_all(self, thresholds):
        try:
            with open(self.path, "w") as file:
                json.dump(thresholds, file)
            return True
        except Exception as exc:
            print("save LAB thresholds:", exc)
            return False

    def add(self, values):
        thresholds = self.load()
        if len(thresholds) >= MAX_THRESHOLDS:
            return False
        next_id = 1
        if thresholds:
            next_id = max(item["id"] for item in thresholds) + 1
        item = {
            "id": next_id,
            "name": "阈值{}".format(next_id),
            "values": [int(value) for value in values],
        }
        thresholds.append(item)
        if self.save_all(thresholds):
            return item
        return False

    def delete(self, threshold_id):
        thresholds = self.load()
        filtered = [item for item in thresholds if item["id"] != threshold_id]
        if len(filtered) == len(thresholds):
            return False
        return self.save_all(filtered)
