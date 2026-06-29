// ui/web/app.js

let selectedVersion = "";

// ==========================================
// 1. CALLBACKS CALLED BY PYTHON VIA evaluate_js
// ==========================================

window.onVersionsLoaded = function(versionsList, savedVersion) {
    renderVersions(versionsList, savedVersion);
};

window.updateStatus = function(message, color) {
    const el = document.getElementById("status");
    if (el) { el.innerText = message; el.style.color = color; }

    const level = (color === "#E74C3C" || color === "red")    ? "error"
                : (color === "#E67E22" || color === "orange")  ? "warn"
                : "info";
    appendLog(`[${level.toUpperCase()}] ${message}`, level);
};

window.updateProgress = function(percentage) {
    const container = document.getElementById("progress-container");
    const bar       = document.getElementById("progress-bar");
    if (container) container.classList.remove("hidden");
    if (bar)       bar.style.width = percentage + "%";
};

window.launchSuccess = function() {
    window.updateStatus("Launched successfully! Have fun.", "#2ECC71");
};

// ==========================================
// 2. TAB SWITCHING
// ==========================================

function switchTab(name) {
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    document.getElementById("tab-" + name).classList.add("active");
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.getElementById("tbtn-" + name).classList.add("active");
}

// ==========================================
// 3. CONSOLE LOGGING
// ==========================================

let _consoleLineCount = 1;

function appendLog(text, level) {
    const box = document.getElementById("console-output");
    if (!box) return;

    if (!level) {
        const t = text.toUpperCase();
        level = t.includes("[ERROR]") || t.includes("[CRITICAL]") ? "error"
              : t.includes("[WARN]")  || t.includes("[WARNING]")  ? "warn"
              : t.includes("[DEBUG]")                              ? "debug"
              : "info";
    }

    const span = document.createElement("span");
    span.className = "log-" + level;
    if (!text.trim().startsWith("[")) {
        span.classList.add("log-continuation");
    }
    span.textContent = text;
    box.appendChild(span);
    box.appendChild(document.createTextNode("\n"));

    _consoleLineCount++;
    const counter = document.getElementById("console-line-count");
    if (counter) counter.textContent =
        _consoleLineCount === 1 ? "1 line" : _consoleLineCount + " lines";

    if (box.scrollTop + box.clientHeight >= box.scrollHeight - 60) {
        box.scrollTop = box.scrollHeight;
    }
}

function clearConsole() {
    const box = document.getElementById("console-output");
    if (box) box.innerHTML = "";
    _consoleLineCount = 0;
    const counter = document.getElementById("console-line-count");
    if (counter) counter.textContent = "0 lines";
}

// ==========================================
// 4. INITIALISE & SYNC PROFILE DATA
// ==========================================

function initializeLauncher() {
    if (!window.pywebview || !window.pywebview.api) return;

    return window.pywebview.api.get_initial_data().then(data => {
        // 4.1  Rebuild profile dropdown and select the active profile
        _rebuildProfileDropdown(data.profiles_list, data.current_profile);

        // 4.2  Username + remember checkbox
        const txtUsername = document.getElementById("username");
        const chkRemember = document.getElementById("remember-username");
        if (txtUsername) txtUsername.value   = data.profile_data.username || "";
        if (chkRemember) chkRemember.checked = data.profile_data.remember || false;

        // 4.3  Persistent checkboxes (localStorage)
        _initCheckboxFromStorage("keep-launcher-open", "keepLauncherOpen", false);

        // 4.4  Segoe UI font toggle
        const chkUseSegoe = document.getElementById("use-segoe-font");
        if (chkUseSegoe) {
            const useSegoe = localStorage.getItem("useSegoeFont") === "true";
            chkUseSegoe.checked = useSegoe;
            document.body.classList.toggle("segoe-active", useSegoe);
            chkUseSegoe.onchange = function() {
                localStorage.setItem("useSegoeFont", this.checked);
                document.body.classList.toggle("segoe-active", this.checked);
            };
        }

        // 4.5  Version list
        if (data.versions_ready) {
            renderVersions(data.versions, data.profile_data.version);
        } else {
            const btnVersion = document.getElementById("version-select-btn");
            if (btnVersion) btnVersion.innerText = "⏳ Fetching versions from Mojang...";
        }

    }).catch(err => {
        appendLog("[ERROR] Launcher init error: " + err, "error");
    });
}

