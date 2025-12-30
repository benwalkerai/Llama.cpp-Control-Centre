// Llama.cpp Control Centre - Main JavaScript

// ===== Global State =====
let chatHistory = [];
let isServerRunning = false;
let wsConnection = null;

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

        // Auto-fill server parameters
        document.getElementById('nCtx').value = rec.n_ctx;
        document.getElementById('nGpuLayers').value = rec.n_gpu_layers;
        document.getElementById('nThreads').value = rec.n_threads;
    } catch (error) {
        console.error('Failed to load recommendations:', error);
    }
}

// ===== Server Functions =====
async function loadServerStatus() {
    try {
        const result = await apiCall('/server/status');
        const status = result.data;

        isServerRunning = status.is_running;

        const statusBadge = document.getElementById('serverStatus');
        const stopBtn = document.getElementById('stopBtn');
        const sendBtn = document.getElementById('sendBtn');

        if (isServerRunning) {
            statusBadge.textContent = 'Running';
            statusBadge.className = 'status-badge status-running';
            stopBtn.disabled = false;
            sendBtn.disabled = false;

            // Display server config
            const config = status.config;
            let html = '<strong>Current Configuration:</strong><br>';
            html += `Model: ${config.model_path || 'N/A'}<br>`;
            html += `Context: ${config.n_ctx || 'N/A'}<br>`;
            html += `GPU Layers: ${config.n_gpu_layers || 0}<br>`;
            html += `Uptime: ${status.uptime ? status.uptime + 's' : 'N/A'}`;

            document.getElementById('serverInfo').innerHTML = html;
        } else {
            statusBadge.textContent = 'Stopped';
            statusBadge.className = 'status-badge status-stopped';
            stopBtn.disabled = true;
            sendBtn.disabled = true;
            document.getElementById('serverInfo').innerHTML = '';
        }

        // Load logs if running
        if (isServerRunning) {
            await loadServerLogs();
        }
    } catch (error) {
        console.error('Failed to load server status:', error);
    }
}

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

// ===== Server Management =====
let serverList = [];
let activeServerId = null;

async function loadServers() {
    try {
        const result = await apiCall('/servers');
        const statusResult = await apiCall('/server/status');

        serverList = result.data;
        activeServerId = statusResult.data.active_server_id;

        renderServerList();

        // Populate model dropdown in Create Modal if empty
        const modelSelect = document.getElementById('serverModel');
        if (modelSelect.options.length <= 1) {
            const modelsResult = await apiCall('/models/list');
            modelsResult.data.forEach(model => {
                const opt = document.createElement('option');
                opt.value = model.path;
                opt.textContent = model.name;
                modelSelect.appendChild(opt);
            });
        }

    } catch (error) {
        showAlert('Error loading servers: ' + error.message, 'error');
    }
}

function renderServerList() {
    const list = document.getElementById('serversList');
    const empty = document.getElementById('noServersMessage');

    if (serverList.length === 0) {
        list.parentElement.style.display = 'none';
        empty.style.display = 'block';
        return;
    }

    list.parentElement.style.display = 'block';
    empty.style.display = 'none';
    list.innerHTML = '';

    serverList.forEach(server => {
        const tr = document.createElement('tr');
        const isRunning = server.id === activeServerId;
        const statusClass = isRunning ? 'status-indicator online' : 'status-indicator offline';
        const statusText = isRunning ? 'Running' : 'Stopped';
        const btnClass = isRunning ? 'btn-danger' : 'btn-success';
        const btnText = isRunning ? '⏹ Stop' : '▶ Start';
        const btnAction = isRunning ? `stopServer()` : `startServer('${server.id}')`;
        const modelName = server.model_path.split(/[\\/]/).pop();

        tr.innerHTML = `
            <td><strong>${server.name}</strong></td>
            <td title="${server.model_path}">${modelName}</td>
            <td>
                <div class="${statusClass}">
                    <div class="status-dot"></div>
                    <span>${statusText}</span>
                </div>
            </td>
            <td>
                <div class="actions-cell">
                    <button class="btn btn-small ${btnClass}" onclick="${btnAction}">
                        ${btnText}
                    </button>
                    <button class="btn btn-small btn-ghost" onclick="deleteServer('${server.id}')" ${isRunning ? 'disabled' : ''}>
                        🗑️
                    </button>
                </div>
            </td>
        `;
        list.appendChild(tr);
    });
}

// ===== Create Server Modal =====
function openCreateServerModal() {
    document.getElementById('createServerModal').classList.add('active');
}

function closeCreateServerModal() {
    document.getElementById('createServerModal').classList.remove('active');
}

function closeCreateServerOnOverlay(event) {
    if (event.target.id === 'createServerModal') {
        closeCreateServerModal();
    }
}

