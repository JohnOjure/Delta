/**
 * Delta Agent - ChatGPT-style Chat Interface
 */

class DeltaChat {
    constructor() {
        this.elements = {
            chatContainer: document.getElementById('chat-container'),
            messages: document.getElementById('messages'),
            welcomeScreen: document.getElementById('welcome-screen'),
            typingIndicator: document.getElementById('typing-indicator'),
            messageInput: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            newChatBtn: document.getElementById('new-chat'),
            chatHistory: document.getElementById('chat-history'),
            statusDot: document.getElementById('status-dot'),
            statusText: document.getElementById('status-text'),
            extCount: document.getElementById('ext-count')
        };

        this.ws = null;
        this.isRunning = false;
        this.chatMessages = [];

        this.init();
    }

    init() {
        this.connectWebSocket();
        this.bindEvents();
        this.loadStats();
        this.bindSettingsEvents();
        this.autoResizeInput();
    }

    connectWebSocket() {
        const wsUrl = `ws://${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.setStatus('Ready', false);
        };

        this.ws.onclose = () => {
            this.setStatus('Disconnected', false);
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onerror = () => {
            this.setStatus('Connection error', false);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };
    }

    bindEvents() {
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());

        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.elements.newChatBtn.addEventListener('click', () => this.newChat());

        // Voice Input
        const micBtn = document.getElementById('mic-btn');
        if (micBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;

            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.elements.messageInput.value = transcript;
                micBtn.classList.remove('active');
                // Auto-send if confident? Maybe just let user verify first.
            };

            this.recognition.onerror = () => {
                micBtn.classList.remove('active');
            };

            this.recognition.onend = () => {
                micBtn.classList.remove('active');
            };

            micBtn.addEventListener('click', () => {
                if (micBtn.classList.contains('active')) {
                    this.recognition.stop();
                } else {
                    this.recognition.start();
                    micBtn.classList.add('active');
                }
            });
        }

        // Speaker (TTS)
        this.ttsEnabled = false;
        const speakerBtn = document.getElementById('speaker-btn');
        if (speakerBtn) {
            speakerBtn.addEventListener('click', () => {
                this.ttsEnabled = !this.ttsEnabled;
                speakerBtn.style.color = this.ttsEnabled ? 'var(--accent-blue)' : '';
                if (this.ttsEnabled) {
                    this.speak("Voice output enabled.");
                }
            });
        }

        // Note: Vision/Screenshot feature removed - Delta is a system agent,
        // not a browser-based chatbot. Screen analysis should be done via
        // system-level screenshot capabilities, not browser context.
    }

    speak(text) {
        if (!this.ttsEnabled || !text) return;
        // Strip code blocks and markdown for cleaner speech
        const cleanText = text.replace(/```[\s\S]*?```/g, "Code block omitted.")
            .replace(/`.*?`/g, "")
            .replace(/\*/g, "");

        const utterance = new SpeechSynthesisUtterance(cleanText);
        window.speechSynthesis.speak(utterance);
    }

    autoResizeInput() {
        const input = this.elements.messageInput;
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 200) + 'px';
        });
    }

    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || this.isRunning) return;

        // Hide welcome screen
        this.elements.welcomeScreen.style.display = 'none';

        // Add user message
        this.addMessage('user', message);

        // Clear input
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';

        // Show typing indicator
        this.showTyping(true);
        this.setRunning(true, 'Thinking...');

        // Send to server
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'goal', goal: message }));
        } else {
            // Fallback to REST
            try {
                const response = await fetch('/api/goal', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ goal: message })
                });
                const result = await response.json();
                this.handleResult(result);
            } catch (error) {
                this.addMessage('agent', `Error: ${error.message}`, 'error');
            } finally {
                this.showTyping(false);
                this.setRunning(false);
            }
        }
    }

    handleMessage(data) {
        switch (data.type) {
            case 'status':
                this.setStatus(data.status, data.status === 'started');
                if (data.status === 'started') {
                    this.showTyping(true);
                    this.setRunning(true, 'Starting...');
                }
                break;

            case 'thinking':
                // Show thinking status like ChatGPT
                this.updateThinking(data.activity, data.details);
                break;

            case 'activity':
                // Update typing indicator with activity
                if (data.activity) {
                    this.elements.statusText.textContent = data.activity;
                }
                break;

            case 'progress':
                // Could show progress in typing indicator
                break;

            case 'result':
                this.showTyping(false);
                this.handleResult(data);
                this.setRunning(false);
                this.loadStats();
                break;

            case 'error':
                this.showTyping(false);
                this.addMessage('agent', `Error: ${data.error || data.message || 'Unknown error'}`, 'error');
                this.setRunning(false);
                break;
        }
    }

    handleResult(data) {
        const content = data.response || data.message || 'Task completed.';
        const status = data.success ? 'success' : 'error';

        this.addMessage('agent', content, status);

        if (data.success) {
            this.speak(content);
        }

        // Show extensions created
        if (data.extensions_created && data.extensions_created.length > 0) {
            const extMsg = `Created extension: ${data.extensions_created.join(', ')}`;
            this.addMessage('agent', extMsg, 'info');
        }

        // Handle Approval Request (True Agency)
        if (data.requires_approval && data.proposed_alternative) {
            this.createApprovalCard(data.proposed_alternative);
        }
    }

    createApprovalCard(alternative) {
        const card = document.createElement('div');
        card.className = 'approval-card';
        card.innerHTML = `
            <div class="approval-header">
                <span class="approval-icon">⚡</span>
                <span class="approval-title">Alternative Plan Proposed</span>
            </div>
            <div class="approval-body">
                <p>The initial approach failed. I recommend:</p>
                <div class="approval-plan">${alternative.alternative_plan}</div>
            </div>
            <div class="approval-actions">
                <button class="approval-btn cancel-btn">Cancel</button>
                <button class="approval-btn approve-btn">Authorize & Execute</button>
            </div>
        `;

        // Bind events
        const cancelBtn = card.querySelector('.cancel-btn');
        const approveBtn = card.querySelector('.approve-btn');

        cancelBtn.onclick = () => {
            card.remove();
            this.addMessage('user', 'Alternative plan rejected.');
        };

        approveBtn.onclick = () => {
            // Disable buttons
            cancelBtn.disabled = true;
            approveBtn.disabled = true;
            approveBtn.textContent = 'Authorizing...';

            this.handleApproval(true, alternative);
            card.remove();
        };

        this.elements.messages.appendChild(card);
        this.scrollToBottom();
    }

    async handleApproval(approved, alternative) {
        try {
            await fetch('/api/approval', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    approved: approved,
                    alternative_plan: alternative.alternative_plan,
                    original_goal: alternative.original_goal
                })
            });

            if (approved) {
                this.addMessage('user', 'Proceed with the alternative plan.');
                this.showTyping(true);
                this.setRunning(true, 'Executing alternative...');
            }
        } catch (e) {
            console.error('Failed to send approval:', e);
            this.addMessage('agent', 'Failed to communicate approval.', 'error');
        }
    }

    addMessage(type, content, status = '') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = type === 'user' ? 'Y' : 'Δ';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${status}`;
        bubble.innerHTML = this.formatMessage(content);

        const timestamp = document.createElement('div');
        timestamp.className = 'message-status';
        timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        contentDiv.appendChild(bubble);
        contentDiv.appendChild(timestamp);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);

