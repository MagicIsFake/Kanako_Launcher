// ui/web/app.js

let selectedVersion = "";

// ==========================================
// 1. CÁC HÀM PYTHON SẼ GỌI NGƯỢC LẠI QUA EVALUATE_JS
// ==========================================
window.onVersionsLoaded = function(versionsList, savedVersion) {
    renderVersions(versionsList, savedVersion);
}

window.updateStatus = function(message, color) {
    let statusLabel = document.getElementById("status"); // Khớp với id="status" trong HTML
    if (statusLabel) {
        statusLabel.innerText = message;
        statusLabel.style.color = color;
    }
}

window.updateProgress = function(percentage) {
    let progressBar = document.getElementById("progress-bar"); // Khớp với id="progress-bar"
    let progressContainer = document.getElementById("progress-container"); // Khớp với id="progress-container"
    
    if (progressContainer) progressContainer.classList.remove("hidden");
    if (progressBar) {
        progressBar.style.width = percentage + "%";
    }
}

window.launchSuccess = function() {
    console.log("Game started! Enjoy!");
    window.updateStatus("Launched successfully! Have fun.", "#2ECC71");
}

// ==========================================
// 2. KHỞI TẠO VÀ ĐỒNG BỘ PROFILE (SỬA LỖI ĐƠ GIAO DIỆN)
// ==========================================
function initializeLauncher() {
    if (!window.pywebview || !window.pywebview.api) return;

    // Gọi Python lấy toàn bộ dữ liệu cấu hình lên Web UI
    window.pywebview.api.get_initial_data().then(data => {
        console.log("Đã nạp dữ liệu từ Python:", data);
        
        // 2.1 Nạp danh sách các Profile đang có vào thẻ <select> một cách tự động
        let profileSelect = document.getElementById("profile-select");
        if (profileSelect && data.profiles_list) {
            profileSelect.innerHTML = data.profiles_list.map(p => 
                `<option value="${p}" ${p === data.current_profile ? 'selected' : ''}>${p}</option>`
            ).join('');
        }

        // 2.2 Nạp Username và Trạng thái checkbox ghi nhớ (Khớp ID HTML)
        let txtUsername = document.getElementById("username");
        let chkRemember = document.getElementById("remember-username");

        if (txtUsername) txtUsername.value = data.profile_data.username || "";
        if (chkRemember) chkRemember.checked = data.profile_data.remember || false;
		
		// --- THÊM ĐOẠN NÀY VÀO NGAY ĐÂY ---
        let chkCloseAfterLaunch = document.getElementById("close-after-launch");
        if (chkCloseAfterLaunch) {
            // Đọc dữ liệu đã lưu từ bộ nhớ trình duyệt
            const savedCloseOption = localStorage.getItem("closeAfterLaunch");
            // Nếu đã từng lưu thì dùng giá trị đó, nếu là lần đầu tiên mở app thì mặc định là false
            if (savedCloseOption !== null) {
                chkCloseAfterLaunch.checked = savedCloseOption === "true";
            } else {
                chkCloseAfterLaunch.checked = false; 
            }

            // Gắn sự kiện lắng nghe: Mỗi lần người dùng click tick/bỏ tick thì tự lưu lại ngay lập tức
            chkCloseAfterLaunch.onchange = function() {
                localStorage.setItem("closeAfterLaunch", chkCloseAfterLaunch.checked);
            };
        }
		
		// 🌟 XỬ LÝ LOGIC CHUYỂN ĐỔI VÀ GHI NHỚ FONT CHỮ TẠI ĐÂY
        let chkUseSegoe = document.getElementById("use-segoe-font");
        if (chkUseSegoe) {
            const savedFontOption = localStorage.getItem("useSegoeFont");
            
            // Nếu trạng thái đã lưu là true -> Tích chọn và kích hoạt class Segoe lên body
            if (savedFontOption === "true") {
                chkUseSegoe.checked = true;
                document.body.classList.add("segoe-active");
            } else {
                // Mặc định ban đầu chưa lưu hoặc false -> Dùng font custom Mincho
                chkUseSegoe.checked = false;
                document.body.classList.remove("segoe-active");
            }

            // Lắng nghe sự kiện click chuột của người dùng
            chkUseSegoe.onchange = function() {
                localStorage.setItem("useSegoeFont", chkUseSegoe.checked);
                if (chkUseSegoe.checked) {
                    document.body.classList.add("segoe-active");
                } else {
                    document.body.classList.remove("segoe-active");
                }
            };
        }
        
        // 2.3 Nạp danh sách phiên bản Minecraft
        if (data.versions_ready) {
            renderVersions(data.versions, data.profile_data.version);
        } else {
            let btnVersion = document.getElementById('version-select-btn');
            if (btnVersion) btnVersion.innerText = "⏳ Fetching versions from Mojang...";
        }
    }).catch(err => console.error("Lỗi khởi tạo Launcher:", err));
}

