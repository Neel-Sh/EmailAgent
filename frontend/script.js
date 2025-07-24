// Global state
let sessionId = null;
let currentEmailDraft = null;
let isLoading = false;

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const typingIndicator = document.getElementById('typingIndicator');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const charCount = document.getElementById('charCount');
const emailModal = document.getElementById('emailModal');
const emailPreview = document.getElementById('emailPreview');
const sendEmailBtn = document.getElementById('sendEmailBtn');
const fullEmailModal = document.getElementById('fullEmailModal');
const fullEmailContent = document.getElementById('fullEmailContent');
const loadingOverlay = document.getElementById('loadingOverlay');

// API base URL
const API_BASE = window.location.origin;

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    checkBackendHealth();
});

function initializeApp() {
    // Generate session ID
    sessionId = generateSessionId();
    
    // Set initial status
    updateStatus('connecting', 'Connecting...');
    
    // Focus input
    messageInput.focus();
    
    console.log('🚀 Email Agent initialized with session:', sessionId);
}

function setupEventListeners() {
    // Send button
    sendButton.addEventListener('click', sendMessage);
    
    // Enter key in input
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Input changes
    messageInput.addEventListener('input', function() {
        updateCharCount();
        updateSendButton();
        autoResize();
    });
    
    // Close modal on background click
    emailModal.addEventListener('click', function(e) {
        if (e.target === emailModal) {
            closeEmailModal();
        }
    });
    
    // Escape key to close modal
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && emailModal.style.display !== 'none') {
            closeEmailModal();
        }
    });
}

function updateCharCount() {
    const count = messageInput.value.length;
    charCount.textContent = `${count} / 500`;
    
    if (count > 450) {
        charCount.style.color = 'var(--error)';
    } else if (count > 300) {
        charCount.style.color = 'var(--warning)';
    } else {
        charCount.style.color = 'var(--text-light)';
    }
}

function updateSendButton() {
    const hasText = messageInput.value.trim().length > 0;
    sendButton.disabled = !hasText || isLoading;
}

function autoResize() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

function generateSessionId() {
    return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
}

