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
    """
    Map a Minecraft version string to the Java major version it requires.

    1.0 – 1.16.5  → Java 8
    1.17 – 1.20.4 → Java 17
    1.20.5+       → Java 21
    """
    try:
        match = re.search(r'\b1\.(\d+)(?:\.(\d+))?\b', version_str)
        if match:
            minor = int(match.group(1))
            patch = int(match.group(2)) if match.group(2) else 0
            v = (1, minor, patch)
            if v <= (1, 16, 5):
                return 8
            elif v < (1, 20, 5):
                return 17
            else:
                return 21
    except Exception:
        pass
    return 21


def get_suitable_java(version_str: str, prof_data: dict) -> str:
    """
    Return the Java executable to use for this version.

    Priority:
    1. Manual override from profile settings
    2. Hardcoded path from constants.JAVA_PATHS  (checked first so Java 8
       versions like Forge 1.12.2 never accidentally get Java 17/21)
    3. Bundled JRE downloaded by minecraft_launcher_lib (modern versions only,
       i.e. Java 17+ -- skipped entirely for Java 8 versions)
    4. System 'java' on PATH
    """
    # 1. Manual override
    if prof_data.get("java_manual") and prof_data.get("java_path"):
        manual = prof_data["java_path"].strip()
        if manual:
            return manual

    java_major = java_major_for_version(version_str)

    # 2. Hardcoded path -- always wins over the bundled JRE so that versions
    #    requiring Java 8 (<=1.16.5, all Forge 1.12.2 etc.) get exactly Java 8
    #    and not whatever modern JRE happens to be in the runtime folder.
    hardcoded = JAVA_PATHS.get(java_major, JAVA_PATHS[21])
    if os.path.exists(hardcoded):
        return hardcoded

    # 3. Bundled JRE -- only for Java 17/21 (modern versions).
    #    Skipped for Java 8 because the bundled runtime is always Java 17+.
    if java_major >= 17:
        minecraft_dir = prof_data.get("game_dir", "")
        if minecraft_dir:
            runtime_base = os.path.join(minecraft_dir, "runtime")
            if os.path.isdir(runtime_base):
                for runtime_name in os.listdir(runtime_base):
                    os_folder = _os_runtime_folder()
                    candidate_root = os.path.join(
                        runtime_base, runtime_name, os_folder, runtime_name, "bin"
                    )
                    for exe in ("javaw.exe", "java.exe", "java"):
                        candidate = os.path.join(candidate_root, exe)
                        if os.path.isfile(candidate):
                            return candidate

    # 4. System java
    fallback = shutil.which("java")
    return fallback if fallback else hardcoded


def _os_runtime_folder() -> str:
    """Return the OS subfolder name used by Mojang's runtime downloads."""
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "windows-arm64" if "arm" in machine or "aarch64" in machine else "windows-x64"
    if system == "Darwin":
        return "mac-os-arm64" if "arm" in machine or "aarch64" in machine else "mac-os"
    return "linux"


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


