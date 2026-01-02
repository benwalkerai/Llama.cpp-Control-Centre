// Llama.cpp Control Centre - Main JavaScript

// ===== Global State =====
let chatHistory = [];
let isServerRunning = false;
let currentChatServerId = null;
let availableModels = [];
let wsConnection = null;
let activeConsoleServerId = null;
let consoleInterval = null;

// ===== Utility Functions =====
function showAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('alerts');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;

    alertsContainer.appendChild(alert);

    setTimeout(() => {
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
}

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`/api${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'API request failed');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        showAlert(error.message, 'error');
        throw error;
    }
}

function formatTime(seconds) {
    if (!seconds || seconds < 0 || seconds === Infinity) return '--:--';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// ===== Hardware Functions =====
async function loadHardwareInfo() {
    try {
        const result = await apiCall('/hardware/info');
        const info = result.data;

        // Update CPU
        document.getElementById('cpuCores').textContent =
            `${info.cpu.cores_physical || 'N/A'} (${info.cpu.cores_logical || 'N/A'} threads)`;

        // Update RAM
        document.getElementById('ramAvailable').textContent =
            `${info.memory.available_gb} GB / ${info.memory.total_gb} GB`;

        // Update GPU
        const gpu = info.gpu;
        if (gpu.available) {
            document.getElementById('gpuStatus').textContent = gpu.name || 'Detected';
            document.getElementById('vram').textContent =
                gpu.vram_gb ? `${gpu.vram_gb} GB` : 'N/A';
        } else {
            document.getElementById('gpuStatus').textContent = 'Not Detected';
            document.getElementById('vram').textContent = 'N/A';
        }

        // Load recommendations
        await loadRecommendations();

        showAlert('Hardware info refreshed', 'success');
    } catch (error) {
        console.error('Failed to load hardware info:', error);
    }
}

async function loadRecommendations() {
    try {
        const result = await apiCall('/hardware/recommendations');
        const rec = result.data;

        let html = '<strong>Recommended Parameters:</strong><br>';
        html += `• Context Size: ${rec.n_ctx}<br>`;
        html += `• GPU Layers: ${rec.n_gpu_layers}<br>`;
        html += `• Threads: ${rec.n_threads}<br>`;

        if (rec.reasoning && rec.reasoning.length > 0) {
            html += '<br><strong>Notes:</strong><br>';
            rec.reasoning.forEach(reason => {
                html += `• ${reason}<br>`;
            });
        }

        document.getElementById('recommendations').innerHTML = html;


        document.getElementById('recommendations').innerHTML = html;

        // Auto-fill removed
        /*
        document.getElementById('nCtx').value = rec.n_ctx;
        document.getElementById('nGpuLayers').value = rec.n_gpu_layers;
        document.getElementById('nThreads').value = rec.n_threads;
        */
    } catch (error) {
        console.error('Failed to load recommendations:', error);
    }
}

// ===== Server Functions =====
async function loadServerLogs() {
    try {
        const result = await apiCall('/server/logs?lines=20');
        const logs = result.data;

        if (logs && logs.length > 0) {
            document.getElementById('serverLogs').innerHTML = logs.join('<br>');
        }
    } catch (error) {
        console.error('Failed to load server logs:', error);
    }
}


async function loadModels() {
    try {
        const result = await apiCall('/models/list');
        const models = result.data;
        availableModels = models;

        const modelsList = document.getElementById('modelsList');

        // Update modal dropdown
        const modelSelect = document.getElementById('serverModel');
        if (modelSelect) {
            modelSelect.innerHTML = '<option value="" disabled selected>Select a model...</option>' +
                models.map(model => `<option value="${model.path}">${model.name}</option>`).join('');
        }

        if (models.length === 0) {
            modelsList.innerHTML = '<div class="empty-state">No models found. Download a model to get started.</div>';
            return;
        }

        modelsList.innerHTML = models.map(model => `
            <div class="model-item">
                <div class="model-info">
                    <div class="model-name">${model.name}</div>
                    <div class="model-meta">${(model.size / (1024 * 1024 * 1024)).toFixed(2)} GB • Modified: ${new Date(model.modified).toLocaleDateString()}</div>
                </div>
                <div class="model-actions">
                    <button class="btn btn-small btn-danger" onclick="deleteModel('${model.name}')" title="Delete Model">🗑️</button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function downloadModel() {
    console.log('Download button clicked');
    const repoId = document.getElementById('repoId').value.trim();
    const filename = document.getElementById('modelFilename').value.trim();

    console.log(`Repo: ${repoId}, Filename: ${filename}`);

    let finalRepoId = repoId;
    let finalFilename = filename;

    // Support for full Hugging Face URLs
    // Example: https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/blob/main/llama-2-7b-chat.Q4_K_M.gguf
    if (repoId.includes('huggingface.co/')) {
        try {
            const url = new URL(repoId);
            const pathParts = url.pathname.split('/').filter(p => p);

            // Expected path: /repo_owner/repo_name/blob/branch/filename
            if (pathParts.length >= 2) {
                finalRepoId = `${pathParts[0]}/${pathParts[1]}`;

                // If filename is in the URL (blob/main/filename)
                if (pathParts.includes('blob') || pathParts.includes('resolve')) {
                    const typeIdx = pathParts.indexOf('blob') !== -1 ? pathParts.indexOf('blob') : pathParts.indexOf('resolve');
                    if (pathParts.length > typeIdx + 2) {
                        finalFilename = pathParts.slice(typeIdx + 2).join('/');
                    }
                }
            }
        } catch (e) {
            console.error('URL parsing failed:', e);
        }
    }

    if (!finalRepoId || !finalFilename) {
        console.warn('Missing fields');
        showAlert('Please fill in all fields (or paste a valid HF URL)', 'error');
        return;
    }

    try {
        console.log('Starting download request...');
        // Show progress container
        const progressContainer = document.getElementById('downloadProgress');
        const progressBar = document.getElementById('downloadProgressBar');
        const progressText = document.getElementById('downloadProgressText');
        const progressStats = document.getElementById('downloadStats');

        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressText.textContent = 'Starting download...';
        progressStats.innerHTML = '';

        const response = await apiCall('/models/download', {
            method: 'POST',
            body: JSON.stringify({ repo_id: finalRepoId, filename: finalFilename })
        });
        console.log('Download request sent', response);

        // Start polling status
        const pollInterval = setInterval(async () => {
            const statusResult = await apiCall('/models/download/status');
            const status = statusResult.data;

            if (!status.is_downloading) {
                clearInterval(pollInterval);
                loadModels();

                if (status.last_error) {
                    progressBar.style.width = '0%';
                    progressText.textContent = `Error: ${status.last_error}`;
                    showAlert(`Download failed: ${status.last_error}`, 'error');
                } else if (status.current_file) {
                    progressBar.style.width = '100%';
                    progressText.textContent = 'Download completed!';
                    showAlert('Download completed!', 'success');
                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                    }, 5000);
                }
            } else {
                // Update UI
                progressBar.style.width = `${status.progress}%`;

                // Main status text
                progressText.textContent = `Downloading ${status.current_file}... ${status.progress}%`;

                // Detailed stats: X MB / Y MB • Z MB/s • ETA: 5s
                if (status.total_size_mb > 0) {
                    const sizeStr = `${status.current_size_mb.toFixed(1)} / ${status.total_size_mb.toFixed(1)} MB`;
                    const speedStr = `${status.speed_mb_s.toFixed(1)} MB/s`;
                    const etaStr = status.eta_seconds ? `ETA: ${formatTime(status.eta_seconds)}` : 'Calculating...';

                    progressStats.innerHTML = `
                        <span>${sizeStr}</span>
                        <span>${speedStr} • ${etaStr}</span>
                    `;
                } else {
                    progressStats.innerHTML = `<span>Preparing...</span>`;
                }
            }
        }, 500);


    } catch (error) {
        showAlert(error.message, 'error');
    }
}

