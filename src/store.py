"""Supabase-backed store for notes and users.

Uses SUPABASE_URL + SUPABASE_KEY + SUPABASE_SERVICE_KEY from environment.
Requires a `notes` table created via the Supabase SQL Editor:

    CREATE TABLE notes (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
"""
import os
from datetime import datetime, timezone

import requests

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')  # anon key

HEADERS = lambda: {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}


def _r(method: str, path: str, json_data: dict | None = None) -> dict | list[dict]:
    """Make a Supabase REST API call."""
    url = f'{SUPABASE_URL}/rest/v1/{path}'
    kwargs = dict(headers=HEADERS())
    if json_data is not None:
        kwargs['json'] = json_data
    resp = requests.request(method, url, **kwargs, timeout=10)
    resp.raise_for_status()
    if resp.status_code == 204:
        return {}
    return resp.json()


# ── notes ────────────────────────────────────────────────────────────────

def get_all_notes() -> list[dict]:
    """Get all notes, ordered by most recently updated."""
    # Use Supabase's ?order query param
    url = f'{SUPABASE_URL}/rest/v1/notes'
    resp = requests.get(
        url,
        headers=HEADERS(),
        params={'order': 'updated_at.desc'},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return []


def get_note(note_id: int) -> dict | None:
    url = f'{SUPABASE_URL}/rest/v1/notes'
    resp = requests.get(
        url,
        headers=HEADERS(),
        params={'id': f'eq.{note_id}'},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def create_note(title: str, content: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    body = {
        'title': title,
        'content': content,
        'created_at': now,
        'updated_at': now,
    }
    headers = dict(HEADERS())
    resp = requests.post(
        f'{SUPABASE_URL}/rest/v1/notes',
        json=body,
        headers=headers,
        params={'select': '*'},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else {'title': title, 'content': content, 'id': 0}


def update_note(note_id: int, title: str | None = None, content: str | None = None) -> dict | None:
    now = datetime.now(timezone.utc).isoformat()
    body = {'updated_at': now}
    if title is not None:
        body['title'] = title
    if content is not None:
        body['content'] = content

    headers = dict(HEADERS())
    resp = requests.patch(
        f'{SUPABASE_URL}/rest/v1/notes',
        json=body,
        headers=headers,
        params={'id': f'eq.{note_id}', 'select': '*'},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def delete_note(note_id: int) -> bool:
    resp = requests.delete(
        f'{SUPABASE_URL}/rest/v1/notes',
        headers=HEADERS(),
        params={'id': f'eq.{note_id}'},
        timeout=10,
    )
    resp.raise_for_status()
    return True  # Supabase returns 204 on success


def search_notes(query: str) -> list[dict]:
    """Search via Supabase text search (matches title or content)."""
    q = query.strip()
    if not q:
        return get_all_notes()
    # Use Supabase full-text OR condition
    url = f'{SUPABASE_URL}/rest/v1/notes'
    filters = f"or=(title.ilike.*{q}*,content.ilike.*{q}*)"
    resp = requests.get(
        url,
        headers=HEADERS(),
        params={'order': 'updated_at.desc', 'filter': filters},
        timeout=10,
    )
    # If the OR filter approach fails, fall back to loading all
    if resp.status_code != 200:
        all_notes = get_all_notes()
        ql = q.lower()
        return [
            n for n in all_notes
            if ql in (n.get('title') or '').lower() or ql in (n.get('content') or '').lower()
        ]
    resp.raise_for_status()
    return resp.json()


# ── users (stub, using same table approach) ──────────────────────────────
# Not actively used; kept for route compatibility.

def get_all_users() -> list[dict]:
    return []


def get_user(user_id: int) -> dict | None:
    return None


def create_user(username: str, email: str) -> dict:
    return {'id': 1, 'username': username, 'email': email}


def update_user(user_id: int, username: str | None = None, email: str | None = None) -> dict | None:
    return None


def delete_user(user_id: int) -> bool:
    return False