def _bootstrap_minecraft_dir(minecraft_dir: str, current_version: str = "1.20.1"):
    """
    Pre-create the sub-folders and launcher_profiles.json Minecraft expects.
    """
    subdirs = [
        "saves", "resourcepacks", "shaderpacks",
        "mods", "config", "screenshots", "logs", "crash-reports",
    ]
    for sub in subdirs:
        os.makedirs(os.path.join(minecraft_dir, sub), exist_ok=True)

    profiles_path = os.path.join(minecraft_dir, "launcher_profiles.json")
    if not os.path.exists(profiles_path):
        dummy_profiles = {
            "profiles": {
                "default-profile": {
                    "name": "Default",
                    "type": "custom",
                    "lastVersionId": current_version,
                }
            },
            "settings": {"crashAssistance": True},
            "version": 3,
        }
        try:
            with open(profiles_path, "w", encoding="utf-8") as f:
                json.dump(dummy_profiles, f, indent=4, ensure_ascii=False)
            print(f"[Bootstrap] Created dummy launcher_profiles.json at {profiles_path}")
        except Exception as e:
            print(f"[Bootstrap] Error creating launcher_profiles.json: {e}")



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
          → versions/assets/libraries are downloaded there
        • the minecraft_dir argument to get_minecraft_command()
          → the JVM classpath resolves from there
        • the "gameDirectory" option
          → --gameDir points there and all runtime writes land there

    This means every profile is 100 % self-sufficient and completely
    independent of every other profile and of %APPDATA%\\.minecraft.

    Native library handling
    ───────────────────────
    minecraft_launcher_lib already handles natives correctly for all versions:

    • Legacy (≤ 1.18): install_minecraft_version() extracts DLLs into
      <minecraft_dir>/versions/<ver>/natives/ and get_minecraft_command()
      emits -Djava.library.path pointing there.

    • Modern (1.19+): native JARs sit on the -cp classpath. LWJGL 3 reads
      -Dorg.lwjgl.system.SharedLibraryExtractPath (emitted by the library)
      and self-extracts DLLs at runtime — no folder extraction required.

    We must NOT inject extra -Djava.library.path / -Dorg.lwjgl.librarypath
    arguments, because that overrides what the library already set up and
    points LWJGL at an empty directory → "Failed to locate library: lwjgl.dll".
    """
    version       = current_prof["version"]
    minecraft_dir = current_prof["game_dir"]
    java_path     = get_suitable_java(version, current_prof)

    os.makedirs(minecraft_dir, exist_ok=True)
    _bootstrap_minecraft_dir(minecraft_dir, version)

    player_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, username))
    dummy_token = str(uuid.uuid4())

    options = {
        "username":       username,
        "uuid":           player_uuid,
        "token":          dummy_token,
        # Do NOT pass jvmArguments here — the library would embed them inside
        # the generated command between the fixed JVM flags it owns
        # (e.g. -Djava.library.path, -Dorg.lwjgl.system.SharedLibraryExtractPath).
        # We insert user args manually at position 1 below, which is safe
        # because position 0 is always the java executable.
        "executablePath": java_path,
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

    # Download/verify versions, assets, libraries (and natives for legacy) into
    # this profile's own directory.
    try:
        minecraft_launcher_lib.install.install_minecraft_version(
            version, minecraft_dir, callback=launcher_callback
        )
        if post_install_cb:
            post_install_cb(minecraft_dir)
    except Exception as e:
        print(f"[Install Error] {e}")

    progress_cb(1.0)

    # Fix mod-loader JSON quirks (e.g. Forge using 'values' instead of 'value')
    if version not in sanitized_versions:
        sanitize_version_json(version, minecraft_dir)
        sanitized_versions.add(version)

    try:
        # Build the launch command — minecraft_launcher_lib handles ALL JVM flags
        # including -Djava.library.path, -Dorg.lwjgl.system.SharedLibraryExtractPath,
        # etc., correctly for both legacy and modern versions.
        mc_command = minecraft_launcher_lib.command.get_minecraft_command(
            version, minecraft_dir, options
        )

        # ── Native DLL extraction (all versions) ────────────────────────────
        # minecraft_launcher_lib already set -Djava.library.path to the
        # 'natives' folder and added the native JARs to -cp.  However for
        # modern LWJGL 3 (1.19+) the self-extractor sometimes fails in
        # third-party launchers (permission issues, missing temp dir, etc.).
        # The safest approach for every version is to extract DLLs ourselves
        # from the classpath JARs into the natives folder the library declared.
        import zipfile

        # Read the natives path directly from the command the library built —
        # this is always correct regardless of version or OS.
        natives_dir = ""
        for arg in mc_command:
            if arg.startswith("-Djava.library.path="):
                natives_dir = arg.split("=", 1)[1]
                break

        if not natives_dir:
            # Fallback: use the standard location
            natives_dir = os.path.join(minecraft_dir, "versions", version, "natives")

        os.makedirs(natives_dir, exist_ok=True)

        # Only extract if the folder has no DLLs yet (skip on re-launch)
        already_extracted = any(
            f.endswith((".dll", ".so", ".dylib"))
            for f in os.listdir(natives_dir)
        )
        if not already_extracted:
            classpath_str = ""
            for i, arg in enumerate(mc_command):
                if arg in ("-cp", "-classpath") and i + 1 < len(mc_command):
                    classpath_str = mc_command[i + 1]
                    break

            extracted_count = 0
            if classpath_str:
                for jar_path in classpath_str.split(os.path.pathsep):
                    if not (jar_path.endswith(".jar") and os.path.exists(jar_path)):
                        continue
                    try:
                        with zipfile.ZipFile(jar_path, "r") as jar:
                            for fi in jar.infolist():
                                fname = fi.filename
                                if "META-INF" in fname or fname.endswith("/"):
                                    continue
                                if fname.endswith((".dll", ".so", ".dylib")):
                                    basename = os.path.basename(fname)
                                    if not basename:
                                        continue
                                    target = os.path.join(natives_dir, basename)
                                    with jar.open(fi) as src, open(target, "wb") as dst:
                                        shutil.copyfileobj(src, dst)
                                    extracted_count += 1
                    except Exception as ex:
                        print(f"[Natives] Could not read {os.path.basename(jar_path)}: {ex}")

            print(f"[Natives] Extracted {extracted_count} files to {natives_dir}")

        # ── Inject user JVM args (-Xmx, GC flags, etc.) ────────────────────
        # Find the insertion point: after the java executable (index 0) and
        # after any -Djava.library.path / -D* flags the library already placed,
        # but BEFORE -cp and the main class.  This keeps the library's flags
        # in their original positions so LWJGL can find its natives.
        insert_at = 1
        for idx, arg in enumerate(mc_command[1:], start=1):
            if arg in ("-cp", "-classpath") or not arg.startswith("-"):
                insert_at = idx
                break

        user_jvm_args = [a.strip() for a in current_prof.get("jvm_args", "").split() if a.strip()]
        for arg in reversed(user_jvm_args):
            mc_command.insert(insert_at, arg)

        # ── Launch ───────────────────────────────────────────────────────────
        popen_kwargs: dict = {
            "cwd":      minecraft_dir,
            "stdout":   subprocess.PIPE,
            "stderr":   subprocess.STDOUT,
            "text":     True,
            "encoding": "utf-8",
            "errors":   "replace",
        }

        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            # SW_SHOWNORMAL = 1: show the game window normally.
            # Without this, LWJGL 2 (1.12.2 and older) creates an invisible window.
            startupinfo.dwFlags    |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 1
            popen_kwargs["startupinfo"]   = startupinfo
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        process = subprocess.Popen(mc_command, **popen_kwargs)

        # Debug: verify -Djava.library.path is still present and correct.
        # Remove this print once the game launches successfully.
        lib_path_args = [a for a in mc_command if "library.path" in a or "SharedLibrary" in a]
        print(f"[DEBUG] natives args in final command: {lib_path_args}")

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