async function deleteModel(modelName) {
    if (!confirm(`Are you sure you want to delete ${modelName}?`)) {
        return;
    }

    try {
        await apiCall(`/models/delete/${encodeURIComponent(modelName)}`, {
            method: 'DELETE'
        });

        showAlert('Model deleted successfully', 'success');
        await loadModels();
    } catch (error) {
        console.error('Failed to delete model:', error);
    }
}


// ===== Server Management =====
let editingServerId = null;

// Open/Close Create Server Modal
async function openCreateServerModal(isEdit = false, serverId = null) {
    const modalTitle = document.getElementById('serverModalTitle');
    const saveBtnText = document.getElementById('saveServerBtnText');

    if (isEdit && serverId) {
        editingServerId = serverId;
        modalTitle.textContent = 'Edit Server';
        saveBtnText.textContent = 'Update';

        try {
            const res = await apiCall(`/servers/${serverId}`);
            const server = res.data;
            if (server) {
                document.getElementById('serverName').value = server.name;

                // Improved path matching for the dropdown
                const modelSelect = document.getElementById('serverModel');
                const options = Array.from(modelSelect.options);
                const matchingOption = options.find(o => o.value === server.model_path);
                if (matchingOption) {
                    modelSelect.value = server.model_path;
                } else {
                    // Try to match by filename if absolute path fails
                    const filename = server.model_path.split(/[/\\]/).pop();
                    const fuzzyMatch = options.find(o => o.value.endsWith(filename));
                    if (fuzzyMatch) {
                        modelSelect.value = fuzzyMatch.value;
                    }
                }

                document.getElementById('serverPort').value = server.port || 8001;

                const config = server.config || {};
                document.getElementById('serverCtx').value = config.n_ctx || 2048;
                document.getElementById('serverGpu').value = config.n_gpu_layers || 0;
                document.getElementById('serverThreads').value = config.n_threads || '';
                document.getElementById('serverTemp').value = config.temperature || 0.7;
                document.getElementById('serverTopP').value = config.top_p || 0.9;
                document.getElementById('serverTopK').value = config.top_k || 40;
                document.getElementById('serverRepeat').value = config.repeat_penalty || 1.1;

                document.getElementById('createServerModal').classList.add('active');
            }
        } catch (error) {
            showAlert('Failed to load server configuration', 'error');
        }

    } else {
        editingServerId = null;
        modalTitle.textContent = 'Create New Server';
        saveBtnText.textContent = 'Create';

        // Clear fields
        document.getElementById('serverName').value = '';
        document.getElementById('serverModel').value = '';
        document.getElementById('serverPort').value = '8001';
        document.getElementById('serverCtx').value = '2048';
        document.getElementById('serverThreads').value = '';
        document.getElementById('serverGpu').value = '0';
        document.getElementById('serverTemp').value = '0.7';
        document.getElementById('serverTopP').value = '0.9';
        document.getElementById('serverTopK').value = '40';
        document.getElementById('serverRepeat').value = '1.1';

        document.getElementById('createServerModal').classList.add('active');
    }
}