/**
 * Rebuild the profile <select> with a fresh list and select the given profile.
 * Kept as a standalone helper so saveProfileSettings, createNewProfile, and
 * removeCurrentProfile can all use it without calling full initializeLauncher.
 */
function _rebuildProfileDropdown(profilesList, activeProfile) {
    const profileSelect = document.getElementById("profile-select");
    if (!profileSelect || !profilesList) return;
    profileSelect.innerHTML = profilesList
        .map(p => `<option value="${p}" ${p === activeProfile ? "selected" : ""}>${p}</option>`)
        .join("");
}

function _initCheckboxFromStorage(elementId, storageKey, defaultValue) {
    const chk = document.getElementById(elementId);
    if (!chk) return;
    const saved = localStorage.getItem(storageKey);
    chk.checked = saved !== null ? saved === "true" : defaultValue;
    chk.onchange = function() { localStorage.setItem(storageKey, this.checked); };
}

if (window.pywebview) {
    initializeLauncher();
} else {
    window.addEventListener("pywebviewready", initializeLauncher);
}

// ==========================================
// 5. VERSION LIST RENDERING
// ==========================================

function renderVersions(versionsList, savedVersion) {
    const dropdown   = document.getElementById("version-dropdown");
    const btnVersion = document.getElementById("version-select-btn");
    if (!btnVersion) return;

    if (!versionsList || versionsList.length === 0) {
        btnVersion.innerText = "⚠️ No versions available";
        return;
    }

    const firstId = typeof versionsList[0] === "object" ? versionsList[0].id : versionsList[0];
    selectedVersion = savedVersion || firstId;
    btnVersion.innerText = `📦 ${selectedVersion}`;

    if (dropdown) {
        dropdown.innerHTML = versionsList.map(ver => {
            const id           = typeof ver === "object" ? ver.id           : ver;
            const isDownloaded = typeof ver === "object" ? ver.is_downloaded : false;
            let   type         = typeof ver === "object" ? ver.type          : "vanilla";

            const idLower = id.toLowerCase();
            if (idLower.includes("forge") || idLower.includes("neoforge")) type = "modded";

            let color, icon;
            if (type === "modded")      { color = "#F39C12"; icon = "🛠️"; }
            else if (!isDownloaded)     { color = "#718096"; icon = "📥"; }
            else                        { color = "#FFFFFF"; icon = "✅"; }

            return `<div class="version-item" style="color:${color};" onclick="selectVersion('${id}')">${icon}  ${id}</div>`;
        }).join("");
    }
}

function selectVersion(versionStr) {
    selectedVersion = versionStr;
    const btnVersion = document.getElementById("version-select-btn");
    const dropdown   = document.getElementById("version-dropdown");
    if (btnVersion) btnVersion.innerText = `📦 ${versionStr}`;
    if (dropdown)   dropdown.classList.add("hidden");
}

function toggleVersionMenu() {
    const dropdown = document.getElementById("version-dropdown");
    if (!dropdown) return;
    if (window.event) window.event.stopPropagation();
    dropdown.classList.toggle("hidden");
}

function refreshVersions() {
    window.updateStatus("Refreshing versions from Mojang...", "#94a3b8");
    window.pywebview.api.refresh_versions();
}

// ==========================================
// 6. PLAY BUTTON
// ==========================================

function handlePlayClick() {
    const txtUsername = document.getElementById("username");
    if (!txtUsername) return;

    const username         = txtUsername.value.trim();
    const version          = selectedVersion;
    const remember         = document.getElementById("remember-username")?.checked  || false;
    const keepLauncherOpen = document.getElementById("keep-launcher-open")?.checked || false;

    if (!username) {
        window.updateStatus("Please enter a username!", "#E74C3C");
        return;
    }
    window.updateStatus("Preparing to launch...", "#3498DB");
    window.pywebview.api.launch_game(username, version, remember, keepLauncherOpen);
}

// ==========================================
// 7. PROFILE SWITCHING
// ==========================================

let profileStatusTimeout = null;

