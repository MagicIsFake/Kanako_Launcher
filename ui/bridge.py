# ui/bridge.py
import os
import threading
import minecraft_launcher_lib
import shutil
import json

from core.config_manager import ConfigManager
from core.game_runner import run_launch_process

class LauncherBridgeAPI:
    def __init__(self):
        # Đổi tên thành có dấu _ ở trước để pywebview không quét trúng gây lỗi crash
        self._config_manager = ConfigManager()
        self._version_manager = None
        self._window = None
        self._versions_ready = False
        
        # CHẠY LUỒNG NGẦM: Tải danh sách phiên bản từ Mojang mà không làm treo giao diện
        threading.Thread(target=self._async_load_versions, daemon=True).start()

    def _async_load_versions(self):
        """Hàm này chạy ngầm để nạp danh sách phiên bản"""
        try:
            from core.version_manager import VersionManager
            # Khởi tạo VersionManager ở đây sẽ tốn vài giây nhưng chạy ngầm
            self._version_manager = VersionManager()
            self._versions_ready = True
            print("[Python Backend] Đã nạp xong danh sách phiên bản thành công!")
            
            # Nếu cửa sổ đã mở, báo ngay cho JavaScript biết để cập nhật dropdown phiên bản
            # ui/bridge.py (Chỉ sửa đoạn cuối của hàm _async_load_versions)

            # ... (các dòng code phía trên của hàm giữ nguyên) ...
            print("[Python Backend] Đã nạp xong danh sách phiên bản thành công!")
            
            if self._window:
                current_prof_name = self._config_manager.get_current_profile_name()
                current_prof_data = self._config_manager.get_profile(current_prof_name)
                
                game_dir = current_prof_data["game_dir"]
                local_vers = minecraft_launcher_lib.utils.get_installed_versions(game_dir)
                local_ids = [v["id"] for v in local_vers]
                version_list = self._version_manager.build_display_list(current_prof_data, local_ids)
                
                # SỬA TẠI ĐÂY: Sử dụng dấu {{ }} để bọc mã JS an toàn trong f-string của Python
                version_list_json = json.dumps(version_list)
                
                safe_js_code = f"""
                if (typeof onVersionsLoaded === 'function') {{
                    onVersionsLoaded({version_list_json}, '{current_prof_data.get('version', '')}');
                }}
                """
                self._window.evaluate_js(safe_js_code)
                
        except Exception as e:
            print(f"[Python Error] Lỗi khi nạp phiên bản ngầm: {e}")

    # Ví dụ cấu trúc hàm trong ui/bridge.py của Python bổ sung cho Web UI mới:

    def get_initial_data(self):
        current_prof = self._config_manager.get_current_profile_name()
        # Lấy toàn bộ danh sách tên Profile (Default, MaryProfile, ...) đưa vào mảng
        profiles_list = list(self._config_manager.config.get("profiles", {}).keys())
        profile_data = self._config_manager.get_profile(current_prof)
        
        # Kiểm tra xem luồng ngầm đã load xong danh sách từ Mojang chưa
        versions_ready = len(self._version_manager.all_versions.get("release", [])) > 0
        version_list = []
        
        if versions_ready:
            game_dir = profile_data["game_dir"]
            local_vers = minecraft_launcher_lib.utils.get_installed_versions(game_dir)
            local_ids = [v["id"] for v in local_vers]
            version_list = self._version_manager.build_display_list(profile_data, local_ids)
            
        return {
            "current_profile": current_prof,
            "profiles_list": profiles_list,     # Cực kỳ quan trọng để vẽ ô chọn Profile
            "profile_data": profile_data,
            "versions_ready": versions_ready,
            "versions": version_list
        }

    # ui/bridge.py

    def switch_profile(self, profile_name):
        try:
            # SỬA TẠI ĐÂY: Thay 'set_current_profile' thành 'set_current_profile_name'
            self._config_manager.set_current_profile_name(profile_name)
            self._config_manager.save_profiles()
            
            # Lấy thông tin chi tiết của profile mới chuyển sang
            profile_data = self._config_manager.get_profile(profile_name)
            game_dir = profile_data["game_dir"]
            
            # Quét các phiên bản đã tải cục bộ của profile mới này
            local_vers = minecraft_launcher_lib.utils.get_installed_versions(game_dir)
            local_ids = [v["id"] for v in local_vers]
            version_list = self._version_manager.build_display_list(profile_data, local_ids)
            
            # Trả dữ liệu sạch về cho JavaScript (app.js) vẽ lại giao diện
            return {
                "profile_data": profile_data,
                "versions_ready": True,
                "versions": version_list
            }
        except Exception as e:
            print(f"[Bridge Error] Lỗi khi chuyển đổi profile: {e}")
            return None

    def launch_game(self, username, version, remember, keep_launcher_open=False):
        try:
            # 1. LẤY ĐÚNG DICTIONARY CỦA PROFILE HIỆN TẠI (Sửa lỗi chí mạng tại đây)
            current_prof_name = self._config_manager.get_current_profile_name()
            prof_data = self._config_manager.get_profile(current_prof_name)
            
            # Cập nhật các thông tin người dùng vừa chọn từ Web UI vào dict
            prof_data["version"] = version
            if remember:
                prof_data["username"] = username
                prof_data["remember"] = True
            else:
                prof_data["username"] = ""
                prof_data["remember"] = False
                
            # Lưu lại file cấu hình json của bạn
            self._config_manager.save_profiles()

            # 2. ĐỊNH NGHĨA CÁC CALLBACK ĐỂ ĐẨY NGƯỢC TIẾN TRÌNH LÊN WEB UI (app.js)
            def progress_cb(pct):
                # pct từ game_runner trả về từ 0.0 đến 1.0, cần nhân 100 để ra phần trăm (%)
                percentage = int(pct * 100)
                if self._window:
                    self._window.evaluate_js(f"window.updateProgress({percentage})")

            def btn_cb(state, text):
                # Hàm callback reset nút bấm nếu gặp lỗi tải/crash cấu trúc JSON
                pass

            def success_cb():
                self._window.evaluate_js("window.launchSuccess()")
                
                # keep_launcher_open is now properly received from JS via launch_game parameter
                if not keep_launcher_open:
                    print("Game started! Closing launcher as requested.")
                    self._window.destroy()
                else:
                    print("Game started! Keeping launcher alive.")

            def status_cb(msg, color_name_or_hex):
                # Convert color names to hex for safe JS injection
                hex_color = color_name_or_hex
                if color_name_or_hex == "red":
                    hex_color = "#E74C3C"
                elif color_name_or_hex == "green":
                    hex_color = "#2ECC71"
                elif color_name_or_hex == "orange":
                    hex_color = "#E67E22"

                # FIX: Escape the message using json.dumps to safely handle
                # apostrophes and special characters that would break the JS string literal.
                # e.g. "Launch failed: can't find file" would have caused SyntaxError.
                import json
                safe_msg = json.dumps(msg)  # produces a properly quoted+escaped JS string
                if self._window:
                    self._window.evaluate_js(f"window.updateStatus({safe_msg}, '{hex_color}')")

            # 3. KHỞI CHẠY THREAD VỚI ĐỐI SỐ THỨ HAI LÀ DICT 'prof_data'
            # Lỗi cũ của bạn có thể là đã truyền biến 'version' (String) vào đây
            threading.Thread(
                target=run_launch_process,
                args=(username, prof_data, status_cb, progress_cb, btn_cb, success_cb),
                daemon=True
            ).start()

        except Exception as e:
            print(f"[Bridge Error] Lỗi kích hoạt luồng chạy game: {e}")
    
    def get_profile_details(self, profile_name):
        """Trả về dictionary chi tiết của profile để đưa lên form chỉnh sửa"""
        return self._config_manager.get_profile(profile_name)

    def web_browse_directory(self):
        """Mở hộp thoại chọn thư mục chuẩn hệ thống bằng pywebview (Không cần Tkinter)"""
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return os.path.normpath(result[0])
        return ""

    def web_browse_file(self):
        """Mở hộp thoại chọn file java.exe hệ thống"""
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG, 
            file_types=('Java Executable (java.exe;java)', 'All files (*.*)')
        )
        if result and len(result) > 0:
            return os.path.normpath(result[0])
        return ""

    def web_open_folder(self, path):
        """Mở thư mục trên File Explorer của máy tính"""
        if not path:
            return
        os.makedirs(path, exist_ok=True)
        if platform.system() == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen(["open" if platform.system() == "Darwin" else "xdg-open", path])

    def web_save_profile(self, old_id, new_name, game_dir, jvm_args, java_manual, java_path, allow_snapshots, allow_beta, allow_alpha):
        """Bê nguyên xi logic xử lý lưu dữ liệu, đổi tên trùng lặp từ edit_window.py sang"""
        try:
            if not new_name:
                new_name = old_id

            prof = self._config_manager.config["profiles"][old_id]
            prof["game_dir"] = game_dir
            prof["jvm_args"] = jvm_args
            prof["java_manual"] = java_manual
            prof["java_path"] = java_path if java_manual else ""
            prof["allow_snapshots"] = allow_snapshots
            prof["allow_beta"] = allow_beta
            prof["allow_alpha"] = allow_alpha

            # Xử lý đổi tên profile và chống trùng lặp ID trong file json
            if new_name != old_id:
                base, counter = new_name, 1
                while new_name in self._config_manager.config["profiles"]:
                    new_name = f"{base}_{counter}"
                    counter += 1
                # Đổi khóa cũ thành khóa mới trong dictionary cấu hình
                self._config_manager.config["profiles"][new_name] = self._config_manager.config["profiles"].pop(old_id)
                self._config_manager.config["profiles"][new_name]["name"] = new_name
                self._config_manager.set_current_profile_name(new_name)
            else:
                prof["name"] = old_id

            # Ghi đè cập nhật xuống ổ đĩa cứng
            self._config_manager.save_profiles()
            return {"success": True}
        except Exception as e:
            print(f"[Bridge Error] Không thể lưu cài đặt profile: {e}")
            raise e
            
    # ui/bridge.py

    def web_create_profile(self):
        """Tạo một profile hoàn toàn mới với các thông số mặc định của hệ thống"""
        try:
            # 1. Tự động tính toán tên để không bị trùng (New Profile, New Profile_1, New Profile_2...)
            base_name = "New Profile"
            new_name = base_name
            counter = 1
            while new_name in self._config_manager.config["profiles"]:
                new_name = f"{base_name}_{counter}"
                counter += 1
            
            # 2. Lấy cụm dữ liệu cấu hình mặc định (từ ConfigManager)
            # Hàm _default_profile_data() đã có sẵn trong file core/config_manager.py của bạn
            default_data = self._config_manager._default_profile_data()
            default_data["name"] = new_name
            
            # 3. Ghi đè cấu hình mới vào danh sách tổng và đặt làm profile mặc định hiện tại
            self._config_manager.config["profiles"][new_name] = default_data
            self._config_manager.set_current_profile_name(new_name)
            
            # 4. Lưu trực tiếp xuống file JSON launcher_profiles_custom.json
            self._config_manager.save_profiles()
            
            # Trả tên profile mới về cho JavaScript biết đường mà chọn
            return new_name
        except Exception as e:
            print(f"[Bridge Error] Không thể tạo profile mới: {e}")
            raise e
            

    def web_remove_profile(self, profile_name, delete_files):
        """Xóa profile khỏi cấu hình và dọn dẹp thư mục game nếu được yêu cầu"""
        try:
            profiles = self._config_manager.config.get("profiles", {})
            if profile_name not in profiles:
                return {"success": False, "error": "Profile không tồn tại"}

            # Lấy đường dẫn thư mục game trước khi xóa dữ liệu cấu hình
            prof_data = profiles[profile_name]
            game_dir = prof_data.get("game_dir", "")

            # 1. Tiến hành xóa profile khỏi bộ nhớ JSON
            del self._config_manager.config["profiles"][profile_name]

            # 2. Xử lý kịch bản: Nếu profile vừa xóa trùng khớp với profile đang chọn hiển thị
            current_active = self._config_manager.get_current_profile_name()
            if current_active == profile_name:
                remaining_profiles = list(self._config_manager.config["profiles"].keys())
                if remaining_profiles:
                    # Chuyển thanh cuộn sang profile kế tiếp có sẵn
                    self._config_manager.set_current_profile_name(remaining_profiles[0])
                else:
                    # Nếu xóa sạch không còn cái nào, tự động tạo lại một cái "Default" sạch để launcher không bị crash
                    default_prof = self._config_manager._default_profile_data()
                    default_prof["name"] = "Default"
                    self._config_manager.config["profiles"]["Default"] = default_prof
                    self._config_manager.set_current_profile_name("Default")

            # 3. Ghi đè cập nhật mới xuống file JSON launcher_profiles_custom.json
            self._config_manager.save_profiles()

            # 4. XỬ LÝ XÓA FILE CỨNG: Nếu tích chọn TRUE và đường dẫn hợp lệ
            if delete_files and game_dir and os.path.exists(game_dir):
                # Một bước check an toàn nhỏ: Không bao giờ cho phép xóa nhầm thư mục gốc ổ đĩa C:\ hoặc D:\
                if len(os.path.abspath(game_dir)) > 4: 
                    try:
                        shutil.rmtree(game_dir, ignore_errors=True)
                        print(f"[Remove Profile] Đã xóa sạch thư mục cứng tại: {game_dir}")
                    except Exception as folder_err:
                        print(f"[Warning] Không thể xóa một số tệp đang mở trong thư mục game: {folder_err}")

            return {"success": True}
        except Exception as e:
            print(f"[Bridge Error] Lỗi nghiêm trọng khi thực hiện lệnh xóa profile: {e}")
            raise e