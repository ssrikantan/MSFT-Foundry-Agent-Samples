/**
 * Foundry Agent Chat - Frontend Application
 * 
 * Handles:
 * - Streaming SSE responses from the backend
 * - Tool call display with expandable cards (ChatGPT style)
 * - Conversation history management
 * - Responsive UI interactions
 */

// =============================================================================
// State
// =============================================================================

const state = {
    messages: [],      // Conversation history
    isStreaming: false, // Currently receiving response
    currentTools: {},  // Active tool cards by ID
    
    // Typewriter effect state
    textBuffer: '',           // Buffer of text waiting to be displayed
    typewriterActive: false,  // Is typewriter animation running
    typewriterSpeed: 12,      // Milliseconds per character (lower = faster)
    currentMessageElements: null, // Current message being typed
};

// =============================================================================
// DOM Elements
// =============================================================================

const elements = {
    messages: document.getElementById('messages'),
    userInput: document.getElementById('userInput'),
    sendBtn: document.getElementById('sendBtn'),
    welcome: document.getElementById('welcome'),
};

// =============================================================================
// SVG Icons
// =============================================================================

const icons = {
    user: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
    </svg>`,
    
    assistant: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
        <path d="M2 17l10 5 10-5"/>
        <path d="M2 12l10 5 10-5"/>
    </svg>`,
    
    tool: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
    </svg>`,
    
    spinner: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>`,
    
    check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12"/>
    </svg>`,
    
    chevron: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="6 9 12 15 18 9"/>
    </svg>`,
    
    search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/>
        <path d="m21 21-4.35-4.35"/>
    </svg>`,
    
    citation: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
    </svg>`,
};

// =============================================================================
// Message Rendering
// =============================================================================

/**
 * Add a user message to the chat
 */
function addUserMessage(content) {
    hideWelcome();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="avatar user">${icons.user}</div>
            <span class="sender-name">You</span>
        </div>
        <div class="message-bubble">
            <p>${escapeHtml(content)}</p>
        </div>
    `;
    
    elements.messages.appendChild(messageDiv);
    scrollToBottom();
    
    state.messages.push({ role: 'user', content });
}

/**
 * Create an assistant message container for streaming
 */
function createAssistantMessage() {
    hideWelcome();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';
    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="avatar assistant">${icons.assistant}</div>
            <span class="sender-name">Foundry Agent</span>
        </div>
        <div class="message-bubble">
            <div class="tool-cards"></div>
            <div class="text-content"></div>
            <div class="citations-container"></div>
        </div>
    `;
    
    elements.messages.appendChild(messageDiv);
    scrollToBottom();
    
    return {
        container: messageDiv,
        toolCards: messageDiv.querySelector('.tool-cards'),
        textContent: messageDiv.querySelector('.text-content'),
        citations: messageDiv.querySelector('.citations-container'),
    };
}

/**
 * Add streaming text to the current message with typewriter effect
 */
function appendText(messageElements, text) {
    // Add text to buffer
    state.textBuffer += text;
    state.currentMessageElements = messageElements;
    
    // Start typewriter if not already running
    if (!state.typewriterActive) {
        state.typewriterActive = true;
        runTypewriter();
    }
}

/**
 * Typewriter effect - displays buffered text character by character
 */
