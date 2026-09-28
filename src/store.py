"""Redis-backed store for notes and users (Vercel KV compatible).

Uses the KV_URL environment variable that Vercel KV automatically provides.
Works locally too — set KV_URL or REDIS_URL to your Redis instance.
"""
import os
from datetime import datetime, timezone

import redis

_REDIS_URL = os.environ.get('KV_URL') or os.environ.get('REDIS_URL')
_r = None


def _redis() -> redis.Redis:
    """Lazy-init Redis connection so the module import never fails."""
    global _r
    if _r is None:
        url = _REDIS_URL or 'redis://localhost:6379'
        _r = redis.Redis.from_url(url, decode_responses=True)
    return _r


# ── key names ────────────────────────────────────────────────────────────

NOTE = 'note:'          # hash: note:id → fields
NOTE_NEXT = 'note:next'  # string: auto-increment counter
NOTE_ZSET = 'notes:by_updated'  # sorted set: id → timestamp score

USER = 'user:'
USER_NEXT = 'user:next'


def _nk(nid: int) -> str:
    return f'{NOTE}{nid}'


def _uk(uid: int) -> str:
    return f'{USER}{uid}'


def _ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (ValueError, TypeError):
        return 0.0


# ── notes ────────────────────────────────────────────────────────────────

def get_all_notes() -> list[dict]:
    r = _redis()
    ids = r.zrevrange(NOTE_ZSET, 0, -1)
    if not ids:
        return []
    pipe = r.pipeline()
    for nid in ids:
        pipe.hgetall(_nk(int(nid)))
    results = pipe.execute()
    notes = []
    for nid, data in zip(ids, results):
        if data:
            data['id'] = int(nid)
            notes.append(data)
    return notes


def get_note(note_id: int) -> dict | None:
    r = _redis()
    data = r.hgetall(_nk(note_id))
    if not data:
        return None
    data['id'] = note_id
    return data


def create_note(title: str, content: str) -> dict:
    r = _redis()
    nid = r.incr(NOTE_NEXT)
    now = datetime.now(timezone.utc).isoformat()
    note = {'title': title, 'content': content, 'created_at': now, 'updated_at': now}
    r.hset(_nk(nid), mapping=note)
    r.zadd(NOTE_ZSET, {str(nid): _ts(now)})
    note['id'] = nid
    return note


def update_note(note_id: int, title: str | None = None, content: str | None = None) -> dict | None:
    r = _redis()
    key = _nk(note_id)
    if not r.exists(key):
        return None
    mapping = {}
    if title is not None:
        mapping['title'] = title
    if content is not None:
        mapping['content'] = content
    now = datetime.now(timezone.utc).isoformat()
    mapping['updated_at'] = now
    r.hset(key, mapping=mapping)
    r.zadd(NOTE_ZSET, {str(note_id): _ts(now)})
    data = r.hgetall(key)
    data['id'] = note_id
    return data


def delete_note(note_id: int) -> bool:
    r = _redis()
    if r.delete(_nk(note_id)):
        r.zrem(NOTE_ZSET, str(note_id))
        return True
    return False


def search_notes(query: str) -> list[dict]:
    q = query.lower()
    return [
        n for n in get_all_notes()
        if q in n.get('title', '').lower() or q in n.get('content', '').lower()
    ]


# ── users ────────────────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    r = _redis()
    users = []
    for key in r.scan_iter(f'{USER}*'):
        data = r.hgetall(key)
        if data:
            data['id'] = int(data.get('id', 0))
            users.append(data)
    return users


def get_user(user_id: int) -> dict | None:
    r = _redis()
    data = r.hgetall(_uk(user_id))
    if not data:
        return None
    data['id'] = user_id
    return data


def create_user(username: str, email: str) -> dict:
    r = _redis()
    uid = r.incr(USER_NEXT)
    user = {'id': str(uid), 'username': username, 'email': email}
    r.hset(_uk(uid), mapping=user)
    user['id'] = uid
    return user


def update_user(user_id: int, username: str | None = None, email: str | None = None) -> dict | None:
    r = _redis()
    key = _uk(user_id)
    if not r.exists(key):
        return None
    mapping = {}
    if username is not None:
        mapping['username'] = username
    if email is not None:
        mapping['email'] = email
    if mapping:
        r.hset(key, mapping=mapping)
    data = r.hgetall(key)
    data['id'] = user_id
    return data


def delete_user(user_id: int) -> bool:
    return bool(_redis().delete(_uk(user_id)))