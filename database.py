import json
import os
from typing import Optional

DATA_FILE = "data.json"


def _load() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"channels": [], "movies": {}, "users": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Database:

    # ─── KANALLAR ───

    def get_channels(self) -> list:
        return _load().get("channels", [])

    def add_channel(self, username: str, name: str) -> bool:
        data = _load()
        for ch in data["channels"]:
            if ch["username"] == username:
                return False
        data["channels"].append({"username": username, "name": name})
        _save(data)
        return True

    def remove_channel(self, username: str) -> bool:
        data = _load()
        before = len(data["channels"])
        data["channels"] = [c for c in data["channels"] if c["username"] != username]
        if len(data["channels"]) < before:
            _save(data)
            return True
        return False

    # ─── KINOLAR ───

    def get_all_movies(self) -> list:
        movies = _load().get("movies", {})
        return list(movies.values())

    def get_movie_by_code(self, code: str) -> Optional[dict]:
        movies = _load().get("movies", {})
        return movies.get(code.upper())

    def add_movie(self, code: str, name: str, description: str, file_id: str) -> bool:
        data = _load()
        code = code.upper()
        if code in data["movies"]:
            return False
        data["movies"][code] = {
            "code": code,
            "name": name,
            "description": description,
            "file_id": file_id
        }
        _save(data)
        return True

    def remove_movie(self, code: str) -> bool:
        data = _load()
        code = code.upper()
        if code in data["movies"]:
            del data["movies"][code]
            _save(data)
            return True
        return False

    # ─── FOYDALANUVCHILAR ───

    def add_user(self, user_id: int):
        data = _load()
        if user_id not in data["users"]:
            data["users"].append(user_id)
            _save(data)

    def get_all_users(self) -> list:
        return _load().get("users", [])

    # ─── STATISTIKA ───

    def get_stats(self) -> dict:
        data = _load()
        return {
            "users": len(data.get("users", [])),
            "movies": len(data.get("movies", {})),
            "channels": len(data.get("channels", []))
        }


db = Database()
