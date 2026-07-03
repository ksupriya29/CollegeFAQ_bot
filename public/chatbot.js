// ===== DOM Elements =====
const chatContainer = document.getElementById('chatContainer');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const voiceBtn = document.getElementById('voiceBtn');
const voiceModal = document.getElementById('voiceModal');
const voiceStopBtn = document.getElementById('voiceStopBtn');
const themeToggle = document.getElementById('themeToggle');
const clearChatBtn = document.getElementById('clearChat');
const hamburger = document.getElementById('hamburger');
const closeSidebar = document.getElementById('closeSidebar');
const sidebar = document.getElementById('sidebar');
const scrollBottomBtn = document.getElementById('scrollBottomBtn');
const welcomeMessage = document.getElementById('welcomeMessage');

// ===== State =====
let isListening = false;
let recognition = null;

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    // Update FAQ count
    document.getElementById('faqCount').textContent = faqDatabase.length;

    // Load theme preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    }

    // Event listeners
    sendBtn.addEventListener('click', handleSend);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });
    themeToggle.addEventListener('click', toggleTheme);
    clearChatBtn.addEventListener('click', clearChat);
    hamburger.addEventListener('click', toggleSidebar);
    closeSidebar.addEventListener('click', toggleSidebar);
    voiceBtn.addEventListener('click', startVoiceRecognition);
    voiceStopBtn.addEventListener('click', stopVoiceRecognition);
    scrollBottomBtn.addEventListener('click', scrollToBottom);

    // Scroll detection for bottom button
    chatContainer.addEventListener('scroll', () => {
        const isNearBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
        scrollBottomBtn.classList.toggle('visible', !isNearBottom);
    });
});

// ===== Send Message =====
function handleSend() {
    const query = userInput.value.trim();
    if (!query) return;

    // Hide welcome message on first message
    if (welcomeMessage && welcomeMessage.style.display !== 'none') {
        welcomeMessage.style.display = 'none';
    }

    addMessage(query, 'user');
    userInput.value = '';
    showTypingIndicator();

    setTimeout(() => {
        hideTypingIndicator();
        const response = findAnswer(query);
        addMessage(response, 'bot');
    }, 600 + Math.random() * 600);
}

// ===== Ask Question (from sidebar buttons / suggestion chips) =====
function askQuestion(query) {
    userInput.value = query;
    handleSend();
}

// ===== Find Answer in FAQ Database =====
function findAnswer(query) {
    const lowerQuery = query.toLowerCase().trim();
    
    // Check for greetings
    const greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "namaste", "hii", "hlo", "hey there"];
    if (greetings.some(g => lowerQuery.includes(g) || lowerQuery === g)) {
        return `👋 <strong>Hello!</strong> Welcome to the College FAQ Assistant!<br><br>
I can help you with information about:
<ul>
    <li>🎓 Admissions & Eligibility</li>
    <li>📚 Courses & Programs</li>
    <li>💰 Fee Structure & Scholarships</li>
    <li>💼 Placements & Internships</li>
    <li>🏛️ Campus Facilities & Hostel</li>
    <li>📝 Exams & Academics</li>
    <li>🎉 Student Clubs & Activities</li>
    <li>📞 Contact Information</li>
</ul>
<strong>How can I help you today?</strong> Just type your question or click on any suggestion! 😊`;
    }

    // Check for thanks
    const thanksWords = ["thank", "thanks", "thank you", "thx", "ty", "appreciate", "grateful", "thankyou"];
    if (thanksWords.some(t => lowerQuery.includes(t))) {
        return `😊 <strong>You're welcome!</strong> I'm glad I could help!<br><br>
If you have any more questions, feel free to ask. Here are some things you might want to know:
<ul>
    <li>🎓 <strong>Admission requirements</strong> - How to apply and eligibility</li>
    <li>💰 <strong>Fee structure</strong> - Tuition, hostel, and other fees</li>
    <li>📚 <strong>Courses offered</strong> - Programs and specializations</li>
    <li>💼 <strong>Placement record</strong> - Companies and packages</li>
    <li>🏛️ <strong>Campus facilities</strong> - Hostel, library, sports, etc.</li>
</ul>
Have a great day! 😊`;
    }

    // Check for goodbye
    const goodbyeWords = ["bye", "goodbye", "see you", "take care", "good night", "good day", "cya", "see ya"];
    if (goodbyeWords.some(b => lowerQuery.includes(b))) {
        return `👋 <strong>Goodbye!</strong> It was nice helping you!<br><br>
Feel free to come back anytime if you have more questions about college. Wishing you all the best in your academic journey! 🎓✨<br><br>
<strong>Quick links:</strong>
<ul>
    <li>📞 Contact admissions: admissions@college.edu.in</li>
    <li>🌐 Website: www.college.edu.in</li>
    <li>📍 Visit us: College Campus, Education District</li>
</ul>
Take care! 😊`;
    }

    // Search through FAQ database
    let bestMatch = null;
    let maxScore = 0;

    for (const faq of faqDatabase) {
        let score = 0;
        
        // Check each keyword
        for (const keyword of faq.keywords) {
            if (lowerQuery.includes(keyword)) {
                score += keyword.length;
            }
        }

        // Bonus for matching multiple keywords
        if (score > maxScore) {
            maxScore = score;
            bestMatch = faq;
        }
    }

    // If we found a good match (score threshold)
    if (bestMatch && maxScore > 3) {
        const categoryIcon = categoryIcons[bestMatch.category] || '📌';
        return `${categoryIcon} <strong>${bestMatch.category}</strong><br><br>${bestMatch.answer}`;
    }

    // No match found - provide helpful fallback
    return `🤔 <strong>I couldn't find a specific answer to your question.</strong><br><br>
Here are some topics I can help with. Please try asking about:<br><br>
<div class="fallback-suggestions">
    <span class="suggestion-chip" onclick="askQuestion('What are the admission requirements?')">🎓 Admission</span>
    <span class="suggestion-chip" onclick="askQuestion('What is the fee structure?')">💰 Fees</span>
    <span class="suggestion-chip" onclick="askQuestion('What courses are offered?')">📚 Courses</span>
    <span class="suggestion-chip" onclick="askQuestion('What is the placement record?')">💼 Placement</span>
    <span class="suggestion-chip" onclick="askQuestion('What are the hostel facilities?')">🏠 Hostel</span>
    <span class="suggestion-chip" onclick="askQuestion('Contact information')">📞 Contact</span>
</div><br>
Or type your question differently and I'll try my best to help! 😊`;
}

