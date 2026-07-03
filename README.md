# Raksha 🛡️ — Digital Arrest Scam Detector + Citizen Fraud Shield

> **ET AI Hackathon 2.0 · Problem Statement 6 (Digital Public Safety)**

A multilingual web assistant where a citizen pastes a suspicious message or call transcript and instantly gets:
- A verdict (**SCAM / SAFE / UNCERTAIN**)
- Plain-language guidance in their language
- An auto-drafted cyber-crime complaint (1930 / cybercrime.gov.in)
- A logged, exportable evidence package

Built as an **orchestrated multi-agent system** with a focus on **very low false-positive rate**.

---

## Quick Start

### 1. Prerequisites
- **Python 3.10+**
- A **Gemini API key** ([Get one here](https://aistudio.google.com/app/apikey))

### 2. Setup

```bash
# Clone and enter the project
cd raksha

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure your API key
cp backend/.env.example backend/.env
# Edit backend/.env and add your GEMINI_API_KEY
```

### 3. Run the Server

```bash
# From the raksha/ root directory
uvicorn backend.app.main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

---

## Usage

### Citizen Fraud Shield (Chat UI)
1. Go to **http://localhost:8000** → Shield page
2. Paste a suspicious message, call transcript, or SMS
3. Optionally add case details (amount, phone, platform)
4. Click **Analyze Message**
5. Review the verdict, guidance, complaint draft, and download the evidence package

### Evaluation Dashboard
1. Generate test data: `python -m backend.app.eval.generate_data`
2. Run evaluation: `python -m backend.app.eval.run_eval`
3. Go to **http://localhost:8000/EvalDashboard.html** to see metrics

### Case Log
- View all analyzed cases at **http://localhost:8000/CaseLog.html**
- Download evidence packages for any case

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Frontend (HTML+CSS+JS)              │
│   Chat Shield │ Eval Dashboard │ Case Log        │
└──────────────────┬──────────────────────────────┘
                   │ POST /analyze
┌──────────────────▼──────────────────────────────┐
│            Orchestrator (FastAPI)                 │
│   Language Detect → Route → Fuse → Log           │
└──────┬──────┬──────┬──────┬─────────────────────┘
       │      │      │      │
  Classifier Guidance Complaint Alert
       │      │      │      │
       └──────┴──────┴──────┘
              │
         LLM Wrapper (Gemini)
```

**Agents:**
- **Scam Classifier** — Classifies with low-FPR priority (SCAM needs ≥0.80 confidence + 2 signals)
- **Guidance** — Calm, empowering advice tailored to scam type
- **Complaint Drafter** — Factual complaint for cybercrime.gov.in
- **Authority Alert** — Structured alert for MHA/I4C

**Data Layer:**
- SQLite audit trail for legal admissibility
- Synthetic dataset + evaluation harness

---

## API Endpoints

| Method | Path | Description |
|:--|:--|:--|
| `POST` | `/analyze` | Analyze a suspicious message |
| `GET` | `/metrics` | Evaluation metrics (precision, recall, F1, FPR) |
| `GET` | `/cases` | List all cases |
| `GET` | `/cases/{id}` | Get case details |
| `GET` | `/evidence/{id}` | Download evidence package |
| `GET` | `/health` | Health check |

---

## Supported Languages
- 🇬🇧 English
- 🇮🇳 Hindi
- 🇮🇳 Telugu
- 🇮🇳 Kannada

---

## Scam Types Detected
- **Digital Arrest** — Fake CBI/ED/Police "digital arrest" calls
- **Courier/Parcel** — Fake FedEx/DHL "parcel seized" scams
- **KYC/Bank** — Fake KYC update with OTP/credential requests
- **Loan App** — Predatory instant-loan scams
- **Lottery/Prize** — Fake KBC/lottery winnings
- **Investment/Job** — Fake trading/work-from-home task scams
- **Other Fraud** — Phishing, impersonation, refund scams

---

## Team
ET AI Hackathon 2.0 — Problem Statement 6 (Digital Public Safety)

## License
This project is for hackathon evaluation purposes.
