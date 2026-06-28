# core/game_runner.py
import os
import re
import shutil
import uuid
import json
import platform
import subprocess
import traceback
import minecraft_launcher_lib
from constants import JAVA_PATHS
from core.patches import _normalize_arg_item


def java_major_for_version(version_str: str) -> int:
    try:
        match = re.search(r'\b1\.(\d+)(?:\.(\d+))?\b', version_str)
        if match:
            minor = int(match.group(1))
            patch = int(match.group(2)) if match.group(2) else 0
            v = (1, minor, patch)
            if v <= (1, 16, 5): return 8
            elif v < (1, 20, 5): return 17
            else: return 21
    except Exception:
        pass
    return 21


def get_suitable_java(version_str: str, prof_data: dict) -> str:
    if prof_data.get("java_manual") and prof_data.get("java_path"):
        manual = prof_data["java_path"].strip()
        if manual:
            return manual

    java_major = java_major_for_version(version_str)
    hardcoded = JAVA_PATHS.get(java_major, JAVA_PATHS[21])
    if os.path.exists(hardcoded):
        return hardcoded

    fallback = shutil.which("java")
    return fallback if fallback else hardcoded


def sanitize_version_json(version: str, minecraft_dir: str):
    """Scan and fix mod-loader argument quirks inside a .minecraft directory."""
    json_path = os.path.join(minecraft_dir, "versions", version, f"{version}.json")
    if not os.path.exists(json_path):
        return
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        modified = False
        if "arguments" in data:
            for arg_type in ("jvm", "game"):
                args_list = data["arguments"].get(arg_type)
                if not isinstance(args_list, list):
                    continue
                cleaned = [_normalize_arg_item(i) for i in args_list]
                if any(c != o for c, o in zip(cleaned, args_list)):
                    data["arguments"][arg_type] = cleaned
                    modified = True

        if modified:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[JSON Scan] Error: {e}")


def _bootstrap_minecraft_dir(minecraft_dir: str):
    """
    Pre-create the sub-folders Minecraft expects inside a .minecraft directory.

    Minecraft writes into these paths relative to --gameDir.  If they do not
    exist on first launch, some versions (especially modded ones) silently
    fall back to the OS-default location (%APPDATA%\\.minecraft on Windows).
    Creating them here guarantees the game stays inside its own directory.
    """
    subdirs = [
        "saves", "resourcepacks", "shaderpacks",
        "mods", "config", "screenshots", "logs", "crash-reports",
    ]
    for sub in subdirs:
        os.makedirs(os.path.join(minecraft_dir, sub), exist_ok=True)


def run_launch_process(username: str, current_prof: dict,
                       status_cb, progress_cb, btn_cb, success_cb,
                       sanitized_versions: set, log_cb=None, post_install_cb=None):
    """
    Launch Minecraft in fully self-contained, per-profile mode.

    Architecture
    ────────────
    Each profile owns one directory that acts as a complete, independent
    .minecraft folder — it holds versions, assets, libraries, saves, mods,
    resourcepacks, and options.txt all in one place.

    profile["game_dir"]  IS  the .minecraft dir for that profile.
    It is passed as BOTH:
        • the minecraft_dir argument to install_minecraft_version()
          → so versions/assets/libraries are downloaded there
        • the minecraft_dir argument to get_minecraft_command()
          → so the JVM classpath resolves from there
        • the "gameDirectory" option
          → so --gameDir points there and all runtime writes land there

    This means every profile is 100 % self-sufficient and completely
    independent of every other profile and of %APPDATA%\\.minecraft.

    Special case — Default profile
    ──────────────────────────────
    The Default profile's game_dir is initialised to the OS-default Minecraft
    directory (%APPDATA%\\.minecraft on Windows).  This lets users who already
    have Mojang's launcher installed pick up their existing worlds and mods
    immediately without any configuration.  If they later point it at a
    different folder it becomes just as independent as any other profile.
    """
    version      = current_prof["version"]
    minecraft_dir = current_prof["game_dir"]   # this IS the .minecraft dir
    java_path    = get_suitable_java(version, current_prof)

    os.makedirs(minecraft_dir, exist_ok=True)

    # Pre-create expected sub-folders so the game never falls back to AppData
    _bootstrap_minecraft_dir(minecraft_dir)

    player_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, username))
    dummy_token = str(uuid.uuid4())

    options = {
        "username":       username,
        "uuid":           player_uuid,
        "token":          dummy_token,
        "jvmArguments":   current_prof["jvm_args"].split(),
        "executablePath": java_path,
        # gameDirectory == minecraft_dir: all three roles (classpath root,
        # asset root, and --gameDir runtime flag) resolve to the same place.
        "gameDirectory":  minecraft_dir,
    }

    status_cb(f"Checking/downloading {version}...", "orange")

    current_max = [0]

    def set_status(text):
        status_cb(text, "orange")

    def set_progress(value):
        if current_max[0] > 0:
            pct = max(0.0, min(1.0, value / current_max[0]))
            progress_cb(pct)

    def set_max(value):
        current_max[0] = value

    launcher_callback = {
        "setStatus":   set_status,
        "setProgress": set_progress,
        "setMax":      set_max,
    }

    # Download/verify versions, assets, libraries into this profile's own dir
    try:
        minecraft_launcher_lib.install.install_minecraft_version(
            version, minecraft_dir, callback=launcher_callback
        )
        if post_install_cb:
            post_install_cb(minecraft_dir)
    except Exception as e:
        print(f"[Install Error] {e}")

    progress_cb(1.0)

    # Fix mod-loader JSON quirks inside this profile's own versions/ folder
    if version not in sanitized_versions:
        sanitize_version_json(version, minecraft_dir)
        sanitized_versions.add(version)

    try:
        # All paths in the command (classpath, natives, assets) resolve from
        # minecraft_dir — the same directory --gameDir points to.
        mc_command = minecraft_launcher_lib.command.get_minecraft_command(
            version, minecraft_dir, options
        )

        popen_kwargs: dict = {
            "cwd":      minecraft_dir,   # working dir = profile's .minecraft
            "stdout":   subprocess.PIPE,
            "stderr":   subprocess.STDOUT,
            "text":     True,
            "encoding": "utf-8",
            "errors":   "replace",
        }

        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            popen_kwargs["startupinfo"]   = startupinfo
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        process = subprocess.Popen(mc_command, **popen_kwargs)

        status_cb("Launched successfully! Have fun.", "green")
        success_cb()

        if log_cb and process.stdout:
            for line in process.stdout:
                log_cb(line.strip())

    except KeyError as e:
        traceback.print_exc()
        msg = ("Mod JSON structure error (unhandled 'value' key)!"
               if "value" in str(e) else f"Structure error: {e}")
        status_cb(msg, "red")
        btn_cb("normal", "PLAY")
    except Exception as e:
        status_cb(f"Launch failed: {e}", "red")
        btn_cb("normal", "PLAY")