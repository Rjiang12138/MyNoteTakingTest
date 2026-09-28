"""Vercel serverless entry point — single-handler Flask app with Supabase backend."""
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


# ── main handler — routes everything through one entry point ─────────────

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle(path):
    """Single entry point that dispatches to API handlers or serves static files."""
    # For OPTIONS (CORS preflight), return empty 200
    if request.method == 'OPTIONS':
        return '', 200

    # API dispatch
    if path.startswith('api/'):
        return _dispatch_api(path)

    # Static files: serve index.html for SPA routing
    if path and os.path.isfile(os.path.join(STATIC, path)):
        return send_from_directory(STATIC, path)
    return send_from_directory(STATIC, 'index.html')


# ── API router ────────────────────────────────────────────────────────────

def _dispatch_api(path: str):
    """Dispatch /api/... path to the correct handler."""
    # /api/notes
    if path == 'api/notes':
        if request.method == 'GET':
            return _list_notes()
        if request.method == 'POST':
            return _create_note()

    # /api/notes/<id>
    if path.startswith('api/notes/') and path.count('/') == 2:
        try:
            note_id = int(path.split('/')[2])
        except ValueError:
            return jsonify({'error': 'Invalid note ID'}), 400
        if request.method == 'GET':
            return _get_note(note_id)
        if request.method == 'PUT':
            return _update_note(note_id)
        if request.method == 'DELETE':
            return _delete_note(note_id)

    # /api/notes/search
    if path == 'api/notes/search':
        return _search_notes()

    # /api/translate
    if path == 'api/translate':
        return _translate_text()

    # /api/translate/languages
    if path == 'api/translate/languages':
        return _translate_languages()

    # /api/users
    if path == 'api/users':
        return jsonify([])

    return jsonify({'error': 'Not found'}), 404


# ── note handlers ─────────────────────────────────────────────────────────

def _list_notes():
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_supa_headers(),
                     params={'order': 'updated_at.desc'}, timeout=10)
    r.raise_for_status()
    return jsonify(r.json())


def _create_note():
    data = request.json
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Title and content are required'}), 400
    now = datetime.now(timezone.utc).isoformat()
    body = {'title': data['title'], 'content': data['content'],
            'created_at': now, 'updated_at': now}
    r = requests.post(f'{SUPABASE_URL}/rest/v1/notes?select=*', json=body,
                      headers=_supa_headers(), timeout=10)
    r.raise_for_status()
    rows = r.json()
    return jsonify(rows[0]), 201


def _get_note(note_id: int):
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_supa_headers(),
                     params={'id': f'eq.{note_id}'}, timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return jsonify({'error': 'Note not found'}), 404
    return jsonify(rows[0])


def _update_note(note_id: int):
    data = request.json or {}
    body = {'updated_at': datetime.now(timezone.utc).isoformat()}
    if 'title' in data:
        body['title'] = data['title']
    if 'content' in data:
        body['content'] = data['content']
    r = requests.patch(f'{SUPABASE_URL}/rest/v1/notes?id=eq.{note_id}&select=*',
                       json=body, headers=_supa_headers(), timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return jsonify({'error': 'Note not found'}), 404
    return jsonify(rows[0])


def _delete_note(note_id: int):
    r = requests.delete(f'{SUPABASE_URL}/rest/v1/notes?id=eq.{note_id}',
                        headers=_supa_headers(), timeout=10)
    r.raise_for_status()
    return '', 204


def _search_notes():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_supa_headers(),
                     params={'order': 'updated_at.desc'}, timeout=10)
    r.raise_for_status()
    all_notes = r.json()
    ql = q.lower()
    return jsonify([n for n in all_notes
                    if ql in (n.get('title') or '').lower()
                    or ql in (n.get('content') or '').lower()])


# ── translate handlers ────────────────────────────────────────────────────

def _translate_text():
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
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                     'Content-Type': 'application/json'},
            json={
                'model': 'deepseek/deepseek-chat',
                'messages': [
                    {'role': 'system',
                     'content': f'Translate to {lang}. Return only translation, no notes.'},
                    {'role': 'user', 'content': text},
                ],
                'temperature': 0.3, 'max_tokens': 4096,
            },
            timeout=10,
        )
        r.raise_for_status()
        translated = r.json()['choices'][0]['message']['content'].strip()
        return jsonify({'translated_text': translated, 'target_lang': target,
                        'target_lang_name': lang})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Translation timed out'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Translation error: {e}'}), 502
    except (KeyError, IndexError):
        return jsonify({'error': 'Bad response from translation service'}), 502


def _translate_languages():
    return jsonify([{'code': c, 'name': n} for c, n in LANGUAGES.items()])