function closeCreateServerModal() {
    document.getElementById('createServerModal').classList.remove('active');
    editingServerId = null;
}

function closeCreateServerOnOverlay(event) {
    if (event.target.id === 'createServerModal') {
        closeCreateServerModal();
    }
}

async function loadServers() {
    try {
        const result = await apiCall('/servers');
        const servers = result.data;
        const list = document.getElementById('serversList');
        const noServers = document.getElementById('noServersMessage');
        const table = document.getElementById('serversTable');

        if (servers.length === 0) {
            list.innerHTML = '';
            noServers.style.display = 'block';
            table.style.display = 'none';
            return;
        }

        noServers.style.display = 'none';
        table.style.display = 'table';

        // Get running status to update UI
        const statusResult = await apiCall('/server/status');
        const runningServers = statusResult.data.running_servers || [];

        list.innerHTML = servers.map(server => {
            const runningServer = runningServers.find(s => s.id === server.id);
            const isRunning = !!runningServer;
            const isReady = runningServer ? runningServer.is_ready : false;
            const modelName = server.model_path.split(/[/\\]/).pop();

            let statusBadge = '';
            if (isRunning) {
                if (isReady) {
                    statusBadge = '<span class="status-badge status-online">Ready</span>';
                } else {
                    statusBadge = '<span class="status-badge status-warning">Initializing...</span>';
                }
            } else {
                statusBadge = '<span class="status-badge status-stopped">Stopped</span>';
            }

            return `
            <tr>
                <td><strong>${server.name}</strong></td>
                <td><span title="${server.model_path}">${modelName}</span></td>
                <td>${server.port || 8000}</td>
                <td>${statusBadge}</td>
                <td>
                    <div class="model-actions">
                        ${isRunning
                    ? `<button class="btn btn-small btn-danger" onclick="stopServer('${server.id}')">⏹️ Stop</button>`
                    : `<button class="btn btn-small btn-success" onclick="startServer('${server.id}')">▶️ Start</button>`
                }
                        <button class="btn btn-small btn-ghost" onclick="openConsoleModal('${server.id}', '${server.name}')" title="View Console">📟</button>
                        <button class="btn btn-small btn-ghost" onclick="openCreateServerModal(true, '${server.id}')" ${isRunning ? 'disabled' : ''}>✏️</button>
                        <button class="btn btn-small btn-ghost" onclick="deleteServer('${server.id}')" ${isRunning ? 'disabled' : ''}>🗑️</button>
                    </div>
                </td>
            </tr>
        `}).join('');

    } catch (error) {
        console.error('Failed to load servers:', error);
    }
}

