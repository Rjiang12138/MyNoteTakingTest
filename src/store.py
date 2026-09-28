"""In-memory store for notes and users (Vercel-compatible)."""
import threading
from datetime import datetime, timezone

_lock = threading.Lock()

# In-memory storage
_notes: dict[int, dict] = {}
_next_note_id = 1

_users: dict[int, dict] = {}
_next_user_id = 1


def get_all_notes() -> list[dict]:
    with _lock:
        return sorted(_notes.values(), key=lambda n: n.get('updated_at', ''), reverse=True)


def get_note(note_id: int) -> dict | None:
    with _lock:
        return _notes.get(note_id)


def create_note(title: str, content: str) -> dict:
    global _next_note_id
    with _lock:
        now = datetime.now(timezone.utc).isoformat()
        note = {
            'id': _next_note_id,
            'title': title,
            'content': content,
            'created_at': now,
            'updated_at': now,
        }
        _notes[_next_note_id] = note
        _next_note_id += 1
        return dict(note)


def update_note(note_id: int, title: str | None = None, content: str | None = None) -> dict | None:
    with _lock:
        note = _notes.get(note_id)
        if note is None:
            return None
        if title is not None:
            note['title'] = title
        if content is not None:
            note['content'] = content
        note['updated_at'] = datetime.now(timezone.utc).isoformat()
        return dict(note)


def delete_note(note_id: int) -> bool:
    with _lock:
        if note_id in _notes:
            del _notes[note_id]
            return True
        return False


def search_notes(query: str) -> list[dict]:
    q = query.lower()
    with _lock:
        return sorted(
            [n for n in _notes.values()
             if q in n.get('title', '').lower() or q in n.get('content', '').lower()],
            key=lambda n: n.get('updated_at', ''),
            reverse=True,
        )


def get_all_users() -> list[dict]:
    with _lock:
        return list(_users.values())


def get_user(user_id: int) -> dict | None:
    with _lock:
        return _users.get(user_id)


def create_user(username: str, email: str) -> dict:
    global _next_user_id
    with _lock:
        user = {
            'id': _next_user_id,
            'username': username,
            'email': email,
        }
        _users[_next_user_id] = user
        _next_user_id += 1
        return dict(user)


def update_user(user_id: int, username: str | None = None, email: str | None = None) -> dict | None:
    with _lock:
        user = _users.get(user_id)
        if user is None:
            return None
        if username is not None:
            user['username'] = username
        if email is not None:
            user['email'] = email
        return dict(user)


def delete_user(user_id: int) -> bool:
    with _lock:
        if user_id in _users:
            del _users[user_id]
            return True
        return False