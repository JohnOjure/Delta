/**
 * Delta Agent - Premium Chat & Extension Management Interface
 */

class DeltaApp {
    constructor() {
        this.elements = {
            chatContainer: document.getElementById('chat-container'),
            messages: document.getElementById('messages'),
            welcomeScreen: document.getElementById('welcome-screen'),
            typingIndicator: document.getElementById('typing-indicator'),
            messageInput: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            chatHistory: document.getElementById('chat-history'),
            statusDot: document.getElementById('status-dot'),
            statusText: document.getElementById('status-text'),
            extensionsGrid: document.getElementById('extensions-grid'),
            views: document.querySelectorAll('.view'),
            navItems: document.querySelectorAll('.nav-item'),
            newChatBtn: document.getElementById('new-chat-btn')
        };

        this.ws = null;
        this.isRunning = false;
        this.chatMessages = JSON.parse(localStorage.getItem('delta_last_chat') || '[]');
        this.currentView = 'chat';

        this.init();
    }

    init() {
        this.connectWebSocket();
        this.bindEvents();
        this.loadRecentChats();
        this.loadSettings();
        this.autoResizeInput();

        // Restore previous chat if any
        if (this.chatMessages.length > 0) {
            this.elements.welcomeScreen.classList.add('hidden');
            this.chatMessages.forEach(msg => this.renderMessage(msg.type, msg.content, msg.status, msg.timestamp));
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => this.setStatus('Ready', false);
        this.ws.onclose = () => {
            this.setStatus('Disconnected', false);
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleServerMessage(data);
            } catch (e) {
                console.error('WS parse error:', e);
            }
        };
    }

