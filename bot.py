import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY')
SHEET_URL = 'https://script.google.com/macros/s/AKfycbyZ3q5CP9YUaMZ-5Af95TRiP4eBPSuPPLOdA73Z2ExUY1IW1zbxZsFrUa9OeQpc4R23Kw/exec'
TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'

conversations = {}

SYSTEM_PROMPT = """You are an elite texting coach for men who are dating. You have deep, real-world experience coaching men on exactly what to text women on dating apps (Hinge, Bumble, Tinder) and in real life.

THE 7-STEP TEXTING FRAMEWORK:
1. OPENER - Tailored first, energy opener fallback: "You seem like you have [energy] [name]"
   - DEFAULT FALLBACK: "You seem like you have a great balance between elegant and yet still fun"
   - PROMPT OPENERS: "At least your most irrational fear isn't men..." / "Speaking of emotional maturity..."
   - NATIONALITY: Brazilian=bachata, Romanian=Cluj vs Bucharest, Polish=twarozek, Italian=north/south, Turkish=Fenerbahce or Galatasaray
   - JOB: Account Manager at tech = "How's the upsell quota this quarter haha"
   - NO REPLY after 3+ days: "Serious question: Why are you on hinge?"
2. TRANSITION - "How's your week going?"
3. VALUE SPRINKLE - Brief, social proof
4. PING PONG - one relatable sentence
5. SOFT CLOSE - "Let's meet for drinks one of these days?"
6. HARD CLOSE - "Cool, Thursday 7pm?"
7. MOVE TO IG

RULES:
- NEVER use em dashes in suggested texts
- Max 2 "I"s per message
- One compliment max then move
- Always acknowledge before pivoting
- Give exact words in quotes
- No "fascinating", "intriguing", "certainly"
- Be direct and concise — this is Telegram, keep responses tight

You are the guy who's seen it all — no judgment, just results."""

def send_message(chat_id, text):
    url = f'{TELEGRAM_API}/sendMessage'
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            requests.post(url, json={'chat_id': chat_id, 'text': chunk, 'parse_mode': 'Markdown'})
    else:
        requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})

def send_typing(chat_id):
    requests.post(f'{TELEGRAM_API}/sendChatAction', json={'chat_id': chat_id, 'action': 'typing'})

def ask_claude(chat_id, user_message):
    if chat_id not in conversations:
        conversations[chat_id] = []
    conversations[chat_id].append({'role': 'user', 'content': user_message})
    history = conversations[chat_id][-20:]
    response = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        },
        json={
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 1024,
            'system': SYSTEM_PROMPT,
            'messages': history
        }
    )
    data = response.json()
    reply = data['content'][0]['text']
    conversations[chat_id].append({'role': 'assistant', 'content': reply})
    return reply

def log_to_sheet(session, role, message, stage='telegram'):
    try:
        requests.post(SHEET_URL, json={
            'session': str(session),
            'role': role,
            'message': message[:1000],
            'stage': stage
        }, timeout=5)
    except:
        pass

@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = request.json
    if 'message' not in update:
        return 'ok'
    message = update['message']
    chat_id = message['chat']['id']
    username = message.get('from', {}).get('username', str(chat_id))

    if 'text' in message and message['text'] == '/start':
        send_message(chat_id, "🎯 *Texting Coach AI*\n\nTrained on real coaching calls. Tell me your situation and I'll tell you exactly what to send.\n\n*Try:*\n• Paste her last message\n• Describe where you're at\n• Ask about openers, closing, no replies\n\nJust type and let's go.")
        return 'ok'

    if 'text' in message and message['text'] == '/reset':
        conversations[chat_id] = []
        send_message(chat_id, "✓ Fresh start — what's the situation?")
        return 'ok'

    if 'text' in message:
        send_typing(chat_id)
        user_text = message['text']
        log_to_sheet(f'tg-{username}', 'user', user_text)
        try:
            reply = ask_claude(chat_id, user_text)
            log_to_sheet(f'tg-{username}', 'assistant', reply)
            send_message(chat_id, reply)
        except Exception as e:
            send_message(chat_id, "Something went wrong. Try again.")
    elif 'photo' in message:
        send_message(chat_id, "📸 I can't analyze images in Telegram — describe her profile and I'll write the opener.")
    
    return 'ok'

# ── LOGGING ENDPOINT (for web app) ────────────────────────────────────────────
@app.route('/log', methods=['POST', 'OPTIONS'])
def log_endpoint():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        return response
    try:
        data = request.json
        log_to_sheet(data.get('session'), data.get('role'), data.get('message'), data.get('stage'))
        response = app.response_class(response='ok', status=200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except:
        return 'ok', 200

@app.route('/')
def index():
    return 'Texting Coach Bot is running.'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
