try:
    import ujson as json
except ImportError:
    import json


DEFAULT_PATH = "/sdcard/configs/gimbal_positions.json"
MAX_POSITIONS = 20


class PositionStore:
    """Persistent ordered gimbal positions."""

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
        positions = []
        for item in raw:
            try:
                pan = int(item["pan"])
                tilt = int(item["tilt"])
                dwell = int(item.get("dwell", 1))
                if -6 <= pan <= 22 and -4 <= tilt <= 21:
                    positions.append({
                        "pan": pan,
                        "tilt": tilt,
                        "dwell": max(1, min(60, dwell)),
                    })
            except Exception:
                pass
        return positions[:MAX_POSITIONS]

    def save(self, positions):
        try:
            with open(self.path, "w") as file:
                json.dump(positions, file)
            return True
        except Exception as exc:
            print("save gimbal positions:", exc)
            return False

    def add(self, pan, tilt, dwell=1):
        positions = self.load()
        if len(positions) >= MAX_POSITIONS:
            return False
        positions.append({
            "pan": int(pan),
            "tilt": int(tilt),
            "dwell": max(1, min(60, int(dwell))),
        })
        return self.save(positions)

    def delete(self, index):
        positions = self.load()
        if index < 0 or index >= len(positions):
            return False
        positions.pop(index)
        return self.save(positions)

    def set_dwell(self, index, seconds):
        positions = self.load()
        if index < 0 or index >= len(positions):
            return False
        positions[index]["dwell"] = max(1, min(60, int(seconds)))
        return self.save(positions)

    def move(self, index, offset):
        positions = self.load()
        new_index = index + offset
        if index < 0 or index >= len(positions):
            return False
        if new_index < 0 or new_index >= len(positions):
            return False
        item = positions.pop(index)
        positions.insert(new_index, item)
        return self.save(positions)
