# core/game_runner.py
import os
import re
import shutil
import uuid
import json
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
        if manual: return manual

    java_major = java_major_for_version(version_str)
    hardcoded = JAVA_PATHS.get(java_major, JAVA_PATHS[21])
    if os.path.exists(hardcoded): return hardcoded

    fallback = shutil.which("java")
    if fallback: return fallback
    return hardcoded

def sanitize_version_json(version: str, game_dir: str):
    json_path = os.path.join(game_dir, "versions", version, f"{version}.json")
    if not os.path.exists(json_path): return
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        modified = False
        if "arguments" in data:
            for arg_type in ("jvm", "game"):
                args_list = data["arguments"].get(arg_type)
                if not isinstance(args_list, list): continue
                cleaned = [_normalize_arg_item(i) for i in args_list]
                if any(c != o for c, o in zip(cleaned, args_list)):
                    data["arguments"][arg_type] = cleaned
                    modified = True

        if modified:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[JSON Scan] Error: {e}")

def run_launch_process(username: str, current_prof: dict, status_cb, progress_cb, btn_cb, success_cb):
    """Hàm chạy ngầm trên Thread, kết nối với thanh tiến độ động của UI"""
    version = current_prof["version"]
    game_dir = current_prof["game_dir"]
    java_path = get_suitable_java(version, current_prof)

    os.makedirs(game_dir, exist_ok=True)
    status_cb(f"Checking/downloading {version}...", "orange")

    # ĐỊNH NGHĨA CALLBACK ĐỂ TÍNH TOÁN % TẢI ENGINE THỰC TẾ
    current_max = [0]

    def set_status(text):
        status_cb(text, "orange")

    def set_progress(value):
        if current_max[0] > 0:
            pct = value / current_max[0]
            pct = max(0.0, min(1.0, pct))
            progress_cb(pct) # Đẩy dữ liệu cập nhật về UI

    def set_max(value):
        current_max[0] = value

    launcher_callback = {
        "setStatus": set_status,
        "setProgress": set_progress,
        "setMax": set_max
    }

    try:
        # Bổ sung lắng nghe tiến trình download
        minecraft_launcher_lib.install.install_minecraft_version(version, game_dir, callback=launcher_callback)
    except Exception as e:
        print(f"[Install Update] {e}")

    progress_cb(1.0)
    sanitize_version_json(version, game_dir)

    player_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, username))
    dummy_token = str(uuid.uuid4())

    options = {
        "username":       username,
        "uuid":           player_uuid,
        "token":          dummy_token,
        "jvmArguments":   current_prof["jvm_args"].split(),
        "executablePath": java_path,
        "gameDirectory":  game_dir,
        "extraArguments": ["--gameDir", game_dir]
    }

    try:
        mc_command = minecraft_launcher_lib.command.get_minecraft_command(version, game_dir, options)
        subprocess.Popen(mc_command, cwd=game_dir)
        status_cb("Launched successfully! Have fun.", "green")
        success_cb()
    except KeyError as e:
        traceback.print_exc()
        msg = "Mod JSON structure error (unhandled 'value' key)!" if "value" in str(e) else f"Structure error: {e}"
        status_cb(msg, "red")
        btn_cb("normal", "PLAY") # Trả lại nút bấm gốc và ẩn thanh bar
    except Exception as e:
        status_cb(f"Launch failed: {e}", "red")
        btn_cb("normal", "PLAY") # Trả lại nút bấm gốc và ẩn thanh bar