function runTypewriter() {
    if (!state.currentMessageElements) {
        state.typewriterActive = false;
        return;
    }
    
    const messageElements = state.currentMessageElements;
    
    // Get or create the text span
    let textSpan = messageElements.textContent.querySelector('.streaming-text');
    if (!textSpan) {
        textSpan = document.createElement('span');
        textSpan.className = 'streaming-text';
        messageElements.textContent.appendChild(textSpan);
    }
    
    // Remove cursor if exists
    const cursor = messageElements.textContent.querySelector('.streaming-cursor');
    if (cursor) cursor.remove();
    
    // Determine how many characters to show at once
    // Show more at once for faster perceived speed, especially for word boundaries
    let charsToShow = 1;
    
    if (state.textBuffer.length > 0) {
        const nextChar = state.textBuffer[0];
        
        // Show whole words or punctuation sequences at once for smoother reading
        if (nextChar === ' ' || nextChar === '\n') {
            charsToShow = 1;
        } else {
            // Find next word boundary (space, newline, or punctuation)
            const match = state.textBuffer.match(/^[^\s.,!?;:\n]+/);
            if (match && match[0].length <= 8) {
                // Show short words (up to 8 chars) all at once
                charsToShow = match[0].length;
            } else {
                // For longer content, show 2-4 chars at a time
                charsToShow = Math.min(3, state.textBuffer.length);
            }
        }
    }
    
    if (state.textBuffer.length > 0) {
        // Extract characters to display
        const chars = state.textBuffer.substring(0, charsToShow);
        state.textBuffer = state.textBuffer.substring(charsToShow);
        
        // Add to display
        textSpan.innerHTML += escapeHtml(chars);
        
        // Add cursor back
        const cursorSpan = document.createElement('span');
        cursorSpan.className = 'streaming-cursor';
        messageElements.textContent.appendChild(cursorSpan);
        
        // Scroll to keep text visible
        scrollToBottom();
        
        // Calculate delay - faster for spaces/newlines, normal for text
        let delay = state.typewriterSpeed;
        if (chars.includes('\n')) {
            delay = state.typewriterSpeed * 3; // Pause at line breaks
        } else if (chars.includes('.') || chars.includes('!') || chars.includes('?')) {
            delay = state.typewriterSpeed * 2; // Pause at sentence ends
        }
        
        // Continue typewriter
        setTimeout(runTypewriter, delay);
    } else {
        // Buffer empty - add cursor and wait for more text
        const cursorSpan = document.createElement('span');
        cursorSpan.className = 'streaming-cursor';
        messageElements.textContent.appendChild(cursorSpan);
        
        // Check again shortly in case more text arrives
        if (state.isStreaming) {
            setTimeout(runTypewriter, 50);
        } else {
            state.typewriterActive = false;
        }
    }
}

/**
 * Wait for typewriter buffer to empty
 */
async function waitForTypewriter() {
    return new Promise(resolve => {
        const check = () => {
            if (state.textBuffer.length === 0 && !state.typewriterActive) {
                resolve();
            } else {
                setTimeout(check, 50);
            }
        };
        check();
    });
}

/**
 * Finalize the streaming message (remove cursor, format markdown)
 */
async function finalizeMessage(messageElements, fullText) {
    // Wait for typewriter to finish displaying all buffered text
    await waitForTypewriter();
    
    // Remove cursor
    const cursor = messageElements.textContent.querySelector('.streaming-cursor');
    if (cursor) cursor.remove();
    
    // Format the text with basic markdown
    const formattedText = formatMarkdown(fullText);
    messageElements.textContent.innerHTML = formattedText;
    
    // Store in history
    state.messages.push({ role: 'assistant', content: fullText });
    
    // Clear state
    state.currentMessageElements = null;
    state.textBuffer = '';
}

// =============================================================================
// Tool Cards
// =============================================================================

/**
 * Add a tool card (in progress state)
 */
function addToolCard(messageElements, toolId, toolName) {
    const card = document.createElement('div');
    card.className = 'tool-card';
    card.id = `tool-${toolId}`;
    card.innerHTML = `
        <div class="tool-card-header" onclick="toggleToolCard('${toolId}')">
            <div class="tool-icon spinning">${icons.spinner}</div>
            <div class="tool-info">
                <div class="tool-name">${formatToolName(toolName)}</div>
                <div class="tool-status">Running...</div>
            </div>
            <div class="tool-expand-icon">${icons.chevron}</div>
        </div>
        <div class="tool-card-body">
            <div class="tool-arguments">
                <div class="tool-arguments-label">Arguments</div>
                <pre>Loading...</pre>
            </div>
        </div>
    `;
    
    messageElements.toolCards.appendChild(card);
    state.currentTools[toolId] = { name: toolName, element: card };
    scrollToBottom();
}

/**
 * Add a discovery card (searching knowledge base)
 */
function addDiscoveryCard(messageElements, source) {
    const existingDiscovery = messageElements.toolCards.querySelector('.discovery-card');
    if (existingDiscovery) return; // Only one discovery card
    
    const card = document.createElement('div');
    card.className = 'tool-card discovery discovery-card';
    card.innerHTML = `
        <div class="tool-card-header">
            <div class="tool-icon spinning">${icons.search}</div>
            <div class="tool-info">
                <div class="tool-name">Searching knowledge base</div>
                <div class="tool-status">Discovering available tools...</div>
            </div>
        </div>
    `;
    
    messageElements.toolCards.appendChild(card);
    scrollToBottom();
}

