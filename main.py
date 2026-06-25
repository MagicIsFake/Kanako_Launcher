# main.py
import os
import sys  
import time  # 🌟 THÊM MỚI: Dùng để hoãn thời gian chờ cửa sổ xuất hiện
import webview
from core.patches import apply_monkey_patches
from ui.bridge import LauncherBridgeAPI

# Khởi động Monkey Patches sửa lỗi JSON trước tiên
apply_monkey_patches()


# 🌟 THẦN CHÚ QUAN TRỌNG NHẤT: Hàm xử lý đường dẫn đa năng
def resource_path(relative_path):
    """ 
    Hàm này tự động nhận diện môi trường:
    - Nếu là file .EXE: Trỏ vào thư mục tạm hệ thống (sys._MEIPASS)
    - Nếu là file .PY: Trỏ vào thư mục code gốc của bạn
    """
    try:
        # Khi đóng gói thành file .exe, PyInstaller sẽ tạo ra biến sys._MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Nếu chạy file .py thông thường, biến trên không tồn tại -> rơi vào đây
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


# 🌟 HÀM ÉP NẠP ICON TRÊN MÔI TRƯỜNG DEV & PRODUCTION
def change_window_icon():
    """
    Hàm này tìm cửa sổ có tiêu đề 'Kanako Launcher' để đổi logo góc trái cửa sổ.
    """
    if sys.platform != "win32":
        return

    import ctypes
    # Đợi khoảng 0.5 giây để cửa sổ kịp render và xuất hiện trên Windows
    time.sleep(0.5)
    
    # Tìm mã định danh (HWND) của cửa sổ dựa theo chính xác Title bạn đặt
    hwnd = ctypes.windll.user32.FindWindowW(None, "Kanako Launcher")
    if hwnd:
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        
        # 🌟 SỬA TẠI ĐÂY: Dùng hàm thông minh để lấy đúng file icon.ico ở cả 2 môi trường
        icon_path = resource_path("icon.ico")
        
        if os.path.exists(icon_path):
            # Nạp icon vào bộ nhớ Windows
            hicon = ctypes.windll.user32.LoadImageW(
                None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE
            )
            if hicon:
                # Ép cửa sổ đổi icon nhỏ (góc tiêu đề) và icon lớn (khi Alt + Tab)
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
                print("🌟 Đã nạp thành công Icon cho cửa sổ!")


if __name__ == "__main__":
    # SỬA ICON DƯỚI THANH TASKBAR (CHO WINDOWS)
    if sys.platform == "win32":
        import ctypes
        try:
            myappid = 'kanako.minecraft.launcher.1.0'  
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print("Không thể thiết lập AppUserModelID:", e)

    # 1. Khởi tạo API cầu nối dữ liệu cũ của bạn
    api = LauncherBridgeAPI()

    # 2. Định nghĩa kích thước cửa sổ Launcher
    window_width = 850
    window_height = 580

    # 3. Lấy thông tin màn hình máy tính để tính toán tọa độ chính giữa
    try:
        screens = webview.screens
        if screens:
            primary_screen = screens[0]  # Lấy màn hình chính
            screen_width = primary_screen.width
            screen_height = primary_screen.height
            
            # Công thức tính tọa độ X, Y để cửa sổ nằm chính giữa màn hình
            start_x = (screen_width - window_width) // 2
            start_y = (screen_height - window_height) // 2
        else:
            start_x, start_y = None, None
    except Exception:
        # Dự phòng nếu có lỗi xảy ra khi lấy thông tin màn hình
        start_x, start_y = None, None

    # 4. 🌟 SỬA TẠI ĐÂY: Sử dụng hàm resource_path để bọc thư mục giao diện UI lại
    ui_path = resource_path(os.path.join("ui", "web", "index.html"))

    # 5. Tạo cửa sổ với cấu hình chuẩn sạch của pywebview
    window = webview.create_window(
        title="Kanako Launcher",
        url=ui_path,            # Đường dẫn tự động biến đổi thông minh
        js_api=api,             # Kết nối Python với JavaScript
        width=window_width,
        height=window_height,
        x=start_x,              # Tọa độ ngang chính giữa
        y=start_y,              # Tọa độ dọc chính giữa
        resizable=True          
    )
    
    # Gắn cửa sổ vào api để điều khiển đóng/ẩn cửa sổ
    api._window = window

    # Khởi chạy và kích hoạt hàm nạp icon song song
    webview.start(change_window_icon)