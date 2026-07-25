# core/bypass/activate.py
import os

def activate_bypass(mc_command: list):
    try:
        # 1. Ép tham số userType về legacy và sửa accessToken thành chuỗi giả cấu trúc JWT
        dummy_jwt = (
            "eyJhbGciOiJSUzI1NiJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "XfG_p8_S472NlzvO8_Bv3M7X4B4J9w8mH7W2l_wO6P4X9Y8zK7gV9b6M2v_X4N7_b8v9M_wO6X4"
        )
        
        for idx, arg in enumerate(mc_command):
            if arg == "--userType" and idx + 1 < len(mc_command):
                mc_command[idx + 1] = "legacy"
            if arg == "--accessToken" and idx + 1 < len(mc_command):
                mc_command[idx + 1] = dummy_jwt
        
        # 2. Định vị file Agent và thư viện Javassist phụ trợ
        # Lúc này __file__ là core/patches/bypass.py => current_dir là core/patches/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # THAY ĐỔI Ở ĐÂY: Vì file jar ở ngay cạnh file bypass.py nên bỏ chữ "patches" đi
        agent_path = os.path.join(current_dir, "multiplayer_patch.jar")
        lib_path = os.path.join(current_dir, "javassist.jar")
        
        # 3. Tiến hành tiêm nạp chuỗi kép vào JVM
        if os.path.exists(agent_path) and os.path.exists(lib_path):
            mc_command.insert(1, f"-Xbootclasspath/a:{lib_path}")
            mc_command.insert(2, f"-javaagent:{agent_path}")
            print(f"[Launcher Agent] Armed successfully with core libraries from patches folder!")
        else:
            print(f"[Launcher Agent] WARNING: Missing files inside core/patches/ folder! Path checked: {agent_path}")
                
    except Exception as e:
        print(f"[Launcher Agent] Error injecting agent setup: {e}")