// ===== Add Message to Chat =====
function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = sender === 'bot' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-user"></i>';

    const content = document.createElement('div');
    content.className = 'message-content';
    content.innerHTML = text;

    const time = document.createElement('div');
    time.className = 'message-time';
    const now = new Date();
    time.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    content.appendChild(time);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatContainer.appendChild(messageDiv);

    scrollToBottom();
}

// ===== Typing Indicator =====
function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'typingIndicator';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = '<i class="fas fa-robot"></i>';

    const dots = document.createElement('div');
    dots.className = 'typing-dots';
    dots.innerHTML = '<span></span><span></span><span></span>';

    indicator.appendChild(avatar);
    indicator.appendChild(dots);
    chatContainer.appendChild(indicator);

    scrollToBottom();
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// ===== Theme Toggle =====
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    
    if (currentTheme === 'dark') {
        html.removeAttribute('data-theme');
        themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
        localStorage.setItem('theme', 'light');
    } else {
        html.setAttribute('data-theme', 'dark');
        themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        localStorage.setItem('theme', 'dark');
    }
}

// ===== Clear Chat =====
function clearChat() {
    // Remove all messages except welcome
    const messages = chatContainer.querySelectorAll('.message, .typing-indicator');
    messages.forEach(msg => msg.remove());
    
    // Show welcome message again
    if (welcomeMessage) {
        welcomeMessage.style.display = 'block';
    }

    scrollToBottom();
}

// ===== Sidebar Toggle (Mobile) =====
function toggleSidebar() {
    sidebar.classList.toggle('open');
}

// ===== Scroll to Bottom =====
function scrollToBottom() {
    setTimeout(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }, 50);
}

// ===== Voice Recognition =====
function startVoiceRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        addMessage('⚠️ <strong>Voice recognition is not supported in your browser.</strong> Please use Chrome, Edge, or Safari for voice input, or type your question instead.', 'bot');
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    voiceModal.classList.add('active');
    isListening = true;

    let finalTranscript = '';

    recognition.onresult = (event) => {
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }
        document.querySelector('.voice-modal-content p').textContent = 
            finalTranscript || interimTranscript || 'Listening...';
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        stopVoiceRecognition();
        if (event.error === 'no-speech') {
            addMessage('⚠️ <strong>No speech detected.</strong> Please try again or type your question.', 'bot');
        } else {
            addMessage('⚠️ <strong>Voice recognition error.</strong> Please try again or type your question.', 'bot');
        }
    };

    recognition.onend = () => {
        if (isListening && finalTranscript) {
            voiceModal.classList.remove('active');
            userInput.value = finalTranscript;
            handleSend();
        } else if (isListening) {
            voiceModal.classList.remove('active');
        }
        isListening = false;
    };

    recognition.start();
}

function stopVoiceRecognition() {
    if (recognition) {
        recognition.stop();
    }
    voiceModal.classList.remove('active');
    isListening = false;
}