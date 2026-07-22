# Raksha 🛡️ — Digital Arrest Defense Platform

> **ET AI Hackathon 2.0 · Problem Statement 6 (Digital Public Safety)**

**Raksha** is a Digital Arrest Defense Platform designed to protect citizens from deceptive "digital arrest" scams. Real cybercriminals rely on three psychological levers to manipulate victims: **FEAR**, **URGENCY**, and **ISOLATION**. Raksha systematically breaks each of these levers while compiling tamper-evident evidence chains and campaign intelligence for law enforcement.

---

## 🧠 The Three Pillars of Digital Arrest Defense

### 1. Breaking FEAR: Scam Inoculation Simulator
Scammers use fake legal threats (CBI, TRAI, Customs) to induce panic. Raksha breaks this lever through the **Scam Inoculation Simulator** (available at `/Rehearsal.html`). 
*   **Active Training Rehearsals**: Citizens undergo realistic, safe, interactive conversation drills with a simulated scammer.
*   **Defensive Sanitization**: Post-LLM filters scrub and replace phone numbers, UPIs, and bank details with placeholder warnings to prevent copy-cat reuse.
*   **Psychological Debrief**: On hanging up, citizens receive a tailored debrief scorecard highlighting tactics used, user strengths, vulnerabilities, and the **3 Critical Rules of Defense**:
    1. *No agency arrests over video call.*
    2. *Never make a payment to avoid arrest.*
    3. *Always hang up and dial 1930.*

### 2. Breaking URGENCY: Live Call Guardian (LiveShield)
Scammers rush victims into making immediate bank transfers. Raksha breaks this lever with the **Live Call Guardian** (available at `/LiveShield.html`).
*   **Real-time Interception**: Performs stream-based, debounced WebSocket analysis of calls.
*   **Performance Cache**: Implements an in-memory LRU cache keyed on transcript hashes to keep response times sub-second.
*   **Lead-Time Metrics**: Tracks `time_to_detection_s` and the exact transcript chunk where the threat was confirmed.
*   **Zero-Transfer Guardrail Overlay**: Triggers an un-dismissible warning banner demanding the citizen hang up when scam risk hits $\ge 80\%$.
*   **WhatsApp Web Real-Time Chrome Extension (`extension/`)**: Content script that runs inside `web.whatsapp.com`. Automatically intercepts incoming chat messages on screen, highlights suspicious links in **RED**, injects `🛡️ RAKSHA WARNING` badges, and intercepts link clicks before opening harmful sites.

### 3. Breaking ISOLATION: Guardian Circle
Scammers order victims to stay silent and cut contacts. Raksha breaks this lever through the **Guardian Circle**.
*   **Emergency Contact Sync**: Allows citizens to register trusted contacts (Hindi, Telugu, Kannada labels).
*   **Automated Circle Alerts**: On digital-arrest classification or manual trigger, Raksha calls `POST /guardian/notify` to dispatch local emergency alert notifications to registered family members.
*   **Zero Third-Party Data Sharing**: Does not send user messages to Twilio or third-party servers. All pre-click scanning runs on-device via the extension and local backend engine.

---

## 🛠️ Quick Start

### 1. Set Up Virtual Environment & Dependencies
```bash
# Clone the repository
git clone https://github.com/Deepikachintamreddy/Raksha.git
cd Raksha

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install requirements
pip install -r backend/requirements.txt
```

### 2. Configure Environment variables
Create a `backend/.env` file:
```env
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.5-flash
TELEGRAM_BOT_TOKEN=8891965985:AAGXuhQ7cwj_2AVoGsxg4OOYFBKyNOJh0zs
TELEGRAM_CHAT_ID=6021694929
```

### 3. Run the Platform
```bash
# Start backend server
uvicorn backend.app.main:app --reload --port 8000
```
Open **`http://localhost:8000`** in your browser.

---

## 🌐 Platform API Endpoints

