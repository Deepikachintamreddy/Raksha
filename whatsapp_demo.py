# whatsapp_demo.py
# ---------------------------------------------------------
# Proof of Concept: WhatsApp Integration for Raksha
# ---------------------------------------------------------
# This is exactly what you would show a judge to prove that 
# your backend is modular and works on WhatsApp!

from fastapi import FastAPI, Form, Response
import httpx
import uvicorn

# We would pip install twilio for this to work in production
try:
    from twilio.twiml.messaging_response import MessagingResponse
except ImportError:
    print("Run: pip install twilio httpx")

app = FastAPI(title="Raksha WhatsApp Bot")

RAKSHA_BACKEND_URL = "http://localhost:8000/analyze"

@app.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...), From: str = Form(...)):
    """
    Twilio (WhatsApp) calls this endpoint whenever a citizen sends a message.
    Body = The text message the citizen forwarded (e.g. "I got a call from CBI...")
    From = The citizen's phone number
    """
    
    # 1. Send the WhatsApp text to our existing Raksha Backend!
    # Notice how we don't write any AI code here. We just reuse our powerful API.
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                RAKSHA_BACKEND_URL,
                json={"text": Body} # The exact same contract our frontend website uses
            )
            
            if response.status_code == 200:
                analysis = response.json()
                verdict = analysis["verdict"]
                reply_text = analysis["reply_text"]
                
                # Format a nice WhatsApp message based on the verdict
                if verdict == "SCAM":
                    whatsapp_reply = f"🚨 *RAKSHA ALERT: SCAM DETECTED* 🚨\n\n{reply_text}"
                elif verdict == "SAFE":
                    whatsapp_reply = f"✅ *SAFE* ✅\n\n{reply_text}"
                else:
                    whatsapp_reply = f"⚠️ *UNCERTAIN* ⚠️\n\n{reply_text}"
                    
            else:
                whatsapp_reply = "Raksha systems are currently offline. Please try again later."
        except Exception:
            whatsapp_reply = "Could not connect to the Raksha Engine."

    # 2. Send the response back to the citizen on WhatsApp
    twiml_response = MessagingResponse()
    twiml_response.message(whatsapp_reply)
    
    # Return XML as required by Twilio
    return Response(content=str(twiml_response), media_type="application/xml")

if __name__ == "__main__":
    print("Starting WhatsApp Bot on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