/**
 * Complete the discovery phase
 */
function completeDiscovery(messageElements) {
    const card = messageElements.toolCards.querySelector('.discovery-card');
    if (card) {
        const icon = card.querySelector('.tool-icon');
        const status = card.querySelector('.tool-status');
        
        icon.classList.remove('spinning');
        icon.innerHTML = icons.check;
        status.textContent = 'Ready';
        status.classList.add('completed');
        
        // Fade out after a moment
        setTimeout(() => {
            card.style.opacity = '0.6';
        }, 500);
    }
}

/**
 * Update tool card with arguments
 */
function updateToolArguments(toolId, args) {
    const tool = state.currentTools[toolId];
    if (!tool) return;
    
    const argsEl = tool.element.querySelector('.tool-arguments pre');
    if (argsEl) {
        const formatted = typeof args === 'object' 
            ? JSON.stringify(args, null, 2) 
            : String(args);
        argsEl.textContent = formatted;
    }
}

/**
 * Complete a tool card
 */
function completeToolCard(toolId, toolName) {
    const tool = state.currentTools[toolId];
    if (!tool) return;
    
    const icon = tool.element.querySelector('.tool-icon');
    const status = tool.element.querySelector('.tool-status');
    
    icon.classList.remove('spinning');
    icon.innerHTML = icons.check;
    status.textContent = 'Completed';
    status.classList.add('completed');
    
    delete state.currentTools[toolId];
}

/**
 * Toggle tool card expansion
 */
function toggleToolCard(toolId) {
    const card = document.getElementById(`tool-${toolId}`);
    if (card) {
        card.classList.toggle('expanded');
    }
}

// Make function globally available
window.toggleToolCard = toggleToolCard;

// =============================================================================
// Citations
// =============================================================================

/**
 * Add citations to the message
 */
function addCitations(messageElements, citations) {
    if (!citations || citations.length === 0) return;
    
    let citationsHtml = `
        <div class="citations">
            <div class="citations-header">
                ${icons.citation}
                <span>Sources</span>
            </div>
            <ul class="citation-list">
    `;
    
    citations.forEach((citation, index) => {
        if (citation.type === 'url') {
            citationsHtml += `
                <li class="citation-item">
                    <a href="${escapeHtml(citation.url)}" target="_blank" rel="noopener">
                        ${escapeHtml(citation.url)}
                    </a>
                </li>
            `;
        } else if (citation.type === 'file') {
            citationsHtml += `
                <li class="citation-item">📄 ${escapeHtml(citation.file_id)}</li>
            `;
        }
    });
    
    citationsHtml += '</ul></div>';
    messageElements.citations.innerHTML = citationsHtml;
}

// =============================================================================
// SSE Streaming
// =============================================================================

/**
 * Send message and stream the response
 */
async function sendMessage() {
    const input = elements.userInput.value.trim();
    if (!input || state.isStreaming) return;
    
    // Clear input and disable
    elements.userInput.value = '';
    autoResize(elements.userInput);
    setStreaming(true);
    
    // Add user message
    addUserMessage(input);
    
    // Create assistant message container
    const messageElements = createAssistantMessage();
    let fullText = '';
    
    try {
        // Prepare messages for API
        const messages = state.messages.map(m => ({
            role: m.role,
            content: m.content
        }));
        
        // Start SSE connection
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages }),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // Process complete SSE messages
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleSSEEvent(data, messageElements, (text) => {
                            fullText += text;
                        });
                    } catch (e) {
                        console.warn('Failed to parse SSE data:', line);
                    }
                }
            }
        }
        
        // Mark streaming as done (but typewriter may still be running)
        state.isStreaming = false;
        
        // Finalize message (wait for typewriter to complete)
        await finalizeMessage(messageElements, fullText);
        
    } catch (error) {
        console.error('Chat error:', error);
        state.isStreaming = false;
        state.textBuffer = '';
        state.typewriterActive = false;
        messageElements.textContent.innerHTML = `
            <p style="color: var(--accent-warning);">
                ⚠️ Error: ${escapeHtml(error.message)}
            </p>
        `;
    } finally {
        // Re-enable input
        elements.sendBtn.disabled = false;
        elements.userInput.disabled = false;
        elements.userInput.focus();
    }
}

