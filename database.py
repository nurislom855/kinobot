import json
import os

DATA_FILE = "data.json"

def _load():
    if not os.path.exists(DATA_FILE):
        _save({"channels": [], "movies": {}, "users": []})
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Database:
    def get_channels(self):
        return _load().get("channels", [])

    def add_channel(self, username, name):
        data = _load()
        for ch in data["channels"]:
            if ch["username"] == username:
                return False
        data["channels"].append({"username": username, "name": name})
        _save(data)
        return True

    def remove_channel(self, username):
        data = _load()
        data["channels"] = [c for c in data["channels"] if c["username"] != username]
        _save(data)
        return True

    def get_all_movies(self):
        return list(_load().get("movies", {}).values())

    def get_movie_by_code(self, code):
        return _load().get("movies", {}).get(code.upper())

    def add_movie(self, code, name, description, file_id):
        data = _load()
        code = code.upper()
        data["movies"][code] = {
            "code": code,
            "name": name,
            "description": description,
            "file_id": file_id
        }
        _save(data)
        return True

    def remove_movie(self, code):
        data = _load()
        code = code.upper()
        if code in data["movies"]:
            del data["movies"][code]
            _save(data)
            return True
        return False

    def add_user(self, user_id):
        data = _load()
        if user_id not in data["users"]:
            data["users"].append(user_id)
            _save(data)

    def get_all_users(self):
        return _load().get("users", [])

    def get_stats(self):
        data = _load()
        return {
            "users": len(data.get("users", [])),
            "movies": len(data.get("movies", {})),
            "channels": len(data.get("channels", []))
        }

db = Database()