async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE}/api/health`);
        if (response.ok) {
            updateStatus('connected', 'Connected');
        } else {
            updateStatus('error', 'Backend Error');
        }
    } catch (error) {
        console.error('Health check failed:', error);
        updateStatus('error', 'Connection Failed');
    }
}

function updateStatus(type, text) {
    statusDot.className = `status-dot ${type}`;
    statusText.textContent = text;
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || isLoading) return;
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Clear input
    messageInput.value = '';
    updateCharCount();
    updateSendButton();
    autoResize();
    
    // Show typing indicator
    showTypingIndicator();
    
    // Send to backend
    await processMessage(message);
}

function addMessage(content, role, extraData = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    const messageText = document.createElement('div');
    messageText.className = 'message-text';
    
    if (role === 'assistant' && extraData.type === 'email_draft') {
        // Special handling for email drafts
        messageText.innerHTML = content;
        
        // Add email draft card if present
        if (extraData.email_draft) {
            const emailCard = createEmailDraftCard(extraData.email_draft);
            messageContent.appendChild(emailCard);
        }
    } else {
        // Regular message - support markdown-like formatting and view email buttons
        messageText.innerHTML = formatMessage(content);
        
        // Add event listeners for view email buttons
        if (role === 'assistant' && content.includes('view-email-btn')) {
            setTimeout(() => {
                const viewButtons = messageText.querySelectorAll('.view-email-btn');
                viewButtons.forEach(button => {
                    button.addEventListener('click', function() {
                        const emailId = this.getAttribute('data-email-id');
                        viewFullEmail(emailId);
                    });
                });
            }, 10);
        }
    }
    
    messageContent.appendChild(messageText);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function formatMessage(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>')
        .replace(/📧\s*\*\*(.*?)\*\*/g, '📧 <strong>$1</strong>')
        .replace(/(\d+)\.\s/g, '<br>$1. ')
        // Handle view email buttons
        .replace(/<button class='view-email-btn' data-email-id='([^']+)'>([^<]+)<\/button>/g, 
                '<button class="view-email-btn" data-email-id="$1">$2</button>');
}

function createEmailDraftCard(emailDraft) {
    const card = document.createElement('div');
    card.className = 'email-draft-card';
    
    const confidenceClass = getConfidenceClass(emailDraft.confidence);
    if (confidenceClass) {
        card.classList.add(confidenceClass);
    }
    
    card.innerHTML = `
        <div class="email-summary">
            <strong>📝 ${emailDraft.summary || 'Email Draft'}</strong>
            <p><strong>To:</strong> ${emailDraft.to || 'Not specified'}</p>
            <p><strong>Subject:</strong> ${emailDraft.subject || 'No subject'}</p>
        </div>
        <div class="email-actions">
            <button class="btn btn-primary" onclick="showEmailPreview('${btoa(JSON.stringify(emailDraft))}')">
                <i class="fas fa-eye"></i> Preview & Send
            </button>
            <button class="btn btn-secondary" onclick="regenerateEmail()">
                <i class="fas fa-redo"></i> Regenerate
            </button>
        </div>
    `;
    
    return card;
}

function getConfidenceClass(confidence) {
    if (confidence <= 0.3) return 'confidence-low';
    if (confidence <= 0.7) return 'confidence-medium';
    if (confidence > 0.7) return 'confidence-high';
    return '';
}

function showTypingIndicator() {
    typingIndicator.style.display = 'flex';
    scrollToBottom();
}

function hideTypingIndicator() {
    typingIndicator.style.display = 'none';
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function processMessage(message) {
    isLoading = true;
    updateSendButton();
    
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Update session ID if provided
        if (data.session_id) {
            sessionId = data.session_id;
        }
        
        // Hide typing indicator
        hideTypingIndicator();
        
        // Add assistant response
        addMessage(data.message, 'assistant', data);
        
        // Store email draft if present
        if (data.email_draft) {
            currentEmailDraft = data.email_draft;
        }
        
    } catch (error) {
        console.error('Error processing message:', error);
        hideTypingIndicator();
        addMessage(`Sorry, I encountered an error: ${error.message}. Please try again.`, 'assistant');
    } finally {
        isLoading = false;
        updateSendButton();
    }
}

function quickAction(action) {
    messageInput.value = action;
    updateCharCount();
    updateSendButton();
    messageInput.focus();
}

function showEmailPreview(encodedDraft) {
    try {
        const emailDraft = JSON.parse(atob(encodedDraft));
        currentEmailDraft = emailDraft;
        
        emailPreview.innerHTML = `
            <div class="email-header">
                <div class="email-field">
                    <strong>To:</strong> ${emailDraft.to || 'Not specified'}
                </div>
                <div class="email-field">
                    <strong>Subject:</strong> ${emailDraft.subject || 'No subject'}
                </div>
                <div class="email-field">
                    <strong>Tone:</strong> ${emailDraft.tone || 'Not specified'}
                </div>
            </div>
            <div class="email-body">${emailDraft.body || 'No content'}</div>
        `;
        
        emailModal.style.display = 'flex';
        
        // Disable send button if no recipient
        sendEmailBtn.disabled = !emailDraft.to;
        
    } catch (error) {
        console.error('Error showing email preview:', error);
        addMessage('Error displaying email preview. Please try again.', 'assistant');
    }
}

function closeEmailModal() {
    emailModal.style.display = 'none';
    currentEmailDraft = null;
}

async function sendEmail() {
    if (!currentEmailDraft || !currentEmailDraft.to) {
        alert('Please specify a recipient before sending.');
        return;
    }
    
    // Show loading
    sendEmailBtn.disabled = true;
    sendEmailBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
    
    try {
        const response = await fetch(`${API_BASE}/api/send-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                email_draft: currentEmailDraft
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Close modal
            closeEmailModal();
            
            // Add success message to chat
            addMessage(result.message, 'assistant');
            
            // Show success animation
            showSuccessAnimation();
            
        } else {
            throw new Error(result.message || 'Failed to send email');
        }
        
    } catch (error) {
        console.error('Error sending email:', error);
        alert(`Failed to send email: ${error.message}`);
        
        // Add error message to chat
        addMessage(`❌ ${error.message}`, 'assistant');
        
    } finally {
        // Reset button
        sendEmailBtn.disabled = false;
        sendEmailBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Send Email';
    }
}