async function saveServerConfig() {
    const name = document.getElementById('serverName').value.trim();
    const modelPath = document.getElementById('serverModel').value;
    const port = parseInt(document.getElementById('serverPort').value) || 8000;
    const nCtx = parseInt(document.getElementById('serverCtx').value);
    const nGpu = parseInt(document.getElementById('serverGpu').value);

    // Chat params usually runtime, but we save defaults
    const temp = parseFloat(document.getElementById('serverTemp').value);
    const topP = parseFloat(document.getElementById('serverTopP').value);

    if (!name || !modelPath) {
        showAlert('Name and Model are required', 'error');
        return;
    }

    if (port === 8000) {
        if (!confirm('Warning: Port 8000 is used by this Control Centre. Your model server might conflict or fail to start. Continue anyway?')) {
            return;
        }
    }

    const payload = {
        name,
        model_path: modelPath,
        port,
        n_ctx: nCtx,
        n_gpu_layers: nGpu,
        n_threads: parseInt(document.getElementById('serverThreads').value) || null,
        temperature: parseFloat(document.getElementById('serverTemp').value),
        top_p: parseFloat(document.getElementById('serverTopP').value),
        top_k: parseInt(document.getElementById('serverTopK').value),
        repeat_penalty: parseFloat(document.getElementById('serverRepeat').value)
    };

    try {
        if (editingServerId) {
            await apiCall(`/servers/${editingServerId}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            showAlert('Server updated successfully', 'success');
        } else {
            await apiCall('/servers', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            showAlert('Server created successfully', 'success');
        }

        closeCreateServerModal();
        await loadServers();
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

async function deleteServer(serverId) {
    if (!confirm('Delete this server configuration?')) return;

    try {
        await apiCall(`/servers/${serverId}`, { method: 'DELETE' });
        loadServers();
        showAlert('Server deleted', 'success');
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

async function startServer(serverId) {
    try {
        showAlert('Starting server...', 'info');
        await apiCall(`/servers/${serverId}/start`, { method: 'POST' });

        // Auto-select this server for chat
        currentChatServerId = serverId;

        await loadServers();
        await loadServerStatus();

        showAlert('Server started successfully', 'success');
    } catch (error) {
        showAlert(`Start failed: ${error.message}`, 'error');
        console.error(error);
    }
}

async function stopServer(serverId) {
    if (!serverId && currentChatServerId) serverId = currentChatServerId;

    try {
        const url = serverId ? `/api/server/stop?server_id=${serverId}` : '/api/server/stop';
        await fetch(url, { method: 'POST' }); // Use fetch directly for query param simplicity or update apiCall

        if (currentChatServerId === serverId) {
            currentChatServerId = null;
        }

        await loadServers();
        await loadServerStatus();
        showAlert('Server stopped', 'success');
    } catch (error) {
        showAlert(error.message, 'error');
    }
}

// ===== Server Status & Chat State =====

async function loadServerStatus() {
    try {
        const result = await apiCall('/server/status');
        const status = result.data; // { running_count: n, running_servers: [...] }

        // Determine active chat server
        // If currentChatServerId is set and valid, keep it.
        // Else if servers running, pick first.
        const runningServers = status.running_servers || [];

        if (runningServers.length > 0) {
            isServerRunning = true;
            if (!currentChatServerId || !runningServers.find(s => s.id === currentChatServerId)) {
                currentChatServerId = runningServers[0].id;
            }
        } else {
            isServerRunning = false;
            currentChatServerId = null;
        }

        // Update UI logic
        const sendBtn = document.getElementById('sendBtn');
        const chatInput = document.getElementById('chatInput');

        if (sendBtn) sendBtn.disabled = !isServerRunning;
        if (chatInput) chatInput.disabled = !isServerRunning;

        // Update Dropdown
        updateChatModelStatus(runningServers);

    } catch (error) {
        console.error('Failed to load server status:', error);
    }
}

// ===== Chat Dropdown Functions =====
function toggleChatDropdown() {
    const dropdown = document.getElementById('chatModelDropdown');
    dropdown.classList.toggle('active');
}

// Close dropdown when clicking outside
document.addEventListener('click', (event) => {
    const dropdown = document.getElementById('chatModelDropdown');
    const trigger = document.getElementById('chatModelBtn');
    if (!dropdown || !trigger) return;

    if (!dropdown.contains(event.target) && !trigger.contains(event.target) && dropdown.classList.contains('active')) {
        dropdown.classList.remove('active');
    }
});

function selectChatServer(serverId) {
    currentChatServerId = serverId;
    loadServerStatus(); // Refresh UI to show selected
    toggleChatDropdown();
}

function updateChatModelStatus(runningServers) {
    const btn = document.getElementById('chatModelBtn');
    const list = document.getElementById('chatModelList');

    if (runningServers.length > 0) {
        // Find currently selected config
        const selected = runningServers.find(s => s.id === currentChatServerId) || runningServers[0];

        const serverName = selected.name || "Unknown Server";
        const modelName = (selected.model_path || "").split(/[/\\]/).pop();
        const port = selected.port || 8000;

        // Update Button
        if (selected.is_ready) {
            btn.textContent = `${serverName} (${port})`;
            btn.className = 'status-badge status-online dropdown-trigger';
        } else {
            btn.textContent = `${serverName} (Loading...)`;
            btn.className = 'status-badge status-warning dropdown-trigger';
        }

        // Build List
        list.innerHTML = runningServers.map(s => {
            const sName = s.name;
            const sModel = (s.model_path || "").split(/[/\\]/).pop();
            const sPort = s.port;
            const isActive = s.id === currentChatServerId;
            const isReady = s.is_ready;

            return `
            <div class="dropdown-item ${isActive ? 'active' : ''}" onclick="selectChatServer('${s.id}')">
                <span>${isReady ? '🟢' : '⏳'}</span>
                <div style="display: flex; flex-direction: column;">
                    <span style="font-weight: 600;">${sName} ${isReady ? '' : '(Loading...)'}</span>
                    <span style="font-size: 0.8em; opacity: 0.8;">:${sPort} - ${sModel}</span>
                </div>
            </div>`;
        }).join('') + `

            <div class="dropdown-item" onclick="stopServer('${selected.id}')" style="color: var(--danger); border-top: 1px solid var(--border); margin-top: 0.5rem;">
                <span>⏹️</span>
                Stop Current
            </div>
        `;
    } else {
        // Server is offline
        btn.textContent = 'Model Not Loaded';
        btn.className = 'status-badge status-offline dropdown-trigger';
        list.innerHTML = `<div class="dropdown-item" style="color: var(--text-muted);">No servers running</div>`;
    }
}

// ===== Chat Functions =====
async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message || !currentChatServerId) return;

    // Check if server is ready
    const statusRes = await apiCall('/server/status');
    const runningServers = statusRes.data.running_servers || [];
    const activeServer = runningServers.find(s => s.id === currentChatServerId);

    if (!activeServer || !activeServer.is_ready) {
        showAlert('Model is still initializing. Please wait...', 'warning');
        return;
    }

    // Add User Message
    addChatMessage('user', message);
    input.value = '';

    // Add Assistant Placeholder
    const assistantMsgId = addChatMessage('assistant', '...');
    const assistantMsgContent = document.querySelector(`#${assistantMsgId} .message-content`);
    let fullResponse = '';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                server_id: currentChatServerId,
                message: message,
                stream: true
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.content) {
                            if (fullResponse === '') assistantMsgContent.textContent = ''; // Clear ...
                            fullResponse += data.content;
                            assistantMsgContent.textContent = fullResponse;

                            // Scroll to bottom
                            const container = document.getElementById('chatMessages');
                            container.scrollTop = container.scrollHeight;
                        } else if (data.error) {
                            assistantMsgContent.textContent += ` [Error: ${data.error}]`;
                        }
                    } catch (e) {
                        // ignore parse errors for keep-alive or malformed chunks
                    }
                }
            }
        }
    } catch (error) {
        assistantMsgContent.textContent = `Error: ${error.message}`;
    }
}

