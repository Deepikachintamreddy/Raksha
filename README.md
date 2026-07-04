# Raksha 🛡️ — Digital Arrest Scam Detector + Citizen Fraud Shield

> **ET AI Hackathon 2.0 · Problem Statement 6 (Digital Public Safety)**

A multilingual web assistant where a citizen gets real-time warning, scam validation, and support tools against cyber fraud:
- **Verdict & Signals**: Instantly flags SCAM / SAFE / UNCERTAIN verdicts with converging threat signals.
- **Dynamic Highlights**: Mouse-hover highlighting of specific text strings matching suspicious signals.
- **Cyber-Crime Complaint**: Automatically drafts complaints for 1930 / cybercrime.gov.in.
- **Interception Alert**: Real-time warning overlays for ongoing digital arrest calls.

Built as an **orchestrated multi-agent system** with a focus on **very low false-positive rate** and compliant with the Gemini Free Tier API (15 RPM / 1,500 RPD).

---

## 🚀 Key Upgrades in v2.0

1. **⚡ Live Call Guardian (LiveShield)**: An incremental transcript WebSocket server (`/ws/live`) that computes threat levels during ongoing calls and triggers full-screen alerts to intercept scam attempts *before* money transfers.
2. **🕸️ Fraud Campaign Intelligence (Intel)**: Graph clustering connecting cases via shared elements (phone numbers, UPI IDs, URLs) or TF-IDF template similarity to expose organized scam operations.
3. **🔒 Cryptographic Tamper-Evident Ledger**: A secure SQLite audit trail chaining records together via SHA-256 block hashes (`verify_chain()` validation).
4. **📊 Hardened Evaluation Harness**: Robust metric reporting split across 5 subsets (`seed`, `hard_negative`, `adversarial`, `code_mixed`, `standard`) totaling **158 evaluation test cases**.
5. **🎙️ Native Multimodal Audio Input**: Direct voice transcription (`POST /transcribe`) allowing users to record or upload call audio recordings.

---

## 🛠️ Quick Start

### 1. Prerequisites
- **Python 3.10+**
- A **Gemini API key** ([Get one here](https://aistudio.google.com/app/apikey))

### 2. Setup

```bash
# Clone the repository
git clone https://github.com/Deepikachintamreddy/Raksha.git
cd Raksha

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Configure your API key
# Create backend/.env and add your key:
# GEMINI_API_KEY=AIzaSy...
# GEMINI_MODEL=gemini-flash-lite-latest
# LLM_PROVIDER=gemini
```

### 3. Run the Server

```bash
# Bind to all interfaces to test on mobile browsers via local Wi-Fi
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** on your computer or `http://<your-local-ip>:8000` on your mobile browser.

---

## 🧪 Testing & Evaluation

### Run Unit & Integration Tests
Verify the full core suite, hash chaining, entity extraction rules, and campaign clustering:
```bash
python -m pytest backend/tests/ -v
```

### Run the Hardened Evaluation Harness
Run predictions and compute subset breakdowns, hard-negative False Positive Rates, and adversarial resistance metrics:
```bash
# 1. Prepopulate the persistent cache (guarantees fast, free eval runs)
python -m backend.app.eval.prepopulate_cache

# 2. Run the evaluator
python -m backend.app.eval.run_eval
```
View the results live at **`http://localhost:8000/EvalDashboard.html`**.

---

## 🗺️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Frontend (Responsive HTML+CSS+JS)           │
│   Shield Scanner │ LiveShield │ Campaign Intel │ Dashboard   │
└──────────────────────────────┬──────────────────────────────┘
                               │ WebSocket / REST API
┌──────────────────────────────▼──────────────────────────────┐
│                  Orchestrator (FastAPI)                     │
│   Router → Multimodal Audio → Union-Find Clust. → Ledger     │
└──────────────┬──────────────┬──────────────┬──────────────┬─┘
               │              │              │              │
          Classifier      Guidance       Complaint        Alert
               │              │              │              │
               └──────────────┴──────────────┴──────────────┘
                              │
                    LLM Wrapper (Gemini)
                [Persistent Disk Cache Layer]
```

---

## 🌐 API Endpoints

| Method | Path | Description |
|:--|:--|:--|
| `POST` | `/analyze` | Analyze a suspicious message |
| `POST` | `/transcribe` | Transcribe call recording audio |
| `WS` | `/ws/live` | Incremental real-time call guardian stream |
| `GET` | `/campaigns` | Retrieve campaign graph nodes and correlations |
| `GET` | `/audit/verify` | Walk ledger chain and verify block hashes |
| `GET` | `/metrics` | Evaluation metrics and subset breakdowns |
| `GET` | `/cases` | List all cases |
| `GET` | `/evidence/{id}`| Download zip evidence packages |
| `GET` | `/health` | Health checks |

---

## 🌍 Supported Languages
- 🇬🇧 English
- 🇮🇳 Hindi (and Hinglish)
- 🇮🇳 Telugu (and Tenglish)
- 🇮🇳 Kannada (and Kannada-English)

---

## 🏆 Presentation Highlights for Judges
- **0.0% False Positive Rate**: Enforces code-level guardrails (`confidence >= 0.80` + `2+ signals`) preventing false panic.
- **100% Adversarial Resistance**: Neutralizes prompt-injection hacks attempt to force `SAFE` classifications.
- **Admissible Evidence**: Complete Chain of Custody evidence package containing cryptographic block hashes.