function handleProfileChange() {
    const profileSelect = document.getElementById("profile-select");
    if (!profileSelect) return;
    const selectedProfile = profileSelect.value;

    if (profileStatusTimeout) clearTimeout(profileStatusTimeout);
    window.updateStatus(`Switching to profile: ${selectedProfile}...`, "#94a3b8");

    window.pywebview.api.switch_profile(selectedProfile).then(data => {
        if (!data) return;
        const txtUsername = document.getElementById("username");
        const chkRemember = document.getElementById("remember-username");
        if (txtUsername) txtUsername.value   = data.profile_data.username || "";
        if (chkRemember) chkRemember.checked = data.profile_data.remember || false;

        if (data.versions_ready) renderVersions(data.versions, data.profile_data.version);

        window.updateStatus(`Switched to profile: ${selectedProfile}`, "#2ECC71");
        profileStatusTimeout = setTimeout(() => window.updateStatus("Ready.", "#94a3b8"), 2000);
    });
}

// ==========================================
// 8. CREATE / EDIT / REMOVE PROFILE
// ==========================================

async function createNewProfile() {
    try {
        window.updateStatus("Creating new profile...", "#94a3b8");
        const newProfileName = await window.pywebview.api.web_create_profile();
        // Full reinit so the dropdown and all fields are in sync
        await initializeLauncher();
        // Then select the newly created profile in the dropdown
        const profileSelect = document.getElementById("profile-select");
        if (profileSelect) profileSelect.value = newProfileName;
        _initCheckboxFromStorage("keep-launcher-open", "keepLauncherOpen", false);
        window.updateStatus("New profile created! Please customize it.", "#2ECC71");
    } catch (err) {
        appendLog("[ERROR] createNewProfile: " + err, "error");
        window.updateStatus("Error creating profile!", "#E74C3C");
    }
}

// Tracks the key used to open the modal so we can pass it to Python on save.
// Updated to the NEW name after a successful rename so the edit button works
// again without reopening the launcher.
let currentEditingOldId = "";

function editProfile() {
    const profileSelect = document.getElementById("profile-select");
    if (!profileSelect) return;

    // Always read the current dropdown value — after a rename the dropdown
    // already shows the new name (we update it on save), so this is correct.
    currentEditingOldId = profileSelect.value;

    window.pywebview.api.get_profile_details(currentEditingOldId).then(prof => {
        if (!prof) {
            appendLog("[ERROR] editProfile: profile not found — " + currentEditingOldId, "error");
            return;
        }
        document.getElementById("edit-profile-name").value     = prof.name      || currentEditingOldId;
        document.getElementById("edit-game-dir").value         = prof.game_dir  || "";
        document.getElementById("edit-jvm-args").value         = prof.jvm_args  || "";
        document.getElementById("edit-java-manual").checked    = prof.java_manual || false;
        document.getElementById("edit-java-path").value        = prof.java_path  || "";
        document.getElementById("edit-allow-snapshot").checked = prof.allow_snapshots || false;
        document.getElementById("edit-allow-beta").checked     = prof.allow_beta     || false;
        document.getElementById("edit-allow-alpha").checked    = prof.allow_alpha    || false;

        toggleJavaInputVisibility();
        document.getElementById("edit-modal").classList.remove("hidden");
    }).catch(err => appendLog("[ERROR] editProfile: " + err, "error"));

    document.getElementById("delete-game-files").checked = false;
    document.getElementById("delete-warning-text").classList.add("hidden");
}

function closeEditModal() {
    document.getElementById("edit-modal").classList.add("hidden");
}

function toggleJavaInputVisibility() {
    const isManual  = document.getElementById("edit-java-manual").checked;
    const pathInput = document.getElementById("edit-java-path");
    const browseBtn = document.getElementById("btn-browse-java");
    pathInput.disabled      = !isManual;
    browseBtn.disabled      = !isManual;
    pathInput.style.opacity = isManual ? "1" : "0.4";
    browseBtn.style.opacity = isManual ? "1" : "0.4";
}

function browseGameDir() {
    window.pywebview.api.web_browse_directory().then(path => {
        if (path) document.getElementById("edit-game-dir").value = path;
    });
}

function browseJavaPath() {
    window.pywebview.api.web_browse_file().then(path => {
        if (path) document.getElementById("edit-java-path").value = path;
    });
}

function openGameFolderNative() {
    const path = document.getElementById("edit-game-dir").value.trim();
    window.pywebview.api.web_open_folder(path);
}