| Method | Path | Description |
|:---|:---|:---|
| `POST` | `/analyze` | Core multi-agent message/transcript scanner |
| `WS` | `/ws/live` | WebSocket call guardian streaming endpoint |
| `POST` | `/guardians` | Register a trusted contact |
| `GET` | `/guardians` | List all active guardians |
| `DELETE` | `/guardians/{id}` | Delete a guardian contact |
| `POST` | `/guardian/notify` | Dispatch WhatsApp alerts to Guardian Circle |
| `GET` | `/guardian/alerts` | List triggered guardian alerts |
| `POST` | `/rehearsal/start` | Start inoculation rehearsal session |
| `POST` | `/rehearsal/message` | Exchange messages with simulated scammer |
| `POST` | `/rehearsal/end` | End session and run debrief evaluation |
| `GET` | `/rehearsal/inoculated` | Get count of inoculated citizens |
| `GET` | `/campaigns` | Retrieve campaign graph and correlations |
| `GET` | `/audit/verify` | Walk ledger chain and verify block hashes |
| `GET` | `/metrics` | Hardened evaluation metrics and subset breakdowns |

---

## 🏆 5-Minute Judge Demo Script

### **0:00 - 1:00 | Intro: The Three Levers**
1. Open `http://localhost:8000`. Show the landing page and introduce Raksha's strategic repositioning.
2. Explain that traditional tools fail because they only analyze text; Raksha is a **Digital Arrest Defense Platform** targeting the psychological levers scammers use: **FEAR**, **URGENCY**, and **ISOLATION**.

### **1:00 - 2:30 | Urgency & Isolation: LiveShield & Guardian Circle**
1. Navigate to **⚡ LiveShield** (`/LiveShield.html`).
2. Register a Guardian contact in the settings panel (e.g. name: "Jane", WhatsApp number). Show the Hindi/Telugu/Kannada labels emphasizing protection for elderly family members.
3. Click `▶️ Play Call` to trigger the demo script simulation.
4. Watch as the transcript streams in: *"Telecom Authority TRAI... warrant under your name... you are under digital arrest..."*
5. Point out the **Risk Meter** climbing. Within 3 chunks, the risk crosses $80\%$, popping up the full-screen **🚨 DO NOT TRANSFER MONEY** banner. Highlight the Lead-Time Story metrics showing the exact time-to-detection.
6. Click **`👥 Alert My Guardian`**. On screen, show the simulated notification detailing exactly who was texted and the custom WhatsApp alert sent.

### **2:30 - 4:00 | Fear: Scam Inoculation Simulator**
1. Navigate to **🎓 Rehearsal** (`/Rehearsal.html`).
2. Show the "Citizens Inoculated" counter.
3. Click `▶️ Start Rehearsal` to load the simulation. The simulated BSNL/CBI scammer initiates the call.
4. Type replies (e.g., *"Why can't I call my lawyer?"* or *"Let me call 1930"*). Note how the scammer escalates threats but uses safe placeholders like `officer.sharma@placeholder`.
5. Click **`📴 Hang Up`**. Show the immediately populated **Psychological Debriefing Scorecard**. Point out the detected manipulation tactics, what you did well (e.g., refusing to comply), vulnerabilities, and the 3 rules of defense.

### **4:00 - 5:00 | Campaign Graph & Evaluation (I4C Dashboard)**
1. Navigate to **🕸️ Intel** (`/Intel.html`). Show how multiple digital arrest cases are correlated in real-time based on shared entities (e.g. phone numbers, UPI IDs) or semantic script similarity, allowing I4C law enforcement teams to trace entire syndicates.
2. Navigate to **📊 Evaluation** (`/EvalDashboard.html`). Highlight the hardened metrics: **0.0% False Positive Rate** on the hard-negatives subset, and **100% Injection Resistance Rate** against jailbreak prompt attacks.
3. Navigate to **📋 Cases** (`/CaseLog.html`) and click `🛡️ Verify Ledger Chain` to show that every case and evidence package is secured in a tamper-evident cryptographic block-hash ledger.