/**
 * Handle individual SSE events
 */
function handleSSEEvent(data, messageElements, onText) {
    switch (data.type) {
        case 'text_delta':
            appendText(messageElements, data.content);
            onText(data.content);
            break;
            
        case 'tool_start':
            addToolCard(messageElements, data.id, data.name);
            break;
            
        case 'tool_args':
            updateToolArguments(data.id, data.arguments);
            break;
            
        case 'tool_done':
            completeToolCard(data.id, data.name);
            break;
            
        case 'tool_discovery':
            addDiscoveryCard(messageElements, data.source);
            break;
            
        case 'tool_discovery_done':
            completeDiscovery(messageElements);
            break;
            
        case 'citations':
            addCitations(messageElements, data.citations);
            break;
            
        case 'error':
            console.error('Stream error:', data.error);
            break;
            
        case 'done':
            // Stream complete
            break;
    }
}

// =============================================================================
// UI Helpers
// =============================================================================

function setStreaming(isStreaming) {
    state.isStreaming = isStreaming;
    elements.sendBtn.disabled = isStreaming;
    elements.userInput.disabled = isStreaming;
}

function hideWelcome() {
    if (elements.welcome) {
        elements.welcome.style.display = 'none';
    }
}

function scrollToBottom() {
    const container = document.querySelector('.chat-container');
    container.scrollTop = container.scrollHeight;
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function sendExample(button) {
    elements.userInput.value = button.textContent;
    sendMessage();
}

function startNewChat() {
    state.messages = [];
    state.currentTools = {};
    state.textBuffer = '';
    state.typewriterActive = false;
    state.currentMessageElements = null;
    
    // Clear messages and show welcome
    elements.messages.innerHTML = '';
    
    const welcome = document.createElement('div');
    welcome.className = 'welcome-message';
    welcome.id = 'welcome';
    welcome.innerHTML = `
        <div class="welcome-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
            </svg>
        </div>
        <h1>Welcome to Foundry Agent</h1>
        <p>Ask me anything about your knowledge base. I'll show you the tools and actions I use to find your answer.</p>
        <div class="example-prompts">
            <button class="example-btn" onclick="sendExample(this)">What insurance policies does Contoso offer?</button>
            <button class="example-btn" onclick="sendExample(this)">Tell me about the claims process</button>
            <button class="example-btn" onclick="sendExample(this)">What are the coverage limits?</button>
        </div>
    `;
    
    elements.messages.appendChild(welcome);
    elements.welcome = welcome;
    
    elements.userInput.value = '';
    elements.userInput.focus();
}

// =============================================================================
// Text Formatting
// =============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatToolName(name) {
    // Convert snake_case or camelCase to readable format
    return name
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/\b\w/g, c => c.toUpperCase());
}

function formatMarkdown(text) {
    // Basic markdown formatting
    let formatted = escapeHtml(text);
    
    // Bold: **text** or __text__
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/__(.+?)__/g, '<strong>$1</strong>');
    
    // Italic: *text* or _text_
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    formatted = formatted.replace(/_([^_]+)_/g, '<em>$1</em>');
    
    // Code: `code`
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Line breaks
    formatted = formatted.replace(/\n\n/g, '</p><p>');
    formatted = formatted.replace(/\n/g, '<br>');
    
    // Wrap in paragraph
    formatted = `<p>${formatted}</p>`;
    
    // Numbered lists
    formatted = formatted.replace(/<p>(\d+)\. /g, '<p class="list-item"><span class="list-number">$1.</span> ');
    
    return formatted;
}

// =============================================================================
// Global Functions (for onclick handlers)
// =============================================================================

window.sendMessage = sendMessage;
window.sendExample = sendExample;
window.startNewChat = startNewChat;
window.handleKeyDown = handleKeyDown;
window.autoResize = autoResize;

// =============================================================================
// Initialize
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    elements.userInput.focus();
});