// Cơ chế bắt sự kiện thông minh chống lỗi race condition tải chậm/nhanh
if (window.pywebview) {
    initializeLauncher();
} else {
    window.addEventListener('pywebviewready', initializeLauncher);
}

// ==========================================
// 3. LOGIC HIỂN THỊ PHIÊN BẢN (VERSION)
// ==========================================
function renderVersions(versionsList, savedVersion) {
    const dropdown = document.getElementById('version-dropdown');
    const btnVersion = document.getElementById('version-select-btn');
    
    if (!btnVersion) return;
    if (!versionsList || versionsList.length === 0) {
        btnVersion.innerText = "⚠️ No versions available";
        return;
    }

    // Lấy ID của phần tử đầu tiên (đề phòng trường hợp nó là Object hoặc String)
    const firstVersionId = typeof versionsList[0] === 'object' ? versionsList[0].id : versionsList[0];
    
    selectedVersion = savedVersion || firstVersionId;
    btnVersion.innerText = `📦 ${selectedVersion}`;

    if (dropdown) {
        dropdown.innerHTML = versionsList.map(ver => {
            // Hỗ trợ cả định dạng cũ (String) và định dạng mới (Object) để không bị lỗi màn hình
            let id = typeof ver === 'object' ? ver.id : ver;
            let isDownloaded = typeof ver === 'object' ? ver.is_downloaded : false;
            let type = typeof ver === 'object' ? ver.type : 'vanilla';

            // BỘ LỌC THÔNG MINH: Tự động đoán loại nếu chuỗi tên có chứa chữ Forge / NeoForge
            let idLower = id.toLowerCase();
            if (idLower.includes('forge') || idLower.includes('neoforge')) {
                type = 'modded'; 
            }

            // THUẬT TOÁN PHÂN LOẠI MÀU SẮC VÀ ICON:
            let textColor = '#FFFFFF'; // Mặc định: Trắng (Vanilla đã download)
            let icon = '✅';          // Icon mặc định

            if (type === 'modded') {
                textColor = '#F39C12'; // Màu cam vàng rực rỡ cho Forge / NeoForge
                icon = '🛠️';           // Icon sửa chữa/chế tạo cho bản Mod
            } else if (!isDownloaded) {
                textColor = '#718096'; // Màu xám (Gray) cho các phiên bản chưa tải xuống
                icon = '📥';           // Icon mũi tên tải xuống nhìn trực quan hơn
            }

            // Trả về HTML kèm thuộc tính style="color: ..." tương ứng
            return `<div class="version-item" style="color: ${textColor};" onclick="selectVersion('${id}')">${icon}  ${id}</div>`;
        }).join('');
    }
}

function selectVersion(versionStr) {
    selectedVersion = versionStr;
    const btnVersion = document.getElementById('version-select-btn');
    const dropdown = document.getElementById('version-dropdown');
    if (btnVersion) btnVersion.innerText = `📦 ${versionStr}`;
    if (dropdown) dropdown.classList.add('hidden'); // Đóng list bằng cách thêm lại class hidden
}