function showSuccessAnimation() {
    // Create temporary success indicator
    const successDiv = document.createElement('div');
    successDiv.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: var(--success);
        color: white;
        padding: 1rem 2rem;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow-xl);
        z-index: 3000;
        animation: successPop 2s ease-out forwards;
        font-weight: 600;
    `;
    successDiv.innerHTML = '✅ Email sent successfully!';
    
    document.body.appendChild(successDiv);
    
    // Remove after animation
    setTimeout(() => {
        document.body.removeChild(successDiv);
    }, 2000);
    
    // Add animation CSS
    if (!document.getElementById('success-animation-style')) {
        const style = document.createElement('style');
        style.id = 'success-animation-style';
        style.textContent = `
            @keyframes successPop {
                0% {
                    opacity: 0;
                    transform: translate(-50%, -50%) scale(0.8);
                }
                20% {
                    opacity: 1;
                    transform: translate(-50%, -50%) scale(1.1);
                }
                100% {
                    opacity: 0;
                    transform: translate(-50%, -50%) scale(1);
                }
            }
        `;
        document.head.appendChild(style);
    }
}

function regenerateEmail() {
    const lastUserMessage = getLastUserMessage();
    if (lastUserMessage) {
        messageInput.value = lastUserMessage + ' (please regenerate with a different approach)';
        updateCharCount();
        updateSendButton();
        messageInput.focus();
    }
}

function getLastUserMessage() {
    const userMessages = document.querySelectorAll('.user-message .message-text');
    if (userMessages.length > 0) {
        return userMessages[userMessages.length - 1].textContent.trim();
    }
    return '';
}

// Error handling for fetch requests
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    updateStatus('error', 'Connection Error');
    
    if (isLoading) {
        hideTypingIndicator();
        addMessage('Sorry, I lost connection to the server. Please check your internet connection and try again.', 'assistant');
        isLoading = false;
        updateSendButton();
    }
});

// Connection monitoring
let connectionCheckInterval;

function startConnectionMonitoring() {
    connectionCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/health`);
            if (response.ok) {
                updateStatus('connected', 'Connected');
            } else {
                updateStatus('error', 'Backend Error');
            }
        } catch (error) {
            updateStatus('error', 'Connection Lost');
        }
    }, 30000); // Check every 30 seconds
}

function stopConnectionMonitoring() {
    if (connectionCheckInterval) {
        clearInterval(connectionCheckInterval);
    }
}

// Start monitoring when page is visible
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        stopConnectionMonitoring();
    } else {
        startConnectionMonitoring();
        checkBackendHealth();
    }
});

// Start monitoring initially
startConnectionMonitoring();

// Utility functions
function showLoading() {
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

// PWA-like features
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        // Service worker registration would go here
        console.log('🔧 Email Agent ready for offline capabilities');
    });
}

console.log('🤖 Email Agent frontend loaded successfully!');

async function viewFullEmail(emailId) {
    try {
        showLoading();
        
        const response = await fetch(`${API_BASE}/api/get-full-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                email_id: emailId
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.email) {
            showFullEmailModal(data.email);
        } else {
            // Show error message
            addMessage(data.message || 'Could not retrieve email details.', 'assistant');
        }
        
    } catch (error) {
        console.error('Error viewing full email:', error);
        addMessage('Sorry, I had trouble retrieving that email. Please try again.', 'assistant');
    } finally {
        hideLoading();
    }
}

function showFullEmailModal(email) {
    const formattedDate = new Date(email.date).toLocaleString();
    
    fullEmailContent.innerHTML = `
        <div class="email-header">
            <div class="email-field">
                <strong>📧 Subject:</strong>
                <span>${email.subject}</span>
            </div>
            <div class="email-field">
                <strong>👤 From:</strong>
                <span>${email.sender}</span>
            </div>
            <div class="email-field">
                <strong>📅 Date:</strong>
                <span>${email.date}</span>
            </div>
        </div>
        <div class="email-body">
            <strong>💬 Content:</strong>
            <div class="email-content">
                ${email.body.replace(/\n/g, '<br>')}
            </div>
        </div>
    `;
    
    fullEmailModal.style.display = 'flex';
    
    // Add escape key handler
    document.addEventListener('keydown', handleFullEmailEscape);
}

function closeFullEmailModal() {
    fullEmailModal.style.display = 'none';
    document.removeEventListener('keydown', handleFullEmailEscape);
}

function handleFullEmailEscape(e) {
    if (e.key === 'Escape') {
        closeFullEmailModal();
    }
} 