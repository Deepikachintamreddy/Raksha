# Raksha — Synthetic Data Generator
# Build-time script: generates labeled test data for evaluation.
# Usage: python -m backend.app.eval.generate_data

from __future__ import annotations
import json
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.llm.wrapper import get_llm


DATA_DIR = Path(__file__).parent.parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "synthetic_dataset.json"
TEST_SET_PATH = DATA_DIR / "test_set.json"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "data_generator.txt"

# We also include a hand-crafted seed set of reliable test cases
SEED_DATA = [
    # ── SAFE examples (the FPR battleground) ──
    {
        "text": "Your OTP for SBI Net Banking login is 847293. Do NOT share this OTP with anyone. OTP is valid for 5 minutes. -SBI",
        "language": "en", "channel": "sms", "label": "SAFE", "scam_type": None
    },
    {
        "text": "Dear Customer, Rs.1,500.00 has been debited from your A/c XX4523 on 01-Jul-26. UPI Ref No: 423156789012. If not done by you, call 1800-XXX-XXXX. -HDFC Bank",
        "language": "en", "channel": "sms", "label": "SAFE", "scam_type": None
    },
    {
        "text": "Your Amazon order #402-1234567 has been shipped. Track: https://www.amazon.in/tracking/402-1234567. Expected delivery: 3 Jul.",
        "language": "en", "channel": "sms", "label": "SAFE", "scam_type": None
    },
    {
        "text": "Aapka PhonePe UPI transaction Rs.250.00 safal raha. UPI Ref: 426187654321. Yadi aapne yeh nahi kiya, toh turant helpline par call karein.",
        "language": "hi", "channel": "sms", "label": "SAFE", "scam_type": None
    },
    {
        "text": "Reminder: Your ICICI Bank credit card payment of Rs.12,450 is due on 05-Jul-2026. Pay via ICICI iMobile or nearest branch. Ignore if paid.",
        "language": "en", "channel": "sms", "label": "SAFE", "scam_type": None
    },
    {
        "text": "Your Swiggy order is out for delivery! Delivery partner Rajesh is on the way. Track live on the Swiggy app.",
        "language": "en", "channel": "sms", "label": "SAFE", "scam_type": None
    },
    # ── SCAM examples ──
    {
        "text": "This is Senior Inspector Sharma from Mumbai Cyber Crime Cell. Your Aadhaar number is linked to a money laundering case worth 48 crores. You are under digital arrest. Do NOT disconnect this call. Transfer Rs.2,50,000 to the RBI verification account immediately or an arrest warrant will be issued in your name within 1 hour. This is highly confidential - do not tell anyone.",
        "language": "en", "channel": "call", "label": "SCAM", "scam_type": "digital_arrest"
    },
    {
        "text": "Yeh CBI ka Senior Officer Verma bol raha hun. Aapke naam par ek parcel mein 5 fake passport aur drugs mili hain. Aap digital arrest mein hain. Video call se disconnect mat kijiye. Apni pehchaan verify karne ke liye Rs.3,00,000 is account mein transfer kijiye. Yeh case gupat hai - kisiko mat batana.",
        "language": "hi", "channel": "call", "label": "SCAM", "scam_type": "digital_arrest"
    },
    {
        "text": "URGENT: Your FedEx parcel #FX9847261 has been seized by Customs as it contains illegal items. Your case has been forwarded to the Narcotics Department. To avoid arrest, pay the fine of Rs.1,85,000 immediately. Contact Officer: +91-90000-XXXXX",
        "language": "en", "channel": "whatsapp", "label": "SCAM", "scam_type": "courier_parcel"
    },
    {
        "text": "Dear customer, your SBI account will be BLOCKED within 24 hours due to incomplete KYC. Click this link to update now: http://sbi-kyc-update.xyz/verify. Share your OTP to complete verification.",
        "language": "en", "channel": "sms", "label": "SCAM", "scam_type": "kyc_bank"
    },
    {
        "text": "Congratulations! You have won Rs.25,00,000 in the KBC Lucky Draw Season 15! To claim, pay processing fee of Rs.9,999 to Paytm number 90000-XXXXX. Offer valid 24 hours only.",
        "language": "en", "channel": "whatsapp", "label": "SCAM", "scam_type": "lottery_prize"
    },
    {
        "text": "EARN Rs.50,000/day from home! Simple tasks - like YouTube videos, rate products. Start with deposit of Rs.500 only. Join now: wa.me/+91-90000XXXXX. 100% guaranteed returns!",
        "language": "en", "channel": "whatsapp", "label": "SCAM", "scam_type": "investment_job"
    },
    {
        "text": "Instant loan approved! Rs.5,00,000 sanctioned in your name. Download our app to receive funds. Processing fee Rs.2,999 required. Your Aadhaar & PAN needed for verification. Send to +91-90000-XXXXX.",
        "language": "en", "channel": "sms", "label": "SCAM", "scam_type": "loan_app"
    },
    # ── UNCERTAIN examples ──
    {
        "text": "Your account needs attention. Please verify your details at your earliest convenience. Click here for more information.",
        "language": "en", "channel": "sms", "label": "UNCERTAIN", "scam_type": None
    },
    {
        "text": "Important: We noticed unusual activity on your account. Please call us at 1800-XXX-XXXX to verify recent transactions.",
        "language": "en", "channel": "sms", "label": "UNCERTAIN", "scam_type": None
    },
]


