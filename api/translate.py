"""API handler for /api/translate"""
import os
import requests
from flask import Flask, jsonify, request

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')

LANGUAGES = {
    'zh': 'Chinese', 'en': 'English', 'ja': 'Japanese', 'ko': 'Korean',
    'fr': 'French', 'de': 'German', 'es': 'Spanish', 'pt': 'Portuguese',
    'ru': 'Russian', 'ar': 'Arabic', 'th': 'Thai', 'vi': 'Vietnamese',
}

app = Flask(__name__)

@app.route('/api/translate', methods=['POST'])
def translate():
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'API key not set'}), 500
    d = request.json
    if not d: return jsonify({'error': 'Body required'}), 400
    text = d.get('text', '').strip()
    target = d.get('target_lang', 'en').strip()
    if not text: return jsonify({'error': 'Text required'}), 400
    if target not in LANGUAGES: return jsonify({'error': f'Unsupported: {target}'}), 400
    ln = LANGUAGES[target]
    try:
        r = requests.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': 'deepseek/deepseek-chat',
                  'messages': [{'role': 'system', 'content': f'Translate to {ln}. Only translation.'},
                               {'role': 'user', 'content': text}],
                  'temperature': 0.3, 'max_tokens': 4096},
            timeout=10)
        r.raise_for_status()
        result = r.json()['choices'][0]['message']['content'].strip()
        return jsonify({'translated_text': result, 'target_lang': target, 'target_lang_name': ln})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Timeout'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 502
    except (KeyError, IndexError):
        return jsonify({'error': 'Bad response'}), 502

@app.route('/api/translate/languages', methods=['GET'])
def langs():
    return jsonify([{'code': c, 'name': n} for c, n in LANGUAGES.items()])