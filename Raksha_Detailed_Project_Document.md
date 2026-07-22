# 🛡️ RAKSHA: CITIZEN FRAUD SHIELD & DIGITAL ARREST DEFENSE PLATFORM
**Executive Detailed Technical Project Document**  
*ET AI Hackathon 2.0 — Problem Statement 6 (Digital Public Safety & Cybercrime Mitigation)*  
**Official GitHub Repository**: https://github.com/Deepikachintamreddy/Raksha

---

## 1. Executive Summary

**Raksha** is an AI-powered Citizen Fraud Shield engineered to combat complex telecommunication fraud in India—specifically high-coercion **"Digital Arrest"** scams, authority impersonation (CBI, TRAI, Customs), and financial phishing attacks. 

Traditional fraud filters rely on static keyword blocking, which fails when scammers use dynamic scripts over phone and video calls. Raksha addresses the core psychological mechanism of Digital Arrest scams by targeting their three fundamental levers:
1. **FEAR** → Mitigated via **AI Scam Inoculation Rehearsals** (building citizen psychological resilience).
2. **URGENCY** → Mitigated via **Real-time Signal Extraction** & 1930 Cybercrime Complaint Auto-Drafting.
3. **ISOLATION** → Mitigated via **Automated Family Guardian Escalation** (dispatched live to Telegram).

Built on top of **Google Gemini 2.5 Flash**, FastAPI, and an immutable SHA-256 evidence ledger, Raksha creates an end-to-end defense ecosystem connecting citizens, family guardians, and law enforcement.

---

## 2. Problem Statement & Domain Context

### 2.1 The Threat Landscape: "Digital Arrest" Scams
Digital Arrest is a sophisticated cybercrime tactic where scammers impersonate law enforcement officers (CBI, State Police, TRAI, Customs). They inform victims that their Aadhaar/Mobile number is linked to money laundering or narcotics, demanding they stay on continuous video calls under threat of immediate arrest unless a "security deposit" is transferred.

### 2.2 Why Existing Solutions Fail
* **Lack of Isolation Breaking**: Victims are forced to remain silent; existing apps only notify the victim who is already in a state of panic.
* **No Legal Evidence Trail**: Victims struggle to document exact coercion timelines for law enforcement.
* **Lack of Citizen Training**: Defensive awareness is passive rather than experiential.

---

## 3. System Architecture & Core Pillars

Raksha operates through **5 integrated pillars**:

```
+-----------------------------------------------------------------------------------+
|                                  RAKSHA ECOSYSTEM                                 |
+-----------------------------------------------------------------------------------+
|  1. WhatsApp Chrome Extension  --> In-situ messaging threat detection             |
|  2. Citizen Shield Web App     --> Gemini 2.5 AI Analysis & 1930 Complaint Draft    |
|  3. Telegram Guardian Bot      --> Real-time Family Escalation (Breaks Isolation) |
|  4. Rehearsal Simulator        --> Interactive AI Roleplay & Resilience Scorecard |
|  5. Audit Ledger Store          --> Tamper-evident SHA-256 Evidence Chain          |
+-----------------------------------------------------------------------------------+
```

### Pillar 1: Citizen Fraud Shield (`index.html`)
* **Multi-Agent Classification Engine**: Leverages Gemini 2.5 Flash to analyze text messages, call transcripts, and SMS.
* **Scam Signal Extraction**: Automatically identifies coercive tactics (*Authority Impersonation*, *Isolation Demand*, *Urgent Financial Demands*).
* **Automated 1930 Complaint Drafting**: Generates a pre-formatted legal complaint ready for immediate filing on the National Cybercrime Reporting Portal (`cybercrime.gov.in`).

