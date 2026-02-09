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
            newChatBtn: document.getElementById('new-chat-btn'),
            sidebar: document.querySelector('.sidebar'),
            sidebarToggle: document.getElementById('sidebar-toggle')
        };

        this.ws = null;
        this.isRunning = false;
        this.chatMessages = JSON.parse(localStorage.getItem('delta_last_chat') || '[]');
        this.currentView = 'chat';

        this.init();
    }

    init() {
        this.currentSessionId = null;
        this.connectWebSocket();
        this.bindEvents();

        // Check URL for session ID
        const urlParams = new URLSearchParams(window.location.search);
        const chatId = urlParams.get('chat_id');

        this.loadSettings();
        this.autoResizeInput();

        if (chatId) {
            this.loadSession(parseInt(chatId));
        } else {
            // Check if we should start fresh or load last
            // For now, let's just show history and wait for user action
            this.startNewChat(false); // false = don't create ID yet, just clear UI
        }

        this.loadRecentChats();
        
        // Restore Sidebar State
        const sidebarCollapsed = localStorage.getItem('delta_sidebar_collapsed') === 'true';
        if (sidebarCollapsed) {
            this.elements.sidebar.classList.add('collapsed');
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

        // Sidebar Toggle
        if (this.elements.sidebarToggle && this.elements.sidebar) {
            this.elements.sidebarToggle.addEventListener('click', () => {
                this.elements.sidebar.classList.toggle('collapsed');
            });
        }

        // Logo click expands sidebar when collapsed
        const logo = document.querySelector('.logo');
        if (logo && this.elements.sidebar) {
            logo.addEventListener('click', () => {
                if (this.elements.sidebar.classList.contains('collapsed')) {
                    this.elements.sidebar.classList.remove('collapsed');
                }
            });
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
                // Sidebar Toggle
        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => {
                this.elements.sidebar.classList.toggle('collapsed');
                localStorage.setItem('delta_sidebar_collapsed', this.elements.sidebar.classList.contains('collapsed'));
            });
        }
        
        // Handle Sidebar Logo Click to Expand when collapsed
        const logo = this.elements.sidebar.querySelector('.logo');
        if (logo) {
            logo.addEventListener('click', () => {
                if (this.elements.sidebar.classList.contains('collapsed')) {
                    this.elements.sidebar.classList.remove('collapsed');
                    localStorage.setItem('delta_sidebar_collapsed', 'false');
                }
            });
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
    


    async startNewChat(createNow = true) {
        // Remove isRunning check to allow starting new chat while another runs in background
        // if (this.isRunning) return; 

        this.currentSessionId = null;
        this.chatMessages = [];

        // Reset UI
        this.elements.messages.innerHTML = '';
        this.elements.welcomeScreen.classList.remove('hidden');
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto'; // Reset height

        // Update URL
        const url = new URL(window.location);
        url.searchParams.delete('chat_id');
        window.history.pushState({}, '', url);

        this.switchView('chat');

        // Optionally create the session immediately on backend
        if (createNow) {
            try {
                const res = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: 'New Chat' })
                });
                const session = await res.json();
                this.currentSessionId = session.id;

                // Update URL with new ID
                url.searchParams.set('chat_id', session.id);
                window.history.pushState({}, '', url);

                // Refresh sidebar
                this.loadRecentChats();
            } catch (e) {
                console.error('Failed to create session:', e);
            }
        }
    }

    async loadSession(sessionId) {
        // Remove isRunning check to allow loading sessions while another runs in background
        // if (this.isRunning) return; 

        try {
            const res = await fetch(`/api/sessions/${sessionId}/history`);
            const history = await res.json();

            this.currentSessionId = sessionId;
            this.chatMessages = history;

            // Update UI
            this.elements.messages.innerHTML = '';
            this.elements.welcomeScreen.classList.add('hidden');
            history.forEach(msg => this.renderMessage(msg.type, msg.content, msg.status, msg.timestamp));

            // Update URL
            const url = new URL(window.location);
            url.searchParams.set('chat_id', sessionId);
            window.history.pushState({}, '', url);

            this.switchView('chat');

            // Highlight in sidebar
            document.querySelectorAll('.history-item').forEach(el => {
                el.classList.toggle('active', el.dataset.id == sessionId);
            });

        } catch (e) {
            console.error('Failed to load session:', e);
            this.startNewChat(false);
        }
    }

    async sendMessage() {
        const goal = this.elements.messageInput.value.trim();
        if (!goal || this.isRunning) return;

        // Ensure we have a session ID
        if (!this.currentSessionId) {
            const res = await fetch('/api/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: goal.substring(0, 30) || 'New Chat' })
            });
            const session = await res.json();
            this.currentSessionId = session.id;

            // Update URL
            const url = new URL(window.location);
            url.searchParams.set('chat_id', session.id);
            window.history.pushState({}, '', url);
            this.loadRecentChats(); // Refresh sidebar to show new chat
        }

        this.elements.welcomeScreen.classList.add('hidden');
        this.addMessage('user', goal);

        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto'; // Reset height

        this.setRunning(true, 'Consulting Brain...');
        this.showTyping(true);

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'goal',
                goal: goal,
                session_id: this.currentSessionId
            }));
        }
    }

    handleServerMessage(data) {
        // Filter messages by session_id to ensure we only update the current chat 
        // if we are in one. If data.session_id is missing (older versions), we fall back.
        const isCurrentSession = !data.session_id || data.session_id == this.currentSessionId;

        switch (data.type) {
            case 'thinking':
                if (!isCurrentSession) return; // Ignore background thinking updates
                
                // Check if this is a code preview
                if (data.state === 'code_preview' && data.code) {
                    this.showCodePreview(data.extension_name, data.code, data.details);
                } else {
                    this.updateThinking(data.activity, data.details);
                }
                break;
            case 'tool_output':
                if (isCurrentSession) {
                    // Render tool output immediately as a "Tool" message
                    this.renderMessage('tool', data.output, 'success');
                    this.scrollToBottom();
                }
                break;
            case 'result':
                // If this is for the current session, render it immediately
                if (isCurrentSession) {
                    this.finishThinking(true);
                    this.handleResult(data);
                    this.setRunning(false);
                } else {
                    // It's a background session completing. 
                    // Just refresh sidebar and maybe show a toast.
                    this.loadRecentChats();
                    this.showToast(`Background task completed in another chat.`, 'success');
                }
                break;
            case 'error':
                if (isCurrentSession) {
                    this.finishThinking(false);
                    this.addMessage('agent', data.error || 'Operation failed', 'error');
                    this.setRunning(false);
                } else {
                   this.showToast(`Error in background task: ${data.error}`, 'error');
                }
                break;
        }
    }
    
    showCodePreview(name, code, description) {
        // Find or create current thinking process block
        let currentProcess = this.elements.messages.querySelector('.thinking-process.active');
        if (currentProcess) {
            const logsContainer = currentProcess.querySelector('.thinking-logs');
            if (logsContainer) {
                // Add code preview block
                const codeBlock = document.createElement('div');
                codeBlock.className = 'code-preview-block';
                codeBlock.innerHTML = `
                    <div class="code-preview-header">
                        <span class="code-preview-title">✨ Generated: ${name}</span>
                        <span class="code-preview-desc">${description || ''}</span>
                    </div>
                    <pre class="code-preview-content"><code>${this.escapeHtml(code)}</code></pre>
                `;
                logsContainer.appendChild(codeBlock);
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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

        // Configure marked options
        marked.setOptions({
            breaks: true, // Enable line breaks
            gfm: true,    // Enable GitHub Flavored Markdown
            highlight: function(code, lang) {
                return code; // We handle code blocks separately/later or let it be plain
            }
        });

        // 1. Pre-process specific Delta-style structures
        
        // Handle explicit Code Blocks to ensure they are preserved and styled
        // We use a temporary placeholder to prevent marked from messing up our custom code block HTML
        const codeBlocks = [];
        text = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            const cleanCode = this.escapeHtml(code.trim());
            const displayLang = lang || 'python';
            const placeholder = `__DELTA_CODE_BLOCK_${codeBlocks.length}__`;
            
            codeBlocks.push(`
<div class="code-block-wrapper">
    <div class="code-header">
        <span class="code-lang">${displayLang}</span>
        <button class="code-copy-btn" onclick="window.deltaApp.copyToClipboard(this)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            Copy
        </button>
    </div>
    <pre><code class="language-${displayLang}">${cleanCode}</code></pre>
</div>`);
            return placeholder;
        });

        // 2. Auto-detect and Pretty-print RAW JSON/Dicts
        const jsonPattern = /(?:Return:\s*)?(\{[\s\S]{15,}\}|\[[\s\S]{15,}\])/g;
        text = text.replace(jsonPattern, (match) => {
             // If it matches a placeholder, skip
            if (match.includes('__DELTA_CODE_BLOCK_')) return match;
            
            try {
                let jsonStr = match.trim();
                if (jsonStr.startsWith('Return:')) jsonStr = jsonStr.replace('Return:', '').trim();
                
                 // Python dict fixups
                jsonStr = jsonStr.replace(/'/g, '"')
                                 .replace(/(\W)True(\W)/g, '$1true$2')
                                 .replace(/(\W)False(\W)/g, '$1false$2')
                                 .replace(/(\W)None(\W)/g, '$1null$2');
                                 
                const obj = JSON.parse(jsonStr);
                const prettyJson = JSON.stringify(obj, null, 2);
                const placeholder = `__DELTA_CODE_BLOCK_${codeBlocks.length}__`;
                codeBlocks.push(`
<div class="code-block-wrapper">
    <div class="code-header"><span class="code-lang">json</span></div>
    <pre><code class="language-json">${this.escapeHtml(prettyJson)}</code></pre>
</div>`);
                return placeholder;
            } catch (e) {
                return match;
            }
        });

        // 3. Use marked for the rest (headers, bold, lists, etc.)
        let html = marked.parse(text);

        // 4. Restore code blocks
        codeBlocks.forEach((block, index) => {
            html = html.replace(`__DELTA_CODE_BLOCK_${index}__`, block);
        });
        
        // Remove surrounding <p> tags from placeholders if marked added them
        html = html.replace(/<p>(<div class="code-block-wrapper">[\s\S]*?<\/div>)<\/p>/g, '$1');

        return html;
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
            currentProcess.className = 'thinking-process active expanded';
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
            
            // Auto-collapse on completion to keep UI clean
            currentProcess.classList.remove('expanded');

            // Hide working indicator
            const workingIndicator = currentProcess.querySelector('.working-indicator');
            if (workingIndicator) {
                workingIndicator.classList.add('hidden');
            }

            const spinner = currentProcess.querySelector('.thinking-spinner');
            if (spinner) {
                spinner.className = 'thinking-complete-icon';
                spinner.textContent = success ? '✓' : '✗';
                spinner.style.color = success ? 'var(--accent-primary)' : '#f87171';
                spinner.style.fontWeight = 'bold';
                spinner.style.border = 'none';
                spinner.style.animation = 'none';
            }
        }
    }

    copyToClipboard(btn) {
        const code = btn.parentElement.nextElementSibling.innerText;
        navigator.clipboard.writeText(code);
        
        const originalText = btn.innerHTML;
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg> Copied!`;
        btn.classList.add('copied');
        
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.classList.remove('copied');
        }, 2000);
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

            // Add Copy Button if not exists
            const codeContainer = document.querySelector('.ext-code');
            let actions = codeContainer.querySelector('.code-actions');

            if (!actions) {
                actions = document.createElement('div');
                actions.className = 'code-actions';

                const copyBtn = document.createElement('button');
                copyBtn.className = 'btn-copy';
                copyBtn.textContent = 'Copy Code';
                copyBtn.onclick = () => {
                    navigator.clipboard.writeText(ext.source_code);
                    copyBtn.textContent = 'Copied!';
                    setTimeout(() => copyBtn.textContent = 'Copy Code', 2000);
                };

                actions.appendChild(copyBtn);
                codeContainer.insertBefore(actions, codeContainer.querySelector('pre'));
            } else {
                // Update click handler for new content
                const copyBtn = actions.querySelector('.btn-copy');
                copyBtn.onclick = () => {
                    navigator.clipboard.writeText(ext.source_code);
                    copyBtn.textContent = 'Copied!';
                    setTimeout(() => copyBtn.textContent = 'Copy Code', 2000);
                };
            }

            document.getElementById('extension-modal').classList.remove('hidden');
        } catch (e) {
            console.error('Error fetching extension details:', e);
        }
    }

    async loadRecentChats() {
        const history = this.elements.chatHistory;
        history.innerHTML = '';

        try {
            const res = await fetch('/api/sessions');
            const sessions = await res.json();

            sessions.forEach(session => {
                const item = document.createElement('div');
                item.className = 'history-item';
                item.textContent = session.title || 'Untitled Chat';
                item.dataset.id = session.id;

                if (this.currentSessionId && session.id === this.currentSessionId) {
                    item.classList.add('active');
                }

                item.onclick = () => this.loadSession(session.id);
                history.appendChild(item);
            });

        } catch (e) {
            console.error('Failed to load recent chats:', e);
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
        const btn = document.getElementById('save-settings');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="thinking-spinner" style="border-width: 2px; width: 14px; height: 14px;"></span> Saving...';
        btn.disabled = true;

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
                this.showToast('Configuration saved successfully', 'success');
                setTimeout(() => {
                    document.getElementById('settings-modal').classList.add('hidden');
                }, 500);
            } else {
                this.showToast(result.message || 'Failed to save settings', 'error');
            }
        } catch (e) {
            console.error(e);
            this.showToast('Network error while saving settings', 'error');
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = '';
        if (type === 'success') icon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        else if (type === 'error') icon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
        else icon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';

        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-message">${this.escapeHtml(message)}</div>
            <button class="toast-close">&times;</button>
        `;

        // Close button
        toast.querySelector('.toast-close').onclick = () => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px) scale(0.95)';
            setTimeout(() => toast.remove(), 200);
        };

        container.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('visible');
        });

        // Auto remove
        setTimeout(() => {
            if (toast.parentNode) {
                toast.classList.remove('visible');
                setTimeout(() => toast.remove(), 200);
            }
        }, 5000);
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
    copyToClipboard(btn) {
        const wrapper = btn.closest('.code-block-wrapper');
        const codeElement = wrapper.querySelector('code');
        const text = codeElement.innerText; // Get text content
        
        navigator.clipboard.writeText(text).then(() => {
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!';
            btn.classList.add('copied');
            
            setTimeout(() => {
                btn.innerHTML = originalHtml;
                btn.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy class content: ', err);
            this.showToast('Failed to copy to clipboard', 'error');
        });
    }
}

// Launch
document.addEventListener('DOMContentLoaded', () => {
    window.deltaApp = new DeltaApp();
});