async def generate_synthetic_data(batch_size: int = 30, num_batches: int = 3) -> list[dict]:
    """Generate synthetic data using the LLM and combine with seed data."""
    llm = get_llm()
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    all_data = list(SEED_DATA)  # Start with seed data
    print(f"Starting with {len(SEED_DATA)} seed examples.")

    for i in range(num_batches):
        print(f"Generating batch {i + 1}/{num_batches} ({batch_size} examples)...")
        try:
            user_message = (
                f"Generate exactly {batch_size} examples as a JSON array. "
                f"Include a good mix of:\n"
                f"- SCAM examples across ALL types (digital_arrest, courier_parcel, kyc_bank, "
                f"loan_app, lottery_prize, investment_job, other_fraud)\n"
                f"- SAFE examples that look risky but are legitimate (bank OTPs, delivery updates, "
                f"UPI alerts, KYC reminders)\n"
                f"- A few UNCERTAIN examples\n"
                f"- Mix of English, Hindi, Hinglish, and a couple Telugu/Kannada\n"
                f"- Vary the channel (sms, whatsapp, call)\n"
                f"Batch {i + 1} of {num_batches} — vary the style from previous batches."
            )

            raw = await llm.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0.8,  # Higher temperature for diversity
                max_tokens=8192,
            )

            # Extract JSON array
            import re
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                batch = json.loads(json_match.group())
                # Validate and clean
                valid = []
                for item in batch:
                    if isinstance(item, dict) and "text" in item and "label" in item:
                        item.setdefault("language", "en")
                        item.setdefault("channel", "sms")
                        item.setdefault("scam_type", None)
                        if item["label"] in ("SCAM", "SAFE", "UNCERTAIN"):
                            valid.append(item)
                all_data.extend(valid)
                print(f"  ✓ Got {len(valid)} valid examples from batch {i + 1}.")
            else:
                print(f"  ✗ Could not parse JSON from batch {i + 1}.")

        except Exception as e:
            print(f"  ✗ Batch {i + 1} failed: {e}")

    return all_data


def split_dataset(data: list[dict], test_ratio: float = 0.3) -> tuple[list, list]:
    """Split into train (few-shot) and held-out test set."""
    import random
    random.seed(42)
    shuffled = list(data)
    random.shuffle(shuffled)

    split_idx = int(len(shuffled) * (1 - test_ratio))
    train = shuffled[:split_idx]
    test = shuffled[split_idx:]
    return train, test


async def main():
    print("=" * 60)
    print("Raksha — Synthetic Data Generator")
    print("=" * 60)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Generate data
    all_data = await generate_synthetic_data(batch_size=30, num_batches=3)

    print(f"\nTotal examples: {len(all_data)}")

    # Count by label
    label_counts = {}
    for item in all_data:
        label = item["label"]
        label_counts[label] = label_counts.get(label, 0) + 1
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")

    # Save full dataset
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    print(f"\nFull dataset saved: {OUTPUT_PATH}")

    # Split and save test set
    train, test = split_dataset(all_data)
    with open(TEST_SET_PATH, "w", encoding="utf-8") as f:
        json.dump(test, f, indent=2, ensure_ascii=False)
    print(f"Test set saved: {TEST_SET_PATH} ({len(test)} examples)")
    print(f"Train set: {len(train)} examples (for few-shot / prompt tuning)")

    print("\n✓ Done. Next: run `python -m backend.app.eval.run_eval` to evaluate.")


if __name__ == "__main__":
    asyncio.run(main())
