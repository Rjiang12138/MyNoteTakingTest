"""Vercel serverless entry point — ALL routes in one file."""
import os
from datetime import datetime, timezone
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

LANGUAGES = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
    "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese",
    "ru": "Russian", "ar": "Arabic", "th": "Thai", "vi": "Vietnamese",
}

STATIC = os.path.join(os.path.dirname(__file__), "..", "src", "static")

app = Flask(__name__)
CORS(app)

def _su():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


# Helper: register route under BOTH /api/xxx and /xxx (Vercel strips /api/ prefix)
def route(path, **kw):
    def wrap(f):
        app.route("/api" + path, **kw)(f)
        app.route(path, **kw)(f)
        return f
    return wrap


# ==================== API: notes ====================

@route("/notes", methods=["GET"])
def api_notes_list():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/notes", headers=_su(), params={"order": "updated_at.desc"}, timeout=10)
    r.raise_for_status()
    return jsonify(r.json())


@route("/notes", methods=["POST"])
def api_notes_create():
    d = request.get_json(silent=True) or {}
    if not d.get("title") or not d.get("content"):
        return jsonify({"error": "Title and content are required"}), 400
    now = datetime.now(timezone.utc).isoformat()
    body = {"title": d["title"], "content": d["content"], "created_at": now, "updated_at": now}
    r = requests.post(f"{SUPABASE_URL}/rest/v1/notes?select=*", json=body, headers=_su(), timeout=10)
    r.raise_for_status()
    return jsonify(r.json()[0]), 201


@route("/notes/search", methods=["GET"])
def api_notes_search():
    q = (request.args.get("q") or "").strip()
    if not q: return jsonify([])
    r = requests.get(f"{SUPABASE_URL}/rest/v1/notes", headers=_su(), params={"order": "updated_at.desc"}, timeout=10)
    r.raise_for_status()
    ql = q.lower()
    return jsonify([n for n in r.json() if ql in (n.get("title") or "").lower() or ql in (n.get("content") or "").lower()])


@route("/notes/<int:nid>", methods=["GET"])
def api_note_get(nid):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/notes", headers=_su(), params={"id": f"eq.{nid}"}, timeout=10)
    r.raise_for_status()
    rows = r.json()
    return (jsonify(rows[0]), 200) if rows else (jsonify({"error": "Not found"}), 404)


@route("/notes/<int:nid>", methods=["PUT"])
def api_note_update(nid):
    d = request.get_json(silent=True) or {}
    body = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if "title" in d: body["title"] = d["title"]
    if "content" in d: body["content"] = d["content"]
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/notes?id=eq.{nid}&select=*", json=body, headers=_su(), timeout=10)
    r.raise_for_status()
    rows = r.json()
    return (jsonify(rows[0]), 200) if rows else (jsonify({"error": "Not found"}), 404)


@route("/notes/<int:nid>", methods=["DELETE"])
def api_note_delete(nid):
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/notes?id=eq.{nid}", headers=_su(), timeout=10)
    r.raise_for_status()
    return "", 204


# ==================== API: translate ====================

@route("/translate", methods=["POST"])
def api_translate():
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "OPENROUTER_API_KEY not set"}), 500
    d = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()
    target = (d.get("target_lang") or "en").strip()
    if not text: return jsonify({"error": "Text required"}), 400
    if target not in LANGUAGES: return jsonify({"error": f"Unsupported language: {target}"}), 400
    ln = LANGUAGES[target]
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek/deepseek-chat",
                  "messages": [{"role": "system", "content": f"Translate to {ln}. Return only the translation."},
                               {"role": "user", "content": text}],
                  "temperature": 0.3, "max_tokens": 4096},
            timeout=10)
        r.raise_for_status()
        result = r.json()["choices"][0]["message"]["content"].strip()
        return jsonify({"translated_text": result, "target_lang": target, "target_lang_name": ln})
    except requests.exceptions.Timeout:
        return jsonify({"error": "Translation service timed out"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 502
    except (KeyError, IndexError):
        return jsonify({"error": "Unexpected response from translation service"}), 502


@route("/translate/languages", methods=["GET"])
def api_translate_langs():
    return jsonify([{"code": c, "name": n} for c, n in LANGUAGES.items()])


# ==================== API: users ====================

@route("/users", methods=["GET"])
def api_users():
    return jsonify([])


# ==================== API: ping ====================

@route("/ping")
def api_ping():
    return jsonify({"pong": True, "path": request.path, "method": request.method})


# ==================== static & SPA ====================

@app.route("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    filepath = os.path.join(STATIC, filename)
    if os.path.isfile(filepath):
        return send_from_directory(STATIC, filename)
    return send_from_directory(STATIC, "index.html")