function clearChat() {
    chatHistory = [];
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = '<div class="empty-state">Chat cleared. Send a message to continue.</div>';
}

function addChatMessage(role, content) {
    const messagesContainer = document.getElementById('chatMessages');

    // Remove empty state if present
    const emptyState = messagesContainer.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    const msgId = `msg-${Date.now()}`;
    const msgDiv = document.createElement('div');
    msgDiv.className = `message chat-message ${role}`;
    msgDiv.id = msgId;
    msgDiv.innerHTML = `
        <div class="chat-role">${role === 'user' ? 'You' : 'Llama'}</div>
        <div class="message-content">${role === 'assistant' && content === '...' ? '<span class="typing-dots">...</span>' : content}</div>
    `;

    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return msgId;
}

// ===== Settings Functions =====
function openSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.add('active');
    loadSettings();
}

function closeSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.remove('active');
}

function closeSettingsOnOverlay(event) {
    if (event.target.id === 'settingsModal') {
        closeSettings();
    }
}

async function loadSettings() {
    try {
        const result = await apiCall('/settings');
        const settings = result.data;

        document.getElementById('modelsDir').value = settings.models_dir || '';
        const tokenInput = document.getElementById('hfToken');
        if (settings.hf_token) {
            tokenInput.placeholder = "Token saved (enter new one to update)";
        } else {
            tokenInput.placeholder = "hf_...";
        }

    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    const modelsDir = document.getElementById('modelsDir').value.trim();
    const hfToken = document.getElementById('hfToken').value.trim();

    if (!modelsDir) {
        showAlert('Models Directory is required', 'error');
        return;
    }

    try {
        showAlert('Saving settings...', 'info');

        await apiCall('/settings', {
            method: 'POST',
            body: JSON.stringify({
                models_dir: modelsDir,
                hf_token: hfToken || null
            })
        });

        showAlert('Settings saved successfully. Model list refreshed.', 'success');

        await loadModels();
        document.getElementById('hfToken').value = '';
        closeSettings();
        await loadSettings();

    } catch (error) {
        console.error('Failed to save settings:', error);
    }
}

// ===== Event Listeners =====
document.addEventListener('DOMContentLoaded', () => {
    // Load initial data
    loadHardwareInfo();
    loadModels();
    loadServers();

    // Initial Load and Poll status
    async function initialLoadAndPollStatus() {
        await loadServerStatus();
    }
    initialLoadAndPollStatus();
    setInterval(loadServerStatus, 5000); // 5s interval for status

    // Chat input handling
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
});

// Refresh logs
setInterval(() => {
    if (isServerRunning) {
        loadServerLogs();
    }
}, 15000); // Refresh logs every 15 seconds
