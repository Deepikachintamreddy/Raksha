# Raksha — Telegram Guardian Service (Part B)
# Handles dual-mode delivery (Live web.telegram.org / phone delivery & Browser Preview / Dry-run delivery)

import os
import logging
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger("raksha.services.telegram")

class TelegramGuardianService:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

    def format_alert_message(
        self,
        victim_name: str = "Protected User",
        risk_level: str = "HIGH",
        confidence: float = 0.95,
        scam_type: str = "Digital Arrest (CBI / TRAI)",
        observed_signals: Optional[List[str]] = None,
        case_id: str = "",
        record_hash: str = ""
    ) -> str:
        signals = observed_signals or [
            "Coercive legal threats (CBI / TRAI / Customs impersonation)",
            "Strict video call isolation demand",
            "Urgent payment/security deposit demand to prevent arrest"
        ]
        signals_formatted = "\n".join([f"• {sig}" for sig in signals])
        hash_display = record_hash if record_hash else "0x9f83a21b... (Verified Audit Chain)"
        case_display = case_id if case_id else "CASE-2026-LIVE"

        message = (
            f"🚨 *GUARDIAN ALERT: DIGITAL ARREST SCAM DETECTED*\n\n"
            f"👤 *Protected User*: {victim_name}\n"
            f"⚠️ *Risk Level*: *{risk_level}* (Confidence: {int(confidence * 100)}%)\n"
            f"🎭 *Detected Scam*: {scam_type}\n"
            f"🆔 *Case Ref*: `{case_display}`\n\n"
            f"🔍 *Observed Scam Tactics*:\n{signals_formatted}\n\n"
            f"🔒 *Tamper-Evident Evidence Hash*:\n`{hash_display}`\n\n"
            f"🛡️ *RECOMMENDED GUARDIAN ACTION*:\n"
            f"1. *Call {victim_name} IMMEDIATELY* to break video call isolation.\n"
            f"2. Tell them to *HANG UP* the call right now.\n"
            f"3. Remind them: *No government agency arrests people via WhatsApp/Skype or asks for money.* \n"
            f"4. If payment was made, immediately dial National Helpline *1930*."
        )
        return message

    def send_alert(
        self,
        victim_name: str = "Protected User",
        risk_level: str = "HIGH",
        confidence: float = 0.95,
        scam_type: str = "Digital Arrest (CBI / TRAI)",
        observed_signals: Optional[List[str]] = None,
        case_id: str = "",
        record_hash: str = "",
        override_chat_id: Optional[str] = None,
        override_bot_token: Optional[str] = None
    ) -> Dict[str, Any]:
        token = override_bot_token or self.bot_token
        target_chat = override_chat_id or self.chat_id

        formatted_msg = self.format_alert_message(
            victim_name=victim_name,
            risk_level=risk_level,
            confidence=confidence,
            scam_type=scam_type,
            observed_signals=observed_signals,
            case_id=case_id,
            record_hash=record_hash
        )

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Check if live Telegram credentials are available
        if not token or not target_chat:
            logger.info("Telegram Bot token/chat_id not configured. Returning Browser Preview Mode.")
            return {
                "status": "simulated",
                "delivered": False,
                "mode": "browser_preview",
                "message": formatted_msg,
                "chat_id": target_chat or "simulated_guardian_chat",
                "timestamp": timestamp,
                "note": "Live Telegram Bot credentials not set in backend/.env. Rendered in Browser Preview Mode."
            }

        # Send live message via Telegram Bot API
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": formatted_msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                api_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_body = json.loads(resp.read().decode('utf-8'))
                if resp_body.get("ok"):
                    logger.info("Live Telegram notification delivered successfully.")
                    return {
                        "status": "success",
                        "delivered": True,
                        "mode": "live_telegram",
                        "message": formatted_msg,
                        "chat_id": target_chat,
                        "telegram_message_id": resp_body.get("result", {}).get("message_id"),
                        "timestamp": timestamp
                    }
                else:
                    error_desc = resp_body.get("description", "Unknown Telegram API Error")
                    logger.warning(f"Telegram API returned error: {error_desc}")
                    return {
                        "status": "failed",
                        "delivered": False,
                        "mode": "live_telegram_failed",
                        "message": formatted_msg,
                        "error_details": error_desc,
                        "timestamp": timestamp
                    }
        except urllib.error.HTTPError as e:
            err_text = e.read().decode('utf-8') if e.fp else str(e)
            logger.error(f"Telegram HTTP Error {e.code}: {err_text}")
            return {
                "status": "failed",
                "delivered": False,
                "mode": "live_telegram_failed",
                "message": formatted_msg,
                "error_details": f"HTTP {e.code}: {err_text}",
                "timestamp": timestamp
            }
        except Exception as e:
            logger.error(f"Telegram Delivery Exception: {e}")
            return {
                "status": "failed",
                "delivered": False,
                "mode": "live_telegram_failed",
                "message": formatted_msg,
                "error_details": str(e),
                "timestamp": timestamp
            }

_telegram_service = None

def get_telegram_service() -> TelegramGuardianService:
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramGuardianService()
    return _telegram_service
