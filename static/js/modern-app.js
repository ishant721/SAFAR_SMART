// Modern App JavaScript

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Navbar scroll effect
window.addEventListener('scroll', function() {
    const navbar = document.querySelector('.navbar-modern');
    if (window.scrollY > 50) {
        navbar.style.background = 'rgba(255, 255, 255, 0.98)';
        navbar.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.background = 'rgba(255, 255, 255, 0.95)';
        navbar.style.boxShadow = 'none';
    }
});

// Loading overlay functions
function showLoading(message = 'Processing...') {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.id = 'loadingOverlay';
    overlay.innerHTML = `
        <div class="loading-content">
            <div class="loading-spinner mb-3"></div>
            <p class="mb-0">${message}</p>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.remove();
    }
}

// Notification system
function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="bi bi-${getNotificationIcon(type)} me-2"></i>
            <span>${message}</span>
            <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Auto hide
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, duration);
}

function getNotificationIcon(type) {
    const icons = {
        success: 'check-circle-fill',
        error: 'exclamation-triangle-fill',
        warning: 'exclamation-triangle-fill',
        info: 'info-circle-fill'
    };
    return icons[type] || 'info-circle-fill';
}

// Form enhancements
document.addEventListener('DOMContentLoaded', function() {
    const mainNav = document.getElementById('mainNav');
    if (mainNav) {
        window.addEventListener('scroll', function () {
            if (window.scrollY > 50) {
                mainNav.classList.add('navbar-scrolled');
            } else {
                mainNav.classList.remove('navbar-scrolled');
            }
        });
    }

    // Add floating label effect to forms
    const formControls = document.querySelectorAll('.form-floating-modern input, .form-floating-modern textarea');
    formControls.forEach(control => {
        // Set initial state
        if (control.value) {
            control.classList.add('has-value');
        }
        
        // Handle input events
        control.addEventListener('input', function() {
            if (this.value) {
                this.classList.add('has-value');
            } else {
                this.classList.remove('has-value');
            }
        });
    });
    
    // Add animation delays to cards
    const cards = document.querySelectorAll('.card-modern, .stats-card, .trip-card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in-up');
    });
});

// Trip processing functions
function processTrip(agentName, tripId) {
    showLoading(`Generating ${agentName.replace('_', ' ')}...`);
    
    fetch(`/planner/process_trip/${tripId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: `agent_name=${agentName}&user_question=Generate ${agentName.replace('_', ' ')}`
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.status === 'success') {
            showNotification('Information generated successfully!', 'success');
            if (data.warning) {
                showNotification('Warning: ' + data.warning, 'warning');
            }
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoading();
        console.error('Error:', error);
        showNotification('An error occurred while processing your request.', 'error');
    });
}

// Chat functionality
function initializeChat() {
    const chatForm = document.getElementById('chatForm');
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const question = formData.get('user_question');
            
            if (!question.trim()) return;
            
            // Add user message to chat
            addChatMessage(question, 'user');
            
            // Clear input
            this.querySelector('input[name="user_question"]').value = '';
            
            // Show typing indicator
            addTypingIndicator();
            
            // Send request
            fetch(this.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                removeTypingIndicator();
                if (data.status === 'success') {
                    addChatMessage(data.chat_response, 'ai');
                    if (data.warning) {
                        showNotification('Warning: ' + data.warning, 'warning');
                    }
                } else {
                    addChatMessage('Sorry, I encountered an error. Please try again.', 'ai');
                    showNotification('Error: ' + data.message, 'error');
                }
            })
            .catch(error => {
                removeTypingIndicator();
                console.error('Error:', error);
                addChatMessage('Sorry, I encountered an error. Please try again.', 'ai');
                showNotification('An error occurred while sending your message.', 'error');
            });
        });
    }
}

function addChatMessage(message, sender) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message chat-message-${sender}`;
    
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble chat-bubble-${sender}`;
    bubble.innerHTML = message;
    
    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addTypingIndicator() {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-message chat-message-ai';
    typingDiv.id = 'typingIndicator';
    
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble chat-bubble-ai';
    bubble.innerHTML = '<i class="bi bi-three-dots"></i> AI is typing...';
    
    typingDiv.appendChild(bubble);
    chatMessages.appendChild(typingDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Initialize chat when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeChat();
});



// Intersection Observer for animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('fade-in-up');
        }
    });
}, observerOptions);

// Observe elements for animation
document.addEventListener('DOMContentLoaded', function() {
    const animatedElements = document.querySelectorAll('.card-modern, .feature-card, .stats-card');
    animatedElements.forEach(el => observer.observe(el));
});

// Typing animation for hero title
document.addEventListener('DOMContentLoaded', function() {
    const heroTitle = document.querySelector('.hero-title .text-gradient');
    if (heroTitle) {
        const text = heroTitle.textContent;
        heroTitle.textContent = '';
        let i = 0;
        function typeWriter() {
            if (i < text.length) {
                heroTitle.textContent += text.charAt(i);
                i++;
                setTimeout(typeWriter, 100);
            }
        }
        typeWriter();
    }
});
