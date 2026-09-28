"""Vercel serverless entry point — single-file Flask app with Supabase backend."""
import os
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# ── config ────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')

LANGUAGES = {
    'zh': 'Chinese', 'en': 'English', 'ja': 'Japanese', 'ko': 'Korean',
    'fr': 'French', 'de': 'German', 'es': 'Spanish', 'pt': 'Portuguese',
    'ru': 'Russian', 'ar': 'Arabic', 'th': 'Thai', 'vi': 'Vietnamese',
}

STATIC = os.path.join(os.path.dirname(__file__), '..', 'src', 'static')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'note-app-secret')
CORS(app)


# ── Supabase helpers ──────────────────────────────────────────────────────

def _supa_headers():
    return {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
    }


# ── API: notes ────────────────────────────────────────────────────────────

@app.route('/api/notes', methods=['GET'])
def list_notes():
    resp = requests.get(
        f'{SUPABASE_URL}/rest/v1/notes',
        headers=_supa_headers(),
        params={'order': 'updated_at.desc'},
        timeout=10,
    )
    resp.raise_for_status()
    return jsonify(resp.json())


@app.route('/api/notes', methods=['POST'])
def create_note():
    data = request.json
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Title and content are required'}), 400
    now = datetime.now(timezone.utc).isoformat()
    body = {'title': data['title'], 'content': data['content'],
            'created_at': now, 'updated_at': now}
    resp = requests.post(
        f'{SUPABASE_URL}/rest/v1/notes?select=*',
        json=body,
        headers=_supa_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return jsonify(rows[0]), 201


@app.route('/api/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    resp = requests.get(
        f'{SUPABASE_URL}/rest/v1/notes',
        headers=_supa_headers(),
        params={'id': f'eq.{note_id}'},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return jsonify({'error': 'Note not found'}), 404
    return jsonify(rows[0])


@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    data = request.json or {}
    body = {'updated_at': datetime.now(timezone.utc).isoformat()}
    if 'title' in data:
        body['title'] = data['title']
    if 'content' in data:
        body['content'] = data['content']
    resp = requests.patch(
        f'{SUPABASE_URL}/rest/v1/notes?id=eq.{note_id}&select=*',
        json=body,
        headers=_supa_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return jsonify({'error': 'Note not found'}), 404
    return jsonify(rows[0])


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    resp = requests.delete(
        f'{SUPABASE_URL}/rest/v1/notes?id=eq.{note_id}',
        headers=_supa_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return '', 204


@app.route('/api/notes/search', methods=['GET'])
def search_notes():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    # client-side search fallback: load all and filter
    resp = requests.get(
        f'{SUPABASE_URL}/rest/v1/notes',
        headers=_supa_headers(),
        params={'order': 'updated_at.desc'},
        timeout=10,
    )
    resp.raise_for_status()
    all_notes = resp.json()
    ql = q.lower()
    filtered = [n for n in all_notes
                if ql in (n.get('title') or '').lower()
                or ql in (n.get('content') or '').lower()]
    return jsonify(filtered)


# ── API: translate ────────────────────────────────────────────────────────

@app.route('/api/translate', methods=['POST'])
def translate_text():
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY not set'}), 500
    data = request.json
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    text = data.get('text', '').strip()
    target = data.get('target_lang', 'en').strip()
    if not text:
        return jsonify({'error': 'Text required'}), 400
    if target not in LANGUAGES:
        return jsonify({'error': f'Unsupported language: {target}'}), 400
    lang = LANGUAGES[target]
    try:
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'deepseek/deepseek-chat',
                'messages': [
                    {'role': 'system',
                     'content': f'Translate to {lang}. Return only the translation, no notes.'},
                    {'role': 'user', 'content': text},
                ],
                'temperature': 0.3,
                'max_tokens': 4096,
            },
            timeout=10,
        )
        resp.raise_for_status()
        translated = resp.json()['choices'][0]['message']['content'].strip()
        return jsonify({'translated_text': translated, 'target_lang': target,
                        'target_lang_name': lang})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Translation timed out'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Translation error: {e}'}), 502
    except (KeyError, IndexError) as e:
        return jsonify({'error': f'Bad response: {e}'}), 502


@app.route('/api/translate/languages', methods=['GET'])
def translate_languages():
    return jsonify([{'code': c, 'name': n} for c, n in LANGUAGES.items()])


# ── API: users (stub) ─────────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def list_users():
    return jsonify([])


# ── static files & SPA fallback ───────────────────────────────────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if path and os.path.isfile(os.path.join(STATIC, path)):
        return send_from_directory(STATIC, path)
    return send_from_directory(STATIC, 'index.html')