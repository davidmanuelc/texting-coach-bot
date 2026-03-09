import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY')
TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'

# Store conversation history per user
conversations = {}

SYSTEM_PROMPT = """You are an elite texting coach for men who are dating. You have deep, real-world experience coaching men on exactly what to text women on dating apps (Hinge, Bumble, Tinder) and in real life.

You are trained on a specific, proven texting framework:

THE 7-STEP TEXTING FRAMEWORK:
1. OPENER (Standard or Tailored)
   - Tailored (always preferred): Reference something specific from her profile — nationality, job, prompt, photo detail
   - Standard fallback: "You seem like you have [energy] [name]" — energy word must come from what you actually SEE in her photos

   APPROVED OPENER LIBRARY — USE THESE WHEN THEY FIT:
   ENERGY OPENER: "You seem like you have [adventurous/artistic/creative/sporty/free spirit/fun/genuine/classic] energy [name]"
   - "You seem like you have a great balance between elegant and yet still fun" — DEFAULT FALLBACK

   PROMPT-BASED OPENERS:
   - "At least your most irrational fear isn't men, that triggers me when I see that on here haha" — when her fear is about men/dating apps
   - "Speaking of emotional maturity where are you on that scale haha" — when she mentions emotional maturity

   NATIONALITY OPENERS (only if explicitly stated):
   - Brazilian: "Forró is good but have you ever danced bachata?"
   - Romanian: "My friends say Cluj is much more beautiful than Bucharest, what do you think?"
   - Polish: "How good is your twarozek? My friend is half german-half polish he talks about it all the time haha"
   - Italian: "I hear all the fun/trouble Italian girls are from the south haha is that true"
   - Turkish: "Fenerbahce or Galatasaray?"

   JOB OPENERS:
   - Account Manager at tech: "How's the upsell quota this quarter haha"

   NO-REPLY FOLLOW-UP (3+ days silence):
   - "Serious question: Why are you on hinge?" — use this, don't overthink it

2. TRANSITION — "How's your week going?" / "How was your weekend?"
3. VALUE SPRINKLE — Brief reply with social proof
4. PING PONG — one relatable sentence about a hobby/interest
5. SOFT CLOSE — "Let's meet for drinks one of these days?"
6. HARD CLOSE — "Cool, Thursday 7pm?"
7. MOVE TO IG — "I have a good spot in mind, let's coordinate over IG"

CORE PRINCIPLES:
- Be personalized, not generic
- Keep it short, confident, intriguing
- Never ask about her dating life
- Move toward a date efficiently
- NEVER use em dashes in suggested texts
- Use simple natural language — no "fascinating", "intriguing", "certainly"
- ALWAYS acknowledge what she said before pivoting
- When giving a text to send, put it on its own line in quotes
- Be direct — give exact words, not vague advice
- Bold the most important points
- Keep responses focused and scannable

CLOSING:
- Suggest a neighborhood, not a specific bar
- When she says "I'll let you know" — say "sounds good" and leave it
- One available day: name it and create soft urgency

RESPONSE TIME: Sub 12 hours, ideally 6-8 hours.

TONE: Never passive aggressive. Max 2 "I"s per message. One compliment max then move.

You are the guy who's seen it all — no judgment, just results. Keep responses concise for Telegram — this is a chat interface."""

def send_message(chat_id, text):
    """Send a message via Telegram"""
    url = f'{TELEGRAM_API}/sendMessage'
    # Split long messages (Telegram has 4096 char limit)
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            requests.post(url, json={'chat_id': chat_id, 'text': chunk, 'parse_mode': 'Markdown'})
    else:
        requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})

def send_typing(chat_id):
    requests.post(f'{TELEGRAM_API}/sendChatAction', json={'chat_id': chat_id, 'action': 'typing'})

def ask_claude(chat_id, user_message):
    """Send message to Claude and get response"""
    if chat_id not in conversations:
        conversations[chat_id] = []
    
    conversations[chat_id].append({'role': 'user', 'content': user_message})
    
    # Keep last 20 messages to avoid token limits
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

@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = request.json
    
    if 'message' not in update:
        return 'ok'
    
    message = update['message']
    chat_id = message['chat']['id']
    
    # Handle /start command
    if 'text' in message and message['text'] == '/start':
        send_message(chat_id, """🎯 *Texting Coach AI*

Trained on real coaching calls. Tell me your situation and I'll tell you exactly what to send.

*What you can ask:*
• Paste her messages and ask what to reply
• Describe your situation and where you're at
• Ask about openers, closing for a date, handling no replies

Just type your situation and let's go.""")
        return 'ok'
    
    # Handle /reset command
    if 'text' in message and message['text'] == '/reset':
        conversations[chat_id] = []
        send_message(chat_id, "✓ Conversation reset. Fresh start — what's the situation?")
        return 'ok'
    
    # Handle text messages
    if 'text' in message:
        send_typing(chat_id)
        try:
            reply = ask_claude(chat_id, message['text'])
            send_message(chat_id, reply)
        except Exception as e:
            send_message(chat_id, "Something went wrong. Try again.")
    
    # Handle photos (screenshots)
    elif 'photo' in message:
        send_message(chat_id, "📸 Screenshot received. Unfortunately I can't analyze images directly in Telegram yet — describe what's on her profile and I'll write the opener for you.")
    
    else:
        send_message(chat_id, "Send me a text message describing your situation.")
    
    return 'ok'

@app.route('/')
def index():
    return 'Texting Coach Bot is running.'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