// Khớp với onclick="toggleVersionMenu()" trong HTML của bạn
function toggleVersionMenu() {
    const dropdown = document.getElementById('version-dropdown');
    if (!dropdown) return;
    
    // Ngăn nổi bọt sự kiện lên document
    if (window.event) window.event.stopPropagation();
    
    // Bật/tắt menu bằng class hidden (vừa an toàn vừa không bị !important đè bẹp)
    dropdown.classList.toggle('hidden');
}

// Khớp với onclick="refreshVersions()" trong HTML của bạn
function refreshVersions() {
    window.updateStatus("Refreshing versions from Mojang...", "#94a3b8");
    window.pywebview.api.refresh_versions();
}

// ==========================================
// 4. LOGIC XỬ LÝ SỰ KIỆN NÚT BẤM GIAO DIỆN
// ==========================================

// Khớp với onclick="handlePlayClick()" của nút PLAY trong HTML
function handlePlayClick() {
    let txtUsername = document.getElementById("username");
    if (!txtUsername) return;

    let username = txtUsername.value.trim(); // Dùng .trim() thay vì .strip() cũ bị lỗi
    let version = selectedVersion;
    let remember = document.getElementById("remember-username")?.checked || false;
	
	// --- THÊM DÒNG NÀY ĐỂ LẤY TRẠNG THÁI CHECKBOX ---
    let keepLauncherOpen = document.getElementById("keep-launcher-open")?.checked || false;

    if (!username) {
        window.updateStatus("Please enter a username!", "#E74C3C");
        return;
    }
    window.updateStatus("Preparing to launch...", "#3498DB");
    window.pywebview.api.launch_game(username, version, remember, keepLauncherOpen);
}

// 1. Tạo một biến toàn cục ở ngoài hàm để quản lý bộ đếm thời gian (chống lỗi chữ nhảy loạn khi click nhanh)
let profileStatusTimeout = null;

function handleProfileChange() {
    let profileSelect = document.getElementById("profile-select");
    if (!profileSelect) return;
    let selectedProfile = profileSelect.value;
    
    // Nếu có bộ đếm ngược của lần click trước đó chưa chạy xong, xóa nó đi ngay
    if (profileStatusTimeout) clearTimeout(profileStatusTimeout);
    
    window.updateStatus(`Switching to profile: ${selectedProfile}...`, "#94a3b8");
    
    // Gọi Python xử lý đổi profile và trả về dữ liệu của profile mới
    window.pywebview.api.switch_profile(selectedProfile).then(data => {
        let txtUsername = document.getElementById("username");
        let chkRemember = document.getElementById("remember-username");
        
        if (txtUsername) txtUsername.value = data.profile_data.username || "";
        if (chkRemember) chkRemember.checked = data.profile_data.remember || false;
        
        if (data.versions_ready) {
            renderVersions(data.versions, data.profile_data.version);
        }
        
        // KÍCH HOẠT THÔNG BÁO THÀNH CÔNG (Màu xanh)
        window.updateStatus(`Switched to profile: ${selectedProfile}`, "#2ECC71");
        
        // ĐẶT LỊCH: Đúng 2 giây (2000ms) sau sẽ tự động đổi lại thành "Ready"
        profileStatusTimeout = setTimeout(() => {
            window.updateStatus("Ready", "#94a3b8"); // Bạn có thể đổi chữ "Ready" hoặc mã màu tùy ý
        }, 2000);
    });
}

// ui/web/app.js

