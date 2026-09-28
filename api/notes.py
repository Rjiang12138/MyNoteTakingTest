"""API handler for /api/notes and /api/notes/<id>"""
import os
from datetime import datetime, timezone
import requests
from flask import Flask, jsonify, request

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

app = Flask(__name__)

def _su():
    return {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'}

@app.route('/api/notes', methods=['GET'])
def list_all():
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_su(), params={'order': 'updated_at.desc'}, timeout=10)
    r.raise_for_status()
    return jsonify(r.json())

@app.route('/api/notes', methods=['POST'])
def create():
    d = request.json
    if not d or 'title' not in d or 'content' not in d:
        return jsonify({'error': 'Title and content required'}), 400
    now = datetime.now(timezone.utc).isoformat()
    body = {'title': d['title'], 'content': d['content'], 'created_at': now, 'updated_at': now}
    r = requests.post(f'{SUPABASE_URL}/rest/v1/notes?select=*', json=body, headers=_su(), timeout=10)
    r.raise_for_status()
    return jsonify(r.json()[0]), 201

@app.route('/api/notes/search', methods=['GET'])
def search():
    q = request.args.get('q', '').strip()
    if not q: return jsonify([])
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_su(), params={'order': 'updated_at.desc'}, timeout=10)
    r.raise_for_status()
    ql = q.lower()
    return jsonify([n for n in r.json() if ql in (n.get('title')or'').lower() or ql in (n.get('content')or'').lower()])

@app.route('/api/notes/<int:nid>', methods=['GET'])
def get_one(nid):
    r = requests.get(f'{SUPABASE_URL}/rest/v1/notes', headers=_su(), params={'id': f'eq.{nid}'}, timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows: return jsonify({'error': 'Not found'}), 404
    return jsonify(rows[0])

@app.route('/api/notes/<int:nid>', methods=['PUT'])
def update(nid):
    d = request.json or {}
    body = {'updated_at': datetime.now(timezone.utc).isoformat()}
    if 'title' in d: body['title'] = d['title']
    if 'content' in d: body['content'] = d['content']
    r = requests.patch(f'{SUPABASE_URL}/rest/v1/notes?id=eq.{nid}&select=*', json=body, headers=_su(), timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows: return jsonify({'error': 'Not found'}), 404
    return jsonify(rows[0])

@app.route('/api/notes/<int:nid>', methods=['DELETE'])
def delete(nid):
    r = requests.delete(f'{SUPABASE_URL}/rest/v1/notes?id=eq.{nid}', headers=_su(), timeout=10)
    r.raise_for_status()
    return '', 204