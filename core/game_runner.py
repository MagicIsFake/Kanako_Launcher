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


def sanitize_version_json(version: str, game_dir: str):
    """Rewrite the version JSON in-place to fix non-standard argument keys."""
    json_path = os.path.join(game_dir, "versions", version, f"{version}.json")
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


def run_launch_process(username: str, current_prof: dict,
                       status_cb, progress_cb, btn_cb, success_cb,
                       sanitized_versions: set, log_cb=None, post_install_cb=None):
    """
    Runs on a background thread.
    SỬA ĐỔI: Bổ sung log_cb để truyền log game về giao diện UI.
    """
    version  = current_prof["version"]
    game_dir = current_prof["game_dir"]
    java_path = get_suitable_java(version, current_prof)

    os.makedirs(game_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # SỬA TẠI ĐÂY (1): Khởi tạo biến 'options' ngay đầu hàm để tránh lỗi UnboundLocalError
    # ------------------------------------------------------------------
    player_uuid  = str(uuid.uuid3(uuid.NAMESPACE_DNS, username))
    dummy_token  = str(uuid.uuid4())

    options = {
        "username":       username,
        "uuid":           player_uuid,
        "token":          dummy_token,
        "jvmArguments":   current_prof["jvm_args"].split(),
        "executablePath": java_path,
        "gameDirectory":  game_dir,
        "extraArguments": ["--gameDir", game_dir],
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

    # Tiến hành cài đặt game
    try:
        minecraft_launcher_lib.install.install_minecraft_version(
            version, game_dir, callback=launcher_callback
        )
        if post_install_cb:
            post_install_cb(game_dir)
    except Exception as e:
        print(f"[Install Error] {e}")

    progress_cb(1.0)

    # Chuẩn hóa cấu hình JSON nếu cần
    if version not in sanitized_versions:
        sanitize_version_json(version, game_dir)
        sanitized_versions.add(version)

    # Tiến hành khởi chạy game và bắt log
    try:
        mc_command = minecraft_launcher_lib.command.get_minecraft_command(version, game_dir, options)

        # ------------------------------------------------------------------
        # SỬA TẠI ĐÂY (2): Thay đổi popen_kwargs để bắt luồng Standard Output/Error
        # ------------------------------------------------------------------
        popen_kwargs: dict = {
            "cwd": game_dir, 
            "stdout": subprocess.PIPE,       # Hứng luồng log chuẩn của game
            "stderr": subprocess.STDOUT,     # Gộp luồng lỗi vào chung luồng log
            "text": True,                    # Đọc dạng String văn bản thay vì Bytes
            "encoding": "utf-8",             # Tránh lỗi font ký tự lạ
            "errors": "replace"
        }
        
        if platform.system() == "Windows":
            # Ẩn cửa sổ cmd đen xì của Java bật kèm (nếu có)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            popen_kwargs["startupinfo"] = startupinfo
            # Tạo nhóm tiến trình mới độc lập để khi tắt launcher game không bị tắt theo (nếu chọn giữ mở launcher)
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        # Chạy tiến trình game
        process = subprocess.Popen(mc_command, **popen_kwargs)
        
        status_cb("Launched successfully! Have fun.", "green")
        success_cb()

        # ------------------------------------------------------------------
        # SỬA TẠI ĐÂY (3): Vòng lặp đọc log liên tục từ Game truyền ra UI Console
        # ------------------------------------------------------------------
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