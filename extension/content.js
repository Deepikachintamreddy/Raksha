// Raksha — Universal Web Messaging Scam & Phishing Shield
// Content script running across Instagram, WhatsApp, Telegram, Facebook, Gmail, Google Messages, X (Twitter), LinkedIn, etc.

console.log("%c 🛡️ Raksha Universal Real-Time Shield Active across all Social & Messaging Web Apps ", "background: #1e1b4b; color: #818cf8; font-weight: bold; font-size: 14px; padding: 4px 8px; border-radius: 4px;");

const RAKSHA_API_URL = "http://localhost:8000/analyze";
const processedMessages = new WeakSet();
const classificationCache = new Map();

// Fast pre-filter regex for instant link / keyword flagging before network call
const FAST_SCAM_KEYWORDS = /\b(cbi|trai|customs|digital arrest|warrant|money laundering|lottery|kbc|safe account|verify account|aadhaar blocked|sim blocked|apk|free gift)\b/i;
const SUSPECT_URL_PATTERN = /(https?:\/\/[^\s]+)/gi;

// Supported App Target Selectors for Instagram, WhatsApp, Telegram, Facebook, Messenger, Gmail, X, LinkedIn, Google Messages
const APP_SELECTORS = [
  ".message-in, .message-out, div[role='row']",               // WhatsApp Web & Facebook Messenger
  ".message, .bubble, .Message",                            // Telegram Web
  "mws-message-wrapper, .message-content",                   // Google Messages (SMS Web)
  ".a3s, .a3s.aiL, div[role='listitem']",                    // Gmail Email Body
  "div[data-scope='messages_table'], div[role='dialog']",     // Instagram Direct Messages
  "div[data-testid='tweetText'], div[data-testid='messageEntry']", // X (Twitter) Posts & DMs
  ".msg-s-event-listitem__body, .msg-s-message-group"        // LinkedIn Direct Messages
].join(", ");

/**
 * Scan a single message element
 */
async function scanMessageElement(msgNode) {
  if (!msgNode || processedMessages.has(msgNode)) return;
  processedMessages.add(msgNode);

  // Extract text content from message bubble / email / DM container
  const textEl = msgNode.querySelector(".selectable-text, ._ao3e, span.dir-ltr, .copyable-text, .message-title, .ii.gt, .a3s, [data-testid='tweetText']") || msgNode;
  if (!textEl) return;

  const text = textEl.textContent.trim();
  if (!text || text.length < 5) return;

  // Check if contains links or scam keywords
  const hasLinks = SUSPECT_URL_PATTERN.test(text);
  const hasScamKeywords = FAST_SCAM_KEYWORDS.test(text);

  if (!hasLinks && !hasScamKeywords) return;

  // Instant local visual warning if urgent scam keywords match
  if (hasScamKeywords) {
    flagMessageAsScam(msgNode, textEl, {
      verdict: "SCAM",
      reasons: "Fast-Filter: Contains urgent digital arrest or scare keywords.",
      confidence: 0.95
    });
  }

  // Deep AI Analysis via Raksha API
  if (classificationCache.has(text)) {
    const cached = classificationCache.get(text);
    if (cached.verdict === "SCAM") {
      flagMessageAsScam(msgNode, textEl, cached);
    }
    return;
  }

  try {
    const response = await fetch(RAKSHA_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    });

    if (!response.ok) return;

    const data = await response.json();
    classificationCache.set(text, data);

    if (data.verdict === "SCAM") {
      flagMessageAsScam(msgNode, textEl, data);
    }
  } catch (err) {
    // Backend offline or unreachable — fast regex fallback already applied
  }
}

/**
 * Flag a message as a SCAM inside DOM
 */
