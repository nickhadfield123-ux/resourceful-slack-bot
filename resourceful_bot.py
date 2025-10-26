import os
import json
import requests
from flask import Flask
from threading import Thread
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ============================================
# CONFIGURATION
# ============================================

GUMLOOP_WEBHOOK = os.environ.get("GUMLOOP_WEBHOOK_URL")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

# Channel mapping
CHANNELS = {
    "C09NEFLB30C": "vision-agent",
    "C09NEFNNXD2": "strategy-agent",
    "C09NAV7HT26": "testing-agent",
    "C09PA0D1ED6": "matching-agent",
    "C09NA0DUTRC": "scheduler-agent",
    "C09PGG5L7AL": "nick-clarity",
    "C09N6NVDWKH": "jordan-clarity"
}

# ============================================
# HEALTH CHECK SERVER (for Render)
# ============================================

flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return json.dumps({"status": "healthy", "bot": "running"}), 200

def run_health_server():
    flask_app.run(host='0.0.0.0', port=PORT)

# ============================================
# INITIALIZE SLACK APP
# ============================================

app = App(token=SLACK_BOT_TOKEN)

# ============================================
# MESSAGE HANDLER
# ============================================

@app.event("message")
def handle_message(event, say, logger):
    """
    Handles all messages in the configured channels.
    Forwards to Gumloop, returns AI response.
    """
    
    # Ignore bot messages (prevent loops!)
    if event.get("bot_id"):
        return
    
    channel_id = event.get("channel")
    message_text = event.get("text", "")
    
    # Only process messages from our 7 channels
    if channel_id not in CHANNELS:
        return
    
    channel_name = CHANNELS[channel_id]
    logger.info(f"Message in #{channel_name}: {message_text[:50]}...")
    
    # Add "thinking" reaction
    try:
        app.client.reactions_add(
            channel=channel_id,
            timestamp=event["ts"],
            name="hourglass_flowing_sand"
        )
    except Exception as e:
        logger.error(f"Could not add reaction: {e}")
    
    # Call Gumloop webhook
    try:
        payload = {
            "channel_id": channel_id,
            "message_text": message_text
        }
        
        response = requests.post(
            GUMLOOP_WEBHOOK,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            ai_response = data.get("response", "Sorry, no response from AI.")
            
            # Post AI response to Slack
            say(ai_response)
            
            # Replace hourglass with checkmark
            try:
                app.client.reactions_remove(
                    channel=channel_id,
                    timestamp=event["ts"],
                    name="hourglass_flowing_sand"
                )
                app.client.reactions_add(
                    channel=channel_id,
                    timestamp=event["ts"],
                    name="white_check_mark"
                )
            except:
                pass
            
            logger.info(f"✅ Response sent to #{channel_name}")
        else:
            say(f"⚠️ Gumloop returned error: {response.status_code}")
            logger.error(f"Gumloop error: {response.text}")
    
    except requests.exceptions.Timeout:
        say("⏰ Request timed out - Gumloop took too long. Try again?")
        logger.error("Gumloop timeout")
    
    except Exception as e:
        say(f"❌ Error connecting to AI: {str(e)}")
        logger.error(f"Exception: {e}")

# ============================================
# START THE APP
# ============================================

if __name__ == "__main__":
    print("🚀 Resourceful AI Suite Bot starting...")
    print(f"📡 Listening to {len(CHANNELS)} channels")
    print(f"🔗 Forwarding to: {GUMLOOP_WEBHOOK[:50] if GUMLOOP_WEBHOOK else 'NOT SET'}...")
    
    # Start health check server in background thread
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print(f"💚 Health check server on port {PORT}")
    
    # Start Slack bot
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
