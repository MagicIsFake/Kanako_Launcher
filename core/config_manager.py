# core/config_manager.py
import os
import json
import minecraft_launcher_lib
from constants import DEFAULT_JVM_ARGS

class ConfigManager:
    def __init__(self):
        self.default_minecraft_dir = minecraft_launcher_lib.utils.get_minecraft_directory()
        self.config_file = os.path.join(self.default_minecraft_dir, "launcher_profiles_custom.json")
        self.config = {}
        self.load_profiles()

    def _default_profile_data(self):
        return {
            "name": "Default",
            "username": "",
            "remember": False,
            "version": "1.20.1",
            "game_dir": self.default_minecraft_dir,
            "jvm_args": DEFAULT_JVM_ARGS,
            "java_path": "",           
            "java_manual": False,      
            "allow_snapshots": False,
            "allow_beta": False,
            "allow_alpha": False,
        }

    def _default_config(self):
        prof = self._default_profile_data()
        prof["name"] = "Default"
        return {
            "current_profile": "Default",
            "profiles": {"Default": prof},
        }

    def load_profiles(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                defaults = self._default_profile_data()
                for prof in self.config.get("profiles", {}).values():
                    for key, val in defaults.items():
                        prof.setdefault(key, val)
                return
            except (json.JSONDecodeError, KeyError, TypeError):
                print("[Warning] Config file corrupted — resetting to default.")
        self.config = self._default_config()

    def save_profiles(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except OSError as e:
            print(f"[Error] Could not save profiles: {e}")

    def get_current_profile_name(self):
        return self.config.get("current_profile", "Default")

    def set_current_profile_name(self, name):
        self.config["current_profile"] = name

    def get_profile(self, name):
        return self.config["profiles"].get(name)