function flagMessageAsScam(msgNode, textEl, result) {
  if (msgNode.querySelector(".raksha-scam-badge")) return;

  // 1. Highlight links in RED and intercept clicks BEFORE opening
  const links = msgNode.querySelectorAll("a");
  links.forEach(link => {
    link.classList.add("raksha-link-danger");
    link.title = "🚨 RAKSHA WARNING: This link has been flagged as suspicious!";
    
    // Intercept click to warn user BEFORE opening URL
    link.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      const targetUrl = link.href || link.textContent;
      showClickInterceptionModal(targetUrl, result);
      return false;
    }, true);
  });

  // 2. Append Raksha Scam Badge directly below the message
  const badge = document.createElement("div");
  badge.className = "raksha-scam-badge";
  badge.innerHTML = `🛡️ <span>RAKSHA WARNING: SUSPICIOUS MESSAGE</span>`;
  badge.title = result.reasons || "Flagged by Raksha AI Fraud Shield";
  
  badge.onclick = (e) => {
    e.stopPropagation();
    showFloatingAlert(textEl.textContent, result);
  };

  textEl.parentNode.appendChild(badge);

  // 3. Display floating alert notification
  showFloatingAlert(textEl.textContent, result);
}

/**
 * Interception modal when user clicks a suspicious link
 */
function showClickInterceptionModal(targetUrl, result) {
  document.querySelectorAll(".raksha-alert-overlay").forEach(el => el.remove());

  const overlay = document.createElement("div");
  overlay.className = "raksha-alert-overlay";
  overlay.innerHTML = `
    <div class="raksha-alert-title">
      🚨 DO NOT CLICK THIS LINK
    </div>
    <div class="raksha-alert-body">
      <strong>Flagged URL:</strong> <code style="color: #fca5a5;">${escapeHtml(targetUrl)}</code><br><br>
      Raksha AI detected this link as part of a scam or phishing campaign. Opening this link may compromise your bank details or credentials.
    </div>
    <div class="raksha-alert-actions">
      <button class="raksha-btn raksha-btn-secondary" id="rakshaDismissBtn">Cancel & Stay Safe</button>
      <button class="raksha-btn raksha-btn-danger" id="rakshaProceedBtn" style="opacity: 0.7;">Proceed Anyway</button>
    </div>
  `;

  document.body.appendChild(overlay);

  document.getElementById("rakshaDismissBtn").onclick = () => overlay.remove();
  document.getElementById("rakshaProceedBtn").onclick = () => {
    if (confirm("⚠️ ARE YOU SURE? This site is flagged as dangerous.")) {
      window.open(targetUrl, "_blank", "noopener,noreferrer");
    }
    overlay.remove();
  };
}

/**
 * Floating toast notification
 */
function showFloatingAlert(messageText, result) {
  let toast = document.getElementById("rakshaToastAlert");
  if (toast) toast.remove();

  toast = document.createElement("div");
  toast.id = "rakshaToastAlert";
  toast.className = "raksha-alert-overlay";
  toast.style.top = "20px";
  toast.style.right = "20px";
  toast.innerHTML = `
    <div class="raksha-alert-title">
      🛡️ RAKSHA SCAM INTERCEPTED
    </div>
    <div class="raksha-alert-body">
      A digital arrest or phishing message was detected on your screen.<br>
      <span style="font-style: italic; opacity: 0.8; margin-top: 4px; display: block;">
        "${escapeHtml(messageText.substring(0, 100))}..."
      </span>
    </div>
    <div class="raksha-alert-actions">
      <button class="raksha-btn raksha-btn-danger" id="closeToastBtn">Got it</button>
    </div>
  `;

  document.body.appendChild(toast);
  document.getElementById("closeToastBtn").onclick = () => toast.remove();

  setTimeout(() => {
    if (toast.parentNode) toast.remove();
  }, 8000);
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, function (m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
  });
}

/**
 * Observe DOM across supported web apps
 */
function observeAppDOM() {
  const targetNode = document.body;
  const config = { childList: true, subtree: true };

  const callback = (mutationsList) => {
    for (const mutation of mutationsList) {
      if (mutation.addedNodes.length > 0) {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const messages = node.querySelectorAll ? node.querySelectorAll(APP_SELECTORS) : [];
            messages.forEach(msg => scanMessageElement(msg));
            if (node.matches && node.matches(APP_SELECTORS)) {
              scanMessageElement(node);
            }
          }
        });
      }
    }
  };

  const observer = new MutationObserver(callback);
  observer.observe(targetNode, config);

  // Initial sweep
  document.querySelectorAll(APP_SELECTORS).forEach(msg => scanMessageElement(msg));
}

// Start observation
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", observeAppDOM);
} else {
  observeAppDOM();
}

// Periodically sweep
setInterval(() => {
  document.querySelectorAll(APP_SELECTORS).forEach(msg => scanMessageElement(msg));
}, 3000);
