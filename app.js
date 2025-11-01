// ---------- DOM Elements ----------
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const chatbox = document.getElementById("chatbox");
const langSelect = document.getElementById("langSelect");
const newChatBtn = document.getElementById("newChatBtn");
const chatHistoryContainer = document.querySelector(".chat-history");

// ---------- State ----------
let chats = JSON.parse(localStorage.getItem("chats")) || [];
let activeChatId = localStorage.getItem("activeChatId") || null;

// ---------- Helpers ----------
function saveChats() {
  localStorage.setItem("chats", JSON.stringify(chats));
  localStorage.setItem("activeChatId", activeChatId);
}

function scrollToBottom() {
  chatbox.scrollTop = chatbox.scrollHeight;
}

// ---------- Create message bubbles ----------
function appendMessage(sender, text, animate = false) {  // Added animate parameter
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message", sender);

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  
  if (sender === "bot" && animate) {
    // Typing animation ONLY when animate=true
    let i = 0;
    const typing = setInterval(() => {
      bubble.textContent = text.slice(0, i);
      i++;
      scrollToBottom();
      if (i > text.length) clearInterval(typing);
    }, 20);
  } else {
    // Instant display for welcome messages and user messages
    bubble.textContent = text;
  }
  
  msgDiv.appendChild(bubble);
  chatbox.appendChild(msgDiv);
  scrollToBottom();
}

// ---------- Display chat ----------
function displayChat(chatId) {
  const chat = chats.find(c => c.id === chatId);
  if (!chat) return;

  chatbox.innerHTML = "";
  // Display all existing messages instantly (no animation)
  chat.messages.forEach(m => appendMessage(m.sender, m.text, false));
  activeChatId = chatId;

  document.querySelectorAll(".history-item").forEach(i => i.classList.remove("active"));
  const activeItem = document.querySelector(`.history-item[data-id="${chatId}"]`);
  if (activeItem) activeItem.classList.add("active");

  saveChats();
}

// ---------- Update sidebar ----------
function refreshChatHistory() {
  chatHistoryContainer.innerHTML = "";
  chats.forEach(chat => {
    const div = document.createElement("div");
    div.classList.add("history-item");
    div.dataset.id = chat.id;
    div.textContent = chat.title || "New Chat";
    if (chat.id === activeChatId) div.classList.add("active");
    div.addEventListener("click", () => displayChat(chat.id));
    chatHistoryContainer.appendChild(div);
  });
}

// ---------- Create new chat ----------
function createNewChat() {
  const newChat = {
    id: Date.now().toString(),
    title: "New Chat",
    messages: [],
  };
  chats.unshift(newChat);
  activeChatId = newChat.id;
  refreshChatHistory();
  chatbox.innerHTML = "";
  
  // Welcome message - show instantly without typing animation
  const welcomeMessage = "👋 Hello! I'm your healthcare assistant. Ask about maternal health, HIV, nutrition, or any health topic.";
  appendMessage("bot", welcomeMessage, false); // false = no animation
  newChat.messages.push({ sender: "bot", text: welcomeMessage });
  
  saveChats();
}

// ---------- Update chat title ----------
function updateChatTitle(chatId, text) {
  const chat = chats.find(c => c.id === chatId);
  if (chat && chat.title === "New Chat") {
    chat.title = text.length > 30 ? text.slice(0, 30) + "..." : text;
    refreshChatHistory();
    saveChats();
  }
}

// ---------- Send message ----------
async function sendMessage() {
  const message = userInput.value.trim();
  const lang = langSelect.value;

  if (!message) return;

  if (!activeChatId) createNewChat();
  const chat = chats.find(c => c.id === activeChatId);

  // User message - show instantly
  appendMessage("user", message, false);
  chat.messages.push({ sender: "user", text: message });
  updateChatTitle(activeChatId, message);
  userInput.value = "";

  // Typing indicator
  const typingDiv = document.createElement("div");
  typingDiv.classList.add("message", "bot");
  typingDiv.innerHTML = `<div class="bubble"><em>Typing...</em></div>`;
  chatbox.appendChild(typingDiv);
  scrollToBottom();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, lang }),
    });

    const data = await res.json();
    chatbox.removeChild(typingDiv);
    
    // Bot response - show with typing animation
    appendMessage("bot", data.response, true); // true = with animation
    chat.messages.push({ sender: "bot", text: data.response });
  } catch (error) {
    chatbox.removeChild(typingDiv);
    appendMessage("bot", "⚠️ Network error. Please try again.", true);
  }

  saveChats();
}

// ---------- Event listeners ----------
chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage();
});

userInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

newChatBtn.addEventListener("click", createNewChat);

// ---------- Initialize ----------
if (chats.length === 0) {
  createNewChat();
} else {
  refreshChatHistory();
  displayChat(activeChatId || chats[0].id);
}

// Focus input on load
userInput.focus();