async function createServer() {
    const name = document.getElementById('serverName').value;
    const model = document.getElementById('serverModel').value;

    if (!name || !model) {
        showAlert('Please provide a name and select a model', 'error');
        return;
    }

    const config = {
        name: name,
        model_path: model,
        n_ctx: parseInt(document.getElementById('serverCtx').value),
        n_gpu_layers: parseInt(document.getElementById('serverGpu').value),
        temperature: parseFloat(document.getElementById('serverTemp').value),
        top_p: parseFloat(document.getElementById('serverTopP').value)
    };

    try {
        await apiCall('/servers', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        showAlert('Server created successfully', 'success');
        closeCreateServerModal();
        loadServers();
    } catch (error) {
        showAlert('Error creating server: ' + error.message, 'error');
    }
}

async function deleteServer(id) {
    if (!confirm('Are you sure you want to delete this server?')) return;
    try {
        await apiCall(`/servers/${id}`, { method: 'DELETE' });
        loadServers();
        showAlert('Server deleted', 'success');
    } catch (error) {
        showAlert('Error deleting server: ' + error.message, 'error');
    }
}

async function startServer(id) {
    try {
        await apiCall(`/servers/${id}/start`, { method: 'POST' });
        showAlert('Server started', 'success');

        // Update UI immediately then poll
        activeServerId = id;
        renderServerList();
        // Assuming updateServerStatus is a function that updates the main server status display
        // If not, you might need to call loadServerStatus() here or similar.
        await loadServerStatus();

    } catch (error) {
        showAlert('Error starting server: ' + error.message, 'error');
    }
}

async function stopServer() {
    try {
        await apiCall('/server/stop', { method: 'POST' });
        showAlert('Server stopped', 'success');

        activeServerId = null;
        renderServerList();
        await loadServerStatus();

    } catch (error) {
        showAlert('Error stopping server: ' + error.message, 'error');
    }
}
// ===== Model Functions =====
async function loadModels() {
    try {
        const result = await apiCall('/models/list');
        const models = result.data;

        const modelsList = document.getElementById('modelsList');
        const modelSelect = document.getElementById('selectedModel');

        if (models.length === 0) {
            modelsList.innerHTML = '<div class="empty-state">No models found. Download a model to get started.</div>';
            modelSelect.innerHTML = '<option value="">-- No models available --</option>';
            return;
        }

        // Update models list
        modelsList.innerHTML = models.map(model => `
            <div class="model-item">
                <div class="model-info">
                    <div class="model-name">${model.name}</div>
                    <div class="model-meta">
                        ${model.size_gb} GB • ${model.type} • Modified: ${new Date(model.modified).toLocaleDateString()}
                    </div>
                </div>
                <div class="model-actions">
                    <button class="btn btn-small btn-danger" onclick="deleteModel('${model.name}')">
                        <span class="btn-icon">🗑️</span>
                        Delete
                    </button>
                </div>
            </div>
        `).join('');

        // Update model select dropdown
        modelSelect.innerHTML = '<option value="">-- Select a model --</option>' +
            models.map(model => `<option value="${model.path}">${model.name}</option>`).join('');

        showAlert(`Loaded ${models.length} models`, 'success');
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function downloadModel() {
    const repoId = document.getElementById('repoId').value.trim();
    const filename = document.getElementById('modelFilename').value.trim();

    if (!repoId || !filename) {
        showAlert('Please enter both repo ID and filename', 'error');
        return;
    }

    const progressContainer = document.getElementById('downloadProgress');
    const progressBar = document.getElementById('downloadProgressBar');
    const progressText = document.getElementById('downloadProgressText');

    progressContainer.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = 'Starting download...';

    try {
        showAlert('Downloading model...', 'info');

        const result = await apiCall('/models/download', {
            method: 'POST',
            body: JSON.stringify({ repo_id: repoId, filename })
        });

        progressBar.style.width = '100%';
        progressText.textContent = 'Download complete!';

        showAlert('Model downloaded successfully!', 'success');

        setTimeout(() => {
            progressContainer.style.display = 'none';
        }, 2000);

        await loadModels();
    } catch (error) {
        console.error('Failed to download model:', error);
        progressContainer.style.display = 'none';
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
        // Don't fill password field with masked token, just placeholder if exists
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
                hf_token: hfToken || null // Send null if empty to keep existing/clear? Back end handles this.
            })
        });

        showAlert('Settings saved successfully. Model list refreshed.', 'success');

        // Refresh models list as directory might have changed
        await loadModels();
        // Clear token field for security
        document.getElementById('hfToken').value = '';
        closeSettings();
        await loadSettings(); // Refresh UI state

    } catch (error) {
        console.error('Failed to save settings:', error);
    }
}

// ===== Chat Functions =====
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

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    messageDiv.innerHTML = `
        <div class="chat-role">${role}</div>
        <div class="chat-content">${content.replace(/\n/g, '<br>')}</div>
    `;

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    chatHistory.push({ role, content });
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();

    if (!message) {
        return;
    }

    if (!isServerRunning) {
        showAlert('Please start a server first', 'error');
        return;
    }

    // Add user message
    addChatMessage('user', message);
    input.value = '';

    // Show loading
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-message assistant';
    loadingDiv.id = 'loading-message';
    loadingDiv.innerHTML = '<div class="chat-role">assistant</div><div class="chat-content">Thinking...</div>';
    document.getElementById('chatMessages').appendChild(loadingDiv);

    try {
        const result = await apiCall('/chat', {
            method: 'POST',
            body: JSON.stringify({
                message,
                stream: false,
                max_tokens: 512
            })
        });

        // Remove loading
        loadingDiv.remove();

        // Add assistant response
        addChatMessage('assistant', result.data.message);
    } catch (error) {
        loadingDiv.remove();
        console.error('Failed to send message:', error);
    }
}

// ===== Event Listeners =====
document.addEventListener('DOMContentLoaded', () => {
    // Load initial data
    loadHardwareInfo();
    loadServerStatus();
    loadModels();
    loadServers();

    // Set up periodic updates
    setInterval(loadServerStatus, 10000); // Every 10 seconds

    // Chat input handling
    const chatInput = document.getElementById('chatInput');
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    console.log('🦙 Llama.cpp Control Centre initialized');
});

// ===== Auto-refresh =====
setInterval(() => {
    if (isServerRunning) {
        loadServerLogs();
    }
}, 15000); // Refresh logs every 15 seconds