async function createNewProfile() {
    try {
        window.updateStatus("Creating new profile...", "#94a3b8");

        // 1. Gọi Python tạo một profile trống với các thông số mặc định
        const newProfileName = await window.pywebview.api.web_create_profile();
        
        // 2. Nạp lại danh sách Profile lên Dropdown ngoài màn hình chính
        // (Hãy đảm bảo tên hàm khởi tạo giao diện của bạn là initializeLauncher)
        await initializeLauncher(); 
        
        // 3. Tự động nhảy thanh cuộn Select sang Profile mới vừa tạo
        let chkKeepOpen = document.getElementById("keep-launcher-open");
        if (chkKeepOpen) {
            const savedKeepOption = localStorage.getItem("keepLauncherOpen");
            if (savedKeepOption !== null) {
                chkKeepOpen.checked = savedKeepOption === "true";
            } else {
                chkKeepOpen.checked = false; // Mặc định không tích chọn -> Tắt khi chạy game
            }

            chkKeepOpen.onchange = function() {
                localStorage.setItem("keepLauncherOpen", chkKeepOpen.checked);
            };
        }
        
        window.updateStatus("New profile created! Please customize it.", "#2ECC71");
    } catch (err) {
        console.error("Lỗi tạo profile:", err);
        window.updateStatus("Error creating profile!", "#E74C3C");
    }
}

// ui/web/app.js

let currentEditingOldId = ""; // Lưu lại tên ID cũ phòng trường hợp đổi tên profile

// Hàm được kích hoạt khi bấm nút "⚙️ Edit" ngoài màn hình chính
function editProfile() {
    let profileSelect = document.getElementById("profile-select");
    if (!profileSelect) return;
    
    currentEditingOldId = profileSelect.value; // Lấy tên profile đang được chọn hiện tại

    // Gọi Python lấy thông tin chi tiết của profile này lên điền vào form
    window.pywebview.api.get_profile_details(currentEditingOldId).then(prof => {
        document.getElementById("edit-profile-name").value = prof.name || currentEditingOldId;
        document.getElementById("edit-game-dir").value = prof.game_dir || "";
        document.getElementById("edit-jvm-args").value = prof.jvm_args || "";
        
        let javaManual = prof.java_manual || false;
        document.getElementById("edit-java-manual").checked = javaManual;
        document.getElementById("edit-java-path").value = prof.java_path || "";
        
        document.getElementById("edit-allow-snapshot").checked = prof.allow_snapshots || false;
        document.getElementById("edit-allow-beta").checked = prof.allow_beta || false;
        document.getElementById("edit-allow-alpha").checked = prof.allow_alpha || false;

        toggleJavaInputVisibility();
        // Mở modal lên bằng cách bỏ class ẩn đi
        document.getElementById("edit-modal").classList.remove("hidden");
    }).catch(err => console.error("Không lấy được dữ liệu profile:", err));
	
	// Thêm 2 dòng này vào cuối hàm editProfile() hiện tại của bạn
    document.getElementById("delete-game-files").checked = false;
    document.getElementById("delete-warning-text").classList.add("hidden");
}

function closeEditModal() {
    document.getElementById("edit-modal").classList.add("hidden");
}

// Bật tắt trạng thái ô nhập Java tùy theo nút tích Chọn thủ công
function toggleJavaInputVisibility() {
    let isManual = document.getElementById("edit-java-manual").checked;
    document.getElementById("edit-java-path").disabled = !isManual;
    document.getElementById("btn-browse-java").disabled = !isManual;
    // Đổi mờ/rõ ô nhập cho trực quan
    document.getElementById("edit-java-path").style.opacity = isManual ? "1" : "0.4";
    document.getElementById("btn-browse-java").style.opacity = isManual ? "1" : "0.4";
}

// Gọi Python mở cửa sổ chọn thư mục game
function browseGameDir() {
    window.pywebview.api.web_browse_directory().then(path => {
        if (path) document.getElementById("edit-game-dir").value = path;
    });
}

// Gọi Python mở cửa sổ chọn file java.exe
function browseJavaPath() {
    window.pywebview.api.web_browse_file().then(path => {
        if (path) document.getElementById("edit-java-path").value = path;
    });
}