### Pillar 2: Automated Family Guardian Escalation (`@Raksha_Guardian_Bot`)
* **Bypassing Scammer Isolation**: When high-risk scams are detected, Raksha dispatches a real-time push notification to registered family guardians via Telegram.
* **Actionable Guardian Guidance**: Prompts relatives with clear rescue steps (*"Call victim immediately, break video call isolation, tell them to hang up"*).
* **Inbound Spam Detection**: Allows family members to forward suspicious messages directly to the bot for instant safety verification.

### Pillar 3: Scam Inoculation Rehearsal Simulator (`Rehearsal.html`)
* **Interactive AI Roleplay**: Citizens safely practice handling simulated scam scenarios (Digital Arrest, KYC Suspension, Courier Narcotics) against an AI scammer.
* **Debriefing Scorecard**: Upon hanging up, citizens receive a personalized safety scorecard, measuring psychological resilience and highlighting tactical mistakes.

### Pillar 4: Cryptographic Tamper-Evident Evidence Ledger (`CaseLog.html`)
* **Legal Admissibility**: Stored in a SQLite audit ledger using SHA-256 cryptographic hash chaining (`Verify Ledger Chain`).
* **Evidence Package Export**: Exports complete JSON evidence packages containing timestamps, full LLM prompts, model versioning, and extracted entities for police investigations.

### Pillar 5: WhatsApp Web Real-Time Chrome Extension (`extension/`)
* **In-Situ In-Browser Defense**: A Manifest V3 Chrome Extension that injects directly into `web.whatsapp.com`, scanning incoming messages and placing warning badges on phishing links.

---

## 4. Technical Stack & Implementation

| Layer | Technology Used | Purpose |
|:---|:---|:---|
| **AI / LLM Engine** | Google Gemini 2.5 Flash | High-speed multi-agent classification & simulation |
| **Backend Framework** | Python 3.11, FastAPI, Uvicorn | Asynchronous REST APIs & WebSocket streaming |
| **Database & Audit** | SQLite, SQLAlchemy, SHA-256 | Tamper-evident evidence ledger store |
| **Messaging Integration**| Telegram Bot API (`python-telegram-bot` / HTTP) | Real-time family guardian push notifications |
| **Browser Extension** | Chrome Extension Manifest V3 (JS Content Script) | WhatsApp Web in-chat real-time scanning |
| **Frontend UI** | HTML5, CSS3 (Vanilla Design System), JavaScript | Responsive, high-contrast, zero-framework UI |

---

## 5. API Specification & Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/analyze` | Core multi-agent message/transcript scanner |
| `POST` | `/guardian/notify` | Triggers live emergency alert to Telegram Guardian Bot |
| `POST` | `/rehearsal/start` | Initializes interactive scam call simulation |
| `POST` | `/rehearsal/message` | Exchanges messages with AI simulated scammer |
| `POST` | `/rehearsal/end` | Finalizes simulation and returns Debriefing Scorecard |
| `GET` | `/cases` | Retrieves cryptographic case ledger entries |
| `GET` | `/evidence/{case_id}` | Downloads legal JSON evidence bundle for police |

---

## 6. Key Differentiators & Impact

1. **Breaks the Isolation Loop**: Raksha is the first solution that automatically notifies third-party family members during active coercion.
2. **Action-Oriented Output**: Moves beyond binary "Scam/Safe" labels by auto-generating legal complaints and step-by-step victim advice.
3. **Experiential Citizen Education**: Rehearsal mode converts passive awareness into active psychological resilience.
4. **Law Enforcement Ready**: Cryptographic hash chaining ensures evidence collected from victims is legally admissible.

---

## 7. Conclusion

Raksha provides a 360-degree public safety shield against digital fraud in India. By combining **in-browser prevention (WhatsApp Extension)**, **AI threat reasoning (Gemini 2.5)**, **family escalation (Telegram Bot)**, and **interactive training (Rehearsal)**, Raksha empowers citizens and law enforcement to effectively eliminate the threat of Digital Arrest.

---
*Document Generated for ET AI Hackathon 2.0 Submission.*