async function saveProfileSettings() {
    const newName       = document.getElementById("edit-profile-name").value.trim();
    const gameDir       = document.getElementById("edit-game-dir").value.trim();
    const jvmArgs       = document.getElementById("edit-jvm-args").value.trim();
    const javaManual    = document.getElementById("edit-java-manual").checked;
    const javaPath      = document.getElementById("edit-java-path").value.trim();
    const allowSnapshot = document.getElementById("edit-allow-snapshot").checked;
    const allowBeta     = document.getElementById("edit-allow-beta").checked;
    const allowAlpha    = document.getElementById("edit-allow-alpha").checked;

    // The effective new name (falls back to old if left blank)
    const resolvedName = newName || currentEditingOldId;

    window.updateStatus("Saving profile settings...", "#94a3b8");

    try {
        await window.pywebview.api.web_save_profile(
            currentEditingOldId, newName, gameDir, jvmArgs,
            javaManual, javaPath, allowSnapshot, allowBeta, allowAlpha
        );

        // FIX 1: Update currentEditingOldId to the new name immediately so
        // the edit button works again without a launcher restart.
        currentEditingOldId = resolvedName;

        closeEditModal();

        // FIX 2: Ask Python for the fresh profile list and rebuild the
        // dropdown — this is the only place that was missing after a rename.
        const data = await window.pywebview.api.switch_profile(resolvedName);
        if (data) {
            // Rebuild the dropdown with the updated list and select new name
            _rebuildProfileDropdown(
                await _fetchProfilesList(),
                resolvedName
            );

            const txtUsername = document.getElementById("username");
            const chkRemember = document.getElementById("remember-username");
            if (txtUsername) txtUsername.value   = data.profile_data.username || "";
            if (chkRemember) chkRemember.checked = data.profile_data.remember || false;
            if (data.versions_ready) renderVersions(data.versions, data.profile_data.version);
        }

        window.updateStatus("Profile saved successfully!", "#2ECC71");

    } catch (err) {
        appendLog("[ERROR] saveProfileSettings: " + err, "error");
        window.updateStatus("Error saving profile!", "#E74C3C");
    }
}

/**
 * Fetch the current profiles list from Python without doing a full reinit.
 * Used after save so we can rebuild just the dropdown.
 */
async function _fetchProfilesList() {
    const data = await window.pywebview.api.get_initial_data();
    return data ? data.profiles_list : [];
}

// ==========================================
// 9. REMOVE PROFILE
// ==========================================

function toggleDeleteWarning() {
    const isChecked   = document.getElementById("delete-game-files").checked;
    const warningText = document.getElementById("delete-warning-text");
    warningText.classList.toggle("hidden", !isChecked);
}

async function removeCurrentProfile() {
    if (!currentEditingOldId) return;
    const deleteFiles = document.getElementById("delete-game-files").checked;
    let confirmMsg = `Are you sure you want to completely REMOVE the profile "${currentEditingOldId}"?`;
    if (deleteFiles) confirmMsg += "\n\n⚠️ WARNING: YOU SELECTED TO DELETE ALL DATA FILES! THIS WILL WIPE OUT THE GAME FOLDER FOREVER!";
    if (!confirm(confirmMsg)) return;

    window.updateStatus("Processing profile removal...", "#94a3b8");

    try {
        // FIX 3: await the removal before doing anything else — previously
        // the success status was set synchronously before the promise resolved,
        // and handleProfileChange fired before the dropdown was rebuilt.
        await window.pywebview.api.web_remove_profile(currentEditingOldId, deleteFiles);
        closeEditModal();
        currentEditingOldId = "";

        // Full reinit rebuilds the dropdown with the surviving profiles
        await initializeLauncher();

        // Now it's safe to trigger profile-change logic on whatever is selected
        handleProfileChange();

        window.updateStatus("Profile removed successfully!", "#E74C3C");
    } catch (err) {
        appendLog("[ERROR] removeCurrentProfile: " + err, "error");
        window.updateStatus("Error trying to remove profile!", "#E74C3C");
    }
}

// ==========================================
// 10. CLOSE VERSION DROPDOWN ON OUTSIDE CLICK
// ==========================================

document.addEventListener("click", function(event) {
    const dropdown   = document.getElementById("version-dropdown");
    const btnVersion = document.getElementById("version-select-btn");
    if (!dropdown || !btnVersion) return;
    if (!btnVersion.contains(event.target) && !dropdown.contains(event.target)) {
        dropdown.classList.add("hidden");
    }
});