// Gọi Python mở trực tiếp thư mục game trên Explorer của máy tính
function openGameFolderNative() {
    let path = document.getElementById("edit-game-dir").value.trim();
    window.pywebview.api.web_open_folder(path);
}

// Gom toàn bộ dữ liệu trên giao diện gửi xuống cho Python xử lý lưu file JSON
function saveProfileSettings() {
    let newName = document.getElementById("edit-profile-name").value.trim();
    let gameDir = document.getElementById("edit-game-dir").value.trim();
    let jvmArgs = document.getElementById("edit-jvm-args").value.trim();
    let javaManual = document.getElementById("edit-java-manual").checked;
    let javaPath = document.getElementById("edit-java-path").value.trim();
    let allowSnapshot = document.getElementById("edit-allow-snapshot").checked;
    let allowBeta = document.getElementById("edit-allow-beta").checked;
    let allowAlpha = document.getElementById("edit-allow-alpha").checked;

    window.updateStatus("Saving profile settings...", "#94a3b8");

    window.pywebview.api.web_save_profile(
        currentEditingOldId, newName, gameDir, jvmArgs, 
        javaManual, javaPath, allowSnapshot, allowBeta, allowAlpha
    ).then(response => {
        closeEditModal();
        // Gọi lại hàm khởi tạo để đồng bộ lại toàn bộ UI ngoài màn hình chính (Danh sách phiên bản, Profile mới...)
        initializeLauncher();
        window.updateStatus("Profile saved successfully!", "#2ECC71");
    }).catch(err => {
        console.error(err);
        window.updateStatus("Error saving profile!", "#E74C3C");
    });
}

// ui/web/app.js

// Hàm bắt sự kiện onchange: Tích chọn thì hiện chữ cam, bỏ tích thì ẩn đi
function toggleDeleteWarning() {
    let isChecked = document.getElementById("delete-game-files").checked;
    let warningText = document.getElementById("delete-warning-text");
    if (isChecked) {
        warningText.classList.remove("hidden");
    } else {
        warningText.classList.add("hidden");
    }
}

// Hàm thực thi việc xóa profile
function removeCurrentProfile() {
    if (!currentEditingOldId) return;

    let deleteFiles = document.getElementById("delete-game-files").checked;
    
    // Tạo thông báo xác nhận nhắc nhở người dùng bằng hộp thoại native
    let confirmMsg = `Are you sure you want to completely REMOVE the profile "${currentEditingOldId}"?`;
    if (deleteFiles) {
        confirmMsg += "\n\n⚠️ WARNING: YOU SELECTED TO DELETE ALL DATA FILES! THIS WILL WIPE OUT THE GAME FOLDER FOREVER!";
    }

    if (!confirm(confirmMsg)) return;

    window.updateStatus("Processing profile removal...", "#94a3b8");

    // Gọi API xuống tầng Python xử lý file
    window.pywebview.api.web_remove_profile(currentEditingOldId, deleteFiles)
        .then(response => {
            // Xóa thành công thì đóng modal lại
            closeEditModal();
            
            // Khởi động lại giao diện màn hình chính (để nạp lại dropdown menu mới)
            initializeLauncher().then(() => {
                handleProfileChange();
            });
            window.updateStatus("Profile removed successfully!", "#E74C3C");
        })
        .catch(err => {
            console.error("Lỗi xóa profile:", err);
            window.updateStatus("Error trying to remove profile!", "#E74C3C");
        });
}

// ==========================================
// LOGIC CLICK RA NGOÀI ĐỂ ĐÓNG LIST VERSION
// ==========================================
document.addEventListener('click', function (event) {
    const dropdown = document.getElementById('version-dropdown');
    const btnVersion = document.getElementById('version-select-btn');

    if (!dropdown || !btnVersion) return;

    // Nếu vị trí click nằm ngoài cả nút bấm và danh sách dropdown thì đóng lại bằng class hidden
    if (!btnVersion.contains(event.target) && !dropdown.contains(event.target)) {
        dropdown.classList.add('hidden'); 
    }
});