    bindEvents() {
        // Navigation
        this.elements.navItems.forEach(item => {
            if (!item.id || item.id !== 'new-chat-btn') {
                item.addEventListener('click', () => this.switchView(item.dataset.view));
            }
        });

        // New Chat
        if (this.elements.newChatBtn) {
            this.elements.newChatBtn.addEventListener('click', () => this.startNewChat());
        }

        // Chat
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Settings Modal
        const settingsBtn = document.getElementById('settings-btn');
        const settingsModal = document.getElementById('settings-modal');
        settingsBtn.onclick = () => settingsModal.classList.remove('hidden');
        document.getElementById('close-settings').onclick = () => settingsModal.classList.add('hidden');
        document.getElementById('save-settings').onclick = () => this.saveSettings();

        // Extension Modal
        document.getElementById('close-extension').onclick = () => {
            document.getElementById('extension-modal').classList.add('hidden');
        };

        // Voice Input
        const micBtn = document.getElementById('mic-btn');
        if (micBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();

            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.elements.messageInput.value = transcript;
                this.elements.messageInput.dispatchEvent(new Event('input'));
                micBtn.classList.remove('active');
            };
            this.recognition.onend = () => micBtn.classList.remove('active');

            micBtn.onclick = () => {
                if (micBtn.classList.contains('active')) {
                    this.recognition.stop();
                } else {
                    this.recognition.start();
                    micBtn.classList.add('active');
                }
            };
        }
    }

    switchView(viewName) {
        this.currentView = viewName;

        // Update Nav
        this.elements.navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.view === viewName);
        });

        // Update Views
        this.elements.views.forEach(view => {
            view.classList.toggle('active', view.id === `view-${viewName}`);
        });

        if (viewName === 'extensions') {
            this.loadExtensions();
        }
    }

    startNewChat() {
        if (this.isRunning) return; // Don't interrupt active mission

        // Clear state
        this.chatMessages = [];
        this.saveChatHistory();

        // Reset UI
        this.elements.messages.innerHTML = '';
        this.elements.welcomeScreen.classList.remove('hidden');
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';

        // Switch to chat view if not already there
        this.switchView('chat');
    }

    async sendMessage() {
        const goal = this.elements.messageInput.value.trim();
        if (!goal || this.isRunning) return;

        this.elements.welcomeScreen.classList.add('hidden');
        this.addMessage('user', goal);

        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';

        this.setRunning(true, 'Consulting Brain...');
        this.showTyping(true);

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'goal', goal: goal }));
        }
    }

    handleServerMessage(data) {
        switch (data.type) {
            case 'thinking':
                this.updateThinking(data.activity, data.details);
                break;
            case 'result':
                this.finishThinking(true);
                this.handleResult(data);
                this.setRunning(false);
                break;
            case 'error':
                this.finishThinking(false);
                this.addMessage('agent', data.error || 'Operation failed', 'error');
                this.setRunning(false);
                break;
        }
    }

    handleResult(data) {
        const content = data.response || data.message || 'Mission accomplished.';
        this.addMessage('agent', content, data.success ? 'success' : 'error');

        if (data.extensions_created && data.extensions_created.length > 0) {
            this.addMessage('agent', `Added ${data.extensions_created.length} new capabilities to my system: ${data.extensions_created.join(', ')}`, 'info');
        }
    }

    addMessage(type, content, status = '') {
        const timestamp = new Date().toISOString();
        this.chatMessages.push({ type, content, status, timestamp });
        this.saveChatHistory();
        this.renderMessage(type, content, status, timestamp);
    }

    renderMessage(type, content, status, timestamp) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${type}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = type === 'user' ? 'U' : 'Δ';

        const bubbleWrapper = document.createElement('div');
        bubbleWrapper.className = 'message-bubble-wrapper';

        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${status}`;
        bubble.innerHTML = this.formatMarkdown(content);

        const meta = document.createElement('div');
        meta.className = 'message-status';
        meta.textContent = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        bubbleWrapper.appendChild(bubble);
        bubbleWrapper.appendChild(meta);
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bubbleWrapper);

        this.elements.messages.appendChild(msgDiv);
        this.scrollToBottom();
    }

    formatMarkdown(text) {
        if (!text) return '';

        // Code Blocks
        text = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<div class="code-block-wrapper">
                <div class="code-header"><span>${lang || 'python'}</span></div>
                <pre><code class="language-${lang || 'python'}">${this.escapeHtml(code.trim())}</code></pre>
            </div>`;
        });

        // Inline Code
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Line Breaks
        text = text.replace(/\n/g, '<br>');

        return text;
    }

    escapeHtml(str) {
        return str.replace(/[&<>"']/g, m => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[m]));
    }

    updateThinking(activity, details) {
        this.showTyping(true);
        const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

        // Find or create current thinking process block
        let currentProcess = this.elements.messages.querySelector('.thinking-process.active');
        
        if (!currentProcess) {
            // Create new thinking block
            currentProcess = document.createElement('div');
            currentProcess.className = 'thinking-process active expanded'; // Default expanded
            currentProcess.innerHTML = `
                <div class="thinking-header">
                    <div class="thinking-title">
                        <div class="thinking-spinner"></div>
                        <span class="process-status">${activity || 'Processing...'}</span>
                    </div>
                    <span class="thinking-toggle">▼</span>
                </div>
                <div class="thinking-logs">
                    <div class="log-list"></div>
                </div>
            `;
            
            // Toggle Logic
            currentProcess.querySelector('.thinking-header').onclick = () => {
                currentProcess.classList.toggle('expanded');
            };

            this.elements.messages.appendChild(currentProcess);
        }

        // Update Status Title
        if (activity) {
            currentProcess.querySelector('.process-status').textContent = activity;
        }

        // Append Log Details
        if (details) {
            const logList = currentProcess.querySelector('.log-list');
            const logItem = document.createElement('div');
            
            // Detect type based on keywords
            let type = 'default';
            if (details.toLowerCase().includes('error') || details.toLowerCase().includes('fail')) type = 'error';
            else if (details.toLowerCase().includes('success') || details.toLowerCase().includes('completed')) type = 'success';
            else if (details.toLowerCase().includes('creating') || details.toLowerCase().includes('building')) type = 'info';
            else if (details.toLowerCase().includes('warning')) type = 'warning';

            logItem.className = `log-item ${type}`;
            logItem.innerHTML = `
                <span class="timestamp">[${timestamp}]</span>
                <span class="content">${this.escapeHtml(details)}</span>
            `;
            
            logList.appendChild(logItem);
            
            // Auto-scroll logs
            const logsContainer = currentProcess.querySelector('.thinking-logs');
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }

        this.scrollToBottom();
    }

    showTyping(show) {
        // We now use inline thinking processes in the message list, 
        // so we just hide the old fixed typing indicator
        this.elements.typingIndicator.classList.add('hidden');
    }

    finishThinking(success = true) {
        const currentProcess = this.elements.messages.querySelector('.thinking-process.active');
        if (currentProcess) {
            currentProcess.classList.remove('active');
            const spinner = currentProcess.querySelector('.thinking-spinner');
            if (spinner) {
                spinner.style.border = 'none';
                spinner.style.animation = 'none';
                spinner.textContent = success ? '✓' : '✗';
                spinner.style.color = success ? 'var(--accent-primary)' : '#f87171';
                spinner.style.display = 'flex';
                spinner.style.alignItems = 'center';
                spinner.style.justifyContent = 'center';
                spinner.style.fontWeight = 'bold';
            }
            // Auto collapse on finish after a delay? Maybe keep expanded for review.
            // currentProcess.classList.remove('expanded'); 
        }
    }

    async loadExtensions() {
        try {
            const res = await fetch('/api/extensions');
            const exts = await res.json();
            this.renderExtensions(exts);
        } catch (e) {
            console.error('Failed to load extensions:', e);
        }
    }

    renderExtensions(exts) {
        this.elements.extensionsGrid.innerHTML = '';
        exts.forEach(ext => {
            const card = document.createElement('div');
            card.className = 'extension-card';
            card.innerHTML = `
                <h3 class="ext-name">${ext.name}</h3>
                <p class="ext-desc">${ext.description || 'No description available.'}</p>
                <div class="ext-meta">
                    <span>v${ext.version}</span>
                    <span>${ext.executions} runs</span>
                </div>
            `;
            card.onclick = () => this.showExtensionDetails(ext.name);
            this.elements.extensionsGrid.appendChild(card);
        });
    }

    async showExtensionDetails(name) {
        try {
            const res = await fetch(`/api/extensions/${name}`);
            const ext = await res.json();

            document.getElementById('ext-detail-title').textContent = ext.name;
            document.getElementById('ext-detail-desc').textContent = ext.description;
            document.getElementById('ext-detail-stats').textContent = `${ext.executions} successful executions since ${new Date(ext.created_at).toLocaleDateString()}`;

            const capsList = document.getElementById('ext-detail-caps');
            capsList.innerHTML = '';
            ext.capabilities.forEach(cap => {
                const tag = document.createElement('span');
                tag.className = 'tag';
                tag.textContent = cap;
                capsList.appendChild(tag);
            });

            document.getElementById('ext-detail-code').textContent = ext.source_code;

            document.getElementById('extension-modal').classList.remove('hidden');
        } catch (e) {
            console.error('Error fetching extension details:', e);
        }
    }

    loadRecentChats() {
        const history = this.elements.chatHistory;
        history.innerHTML = '';

        // This is a placeholder for actual multi-chat history
        // For now, we just show "Current Mission" if there are messages
        if (this.chatMessages.length > 0) {
            const item = document.createElement('div');
            item.className = 'history-item';
            const firstMsg = this.chatMessages.find(m => m.type === 'user');
            item.textContent = firstMsg ? firstMsg.content : 'New Mission';
            history.appendChild(item);
        }
    }

    saveChatHistory() {
        localStorage.setItem('delta_last_chat', JSON.stringify(this.chatMessages));
    }

    setRunning(running, activity = '') {
        this.isRunning = running;
        this.elements.sendBtn.disabled = running;
        this.elements.statusDot.classList.toggle('running', running);
        this.elements.statusText.textContent = running ? activity : 'Ready';
    }

    setStatus(status, isRunning) {
        this.elements.statusText.textContent = status;
        this.elements.statusDot.classList.toggle('running', isRunning);
    }

    async loadSettings() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            document.getElementById('setting-name').value = data.user_name || 'Fluxx';
            document.getElementById('setting-model').value = data.model_name || 'gemini-3-pro-preview';
            document.getElementById('setting-api-key').value = data.api_key || '';
            document.getElementById('setting-voice').checked = data.voice_enabled || false;
        } catch (e) {
            console.error('Settings load error:', e);
        }
    }

    async saveSettings() {
        const config = {
            user_name: document.getElementById('setting-name').value,
            model_name: document.getElementById('setting-model').value,
            api_key: document.getElementById('setting-api-key').value,
            voice_enabled: document.getElementById('setting-voice').checked
        };

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const result = await res.json();
            if (result.success) {
                document.getElementById('settings-modal').classList.add('hidden');
            }
        } catch (e) {
            alert('Failed to save settings');
        }
    }

    autoResizeInput() {
        const input = this.elements.messageInput;
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 160) + 'px';
        });
    }

    scrollToBottom() {
        this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
    }
}

// Launch
document.addEventListener('DOMContentLoaded', () => {
    window.deltaApp = new DeltaApp();
});