        this.elements.messages.appendChild(messageDiv);
        this.scrollToBottom();

        // Save to history
        this.chatMessages.push({ type, content, timestamp: new Date() });
    }

    formatMessage(content) {
        // Convert markdown-like formatting
        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }

    showTyping(show) {
        if (show) {
            this.elements.typingIndicator.classList.remove('hidden');
            this.scrollToBottom();
        } else {
            this.elements.typingIndicator.classList.add('hidden');
            // Clear thinking content
            const thinkingContent = this.elements.typingIndicator.querySelector('.thinking-content');
            if (thinkingContent) {
                thinkingContent.remove();
            }
        }
    }

    updateThinking(activity, details) {
        // Show the thinking indicator with current activity
        this.showTyping(true);
        this.elements.statusText.textContent = activity || 'Thinking...';

        // Update or create thinking content element
        let thinkingContent = this.elements.typingIndicator.querySelector('.thinking-content');
        if (!thinkingContent) {
            thinkingContent = document.createElement('div');
            thinkingContent.className = 'thinking-content';

            // Allow toggle via header click
            thinkingContent.onclick = (e) => {
                // Only toggle if clicking header or self, not details text selection
                if (e.target.closest('.thinking-header') || e.target === thinkingContent) {
                    thinkingContent.classList.toggle('expanded');
                }
            };

            this.elements.typingIndicator.appendChild(thinkingContent);
        }

        // Update with activity and details
        thinkingContent.innerHTML = `
            <div class="thinking-header">
                <div class="thinking-activity">${activity || 'Processing...'}</div>
                <div class="thinking-toggle">
                    <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M1 1L5 5L9 1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            </div>
            ${details ? `<div class="thinking-details">${details}</div>` : ''}
        `;

        this.scrollToBottom();
    }

    scrollToBottom() {
        this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
    }

    setRunning(running, activity = '') {
        this.isRunning = running;
        this.elements.sendBtn.disabled = running;

        if (running) {
            this.elements.statusDot.classList.add('running');
            this.elements.statusText.textContent = activity || 'Running...';
        } else {
            this.elements.statusDot.classList.remove('running');
            this.elements.statusText.textContent = 'Ready';
        }
    }

    setStatus(status, isRunning) {
        this.elements.statusText.textContent = status;
        if (isRunning) {
            this.elements.statusDot.classList.add('running');
        } else {
            this.elements.statusDot.classList.remove('running');
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            this.elements.extCount.textContent = (stats.extensions || 0) + ' Extensions';
        } catch (e) {
            console.error('Failed to load stats:', e);
        }
    }

    bindSettingsEvents() {
        const modal = document.getElementById('settings-modal');
        const settingsBtn = document.getElementById('settings-btn');
        const closeBtn = document.getElementById('close-settings');
        const saveBtn = document.getElementById('save-settings');

        // Open
        if (settingsBtn) {
            settingsBtn.onclick = () => {
                this.loadSettings();
                modal.classList.remove('hidden');
            };
        }

        // Close
        if (closeBtn) {
            closeBtn.onclick = () => modal.classList.add('hidden');
        }

        // Close on outside click
        window.onclick = (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        };

        // Save
        if (saveBtn) {
            saveBtn.onclick = () => this.saveSettings();
        }
    }

    async loadSettings() {
        try {
            const res = await fetch('/api/config');
            const config = await res.json();

            document.getElementById('setting-name').value = config.user_name || '';
            document.getElementById('setting-model').value = config.model_name || 'gemini-3-pro-preview';
            document.getElementById('setting-api-key').value = config.api_key || '';
            document.getElementById('setting-voice').checked = config.voice_enabled || false;
            document.getElementById('setting-limit').value = config.usage_limit || 100;
        } catch (e) {
            console.error('Failed to load settings:', e);
            alert('Failed to load settings.');
        }
    }

    async saveSettings() {
        const btn = document.getElementById('save-settings');
        const originalText = btn.textContent;
        btn.textContent = 'Saving...';
        btn.disabled = true;

        const config = {
            user_name: document.getElementById('setting-name').value,
            model_name: document.getElementById('setting-model').value,
            api_key: document.getElementById('setting-api-key').value,
            voice_enabled: document.getElementById('setting-voice').checked,
            usage_limit: document.getElementById('setting-limit').value
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
                // Optional: alert('Settings saved!');
            } else {
                alert('Error saving settings: ' + result.message);
            }
        } catch (e) {
            console.error('Failed to save settings:', e);
            alert('Failed to save settings.');
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

    newChat() {
        this.elements.messages.innerHTML = '';
        this.elements.welcomeScreen.style.display = 'block';
        this.chatMessages = [];
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.deltaChat = new DeltaChat();
});
