"""Vercel serverless entry point — Flask app with Supabase backend."""
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
CORS(app)


# ── Supabase helpers ──────────────────────────────────────────────────────

def _su():
    return {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
    }


# ── API: notes ────────────────────────────────────────────────────────────

@app.route('/api/notes', methods=['GET'])
def api_notes_list():
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_su(),
                     params={'order': 'updated_at.desc'}, timeout=10)
    r.raise_for_status()
    return jsonify(r.json())


@app.route('/api/notes', methods=['POST'])
def api_notes_create():
    d = request.json
    if not d or 'title' not in d or 'content' not in d:
        return jsonify({'error': 'Title and content are required'}), 400
    now = datetime.now(timezone.utc).isoformat()
    body = {'title': d['title'], 'content': d['content'],
            'created_at': now, 'updated_at': now}
    r = requests.post(f'{SUPABASE_URL}/rest/v1/notes?select=*', json=body,
                      headers=_su(), timeout=10)
    r.raise_for_status()
    return jsonify(r.json()[0]), 201


@app.route('/api/notes/search', methods=['GET'])
def api_notes_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_su(),
                     params={'order': 'updated_at.desc'}, timeout=10)
    r.raise_for_status()
    ql = q.lower()
    return jsonify([n for n in r.json()
                    if ql in (n.get('title') or '').lower()
                    or ql in (n.get('content') or '').lower()])


@app.route('/api/notes/<int:note_id>', methods=['GET'])
def api_notes_get(note_id):
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_su(),
                     params={'id': f'eq.{note_id}'}, timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(rows[0])


@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def api_notes_update(note_id):
    d = request.json or {}
    body = {'updated_at': datetime.now(timezone.utc).isoformat()}
    if 'title' in d:
        body['title'] = d['title']
    if 'content' in d:
        body['content'] = d['content']
    r = requests.patch(f'{SUPABASE_URL}/rest/v1/notes?id=eq.{note_id}&select=*',
                       json=body, headers=_su(), timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(rows[0])


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def api_notes_delete(note_id):
    r = requests.delete(f'{SUPABASE_URL}/rest/v1/notes?id=eq.{note_id}',
                        headers=_su(), timeout=10)
    r.raise_for_status()
    return '', 204


# ── API: translate ────────────────────────────────────────────────────────

@app.route('/api/translate', methods=['POST'])
def api_translate():
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY not set'}), 500
    d = request.json
    if not d:
        return jsonify({'error': 'Body required'}), 400
    text = d.get('text', '').strip()
    target = d.get('target_lang', 'en').strip()
    if not text:
        return jsonify({'error': 'Text required'}), 400
    if target not in LANGUAGES:
        return jsonify({'error': f'Unsupported: {target}'}), 400
    ln = LANGUAGES[target]
    try:
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                     'Content-Type': 'application/json'},
            json={
                'model': 'deepseek/deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': f'Translate to {ln}. Only translation.'},
                    {'role': 'user', 'content': text},
                ],
                'temperature': 0.3, 'max_tokens': 4096,
            },
            timeout=10,
        )
        r.raise_for_status()
        result = r.json()['choices'][0]['message']['content'].strip()
        return jsonify({'translated_text': result, 'target_lang': target,
                        'target_lang_name': ln})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Timeout'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 502
    except (KeyError, IndexError):
        return jsonify({'error': 'Bad response'}), 502


@app.route('/api/translate/languages', methods=['GET'])
def api_translate_langs():
    return jsonify([{'code': c, 'name': n} for c, n in LANGUAGES.items()])


# ── API: users (stub) ─────────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def api_users():
    return jsonify([])


# ── static & SPA fallback (must be LAST) ──────────────────────────────────

@app.route('/<path:path>')
def serve_static(path):
    filepath = os.path.join(STATIC, path)
    # Security: prevent directory traversal
    if '..' in path or not os.path.abspath(filepath).startswith(os.path.abspath(STATIC)):
        return send_from_directory(STATIC, 'index.html')
    if os.path.isfile(filepath):
        return send_from_directory(STATIC, path)
    return send_from_directory(STATIC, 'index.html')


@app.route('/')
def serve_index():
    return send_from_directory(STATIC, 'index.html')