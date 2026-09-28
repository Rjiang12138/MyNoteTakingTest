"""Vercel serverless entry point — manual dispatch, no Flask route matching."""
import os, re, json
from datetime import datetime, timezone
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

def _clean_supabase_url(value):
    url = (value or "").strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-len("/rest/v1")].rstrip("/")
    return url


SUPABASE_URL = _clean_supabase_url(os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

LANGUAGES = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
    "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese",
    "ru": "Russian", "ar": "Arabic", "th": "Thai", "vi": "Vietnamese",
}

STATIC = os.path.join(os.path.dirname(__file__), "..", "src", "static")
app = Flask(__name__)
CORS(app)


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Keep API failures JSON so the frontend never parses an HTML error page."""
    app.logger.exception("Unhandled request error")
    return jsonify({"error": "Internal server error"}), 500


def _su():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


# ============ SINGLE CATCH-ALL ROUTE WITH MANUAL DISPATCH ============

@app.route("/", defaults={"rest": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@app.route("/<path:rest>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def handler(rest):
    # Depending on the Vercel Python runtime/configuration, the function can
    # receive either /notes or /api/notes. Normalize both forms.
    path = "/" + rest.lstrip("/") if rest else "/"
    if path == "/api":
        path = "/"
    elif path.startswith("/api/"):
        path = path[4:]
    
    if request.method == "OPTIONS":
        return "", 200

    # --- static files ---
    if request.method == "GET":
        if rest and os.path.isfile(os.path.join(STATIC, rest)):
            return send_from_directory(STATIC, rest)
    
    # --- API: notes ---
    m = re.match(r"^/?notes/(\d+)$", path)
    if path == "notes" or path == "/notes":
        if request.method == "GET":
            return _list_notes()
        if request.method == "POST":
            return _create_note()
    elif m:
        nid = int(m.group(1))
        if request.method == "GET":
            return _get_note(nid)
        if request.method == "PUT":
            return _update_note(nid)
        if request.method == "DELETE":
            return _delete_note(nid)
    elif path in ("notes/search", "/notes/search"):
        if request.method == "GET":
            return _search_notes()
    
    # --- API: translate ---
    if path in ("translate", "/translate"):
        if request.method == "POST":
            return _translate()
    elif path in ("translate/languages", "/translate/languages"):
        if request.method == "GET":
            return _langs()
    
    # --- API: users ---
    if path in ("users", "/users"):
        if request.method == "GET":
            return jsonify([])
    
    # --- API: ping ---
    if path in ("ping", "/ping"):
        return jsonify({"pong": True, "path": request.path, "seen_path": path, "method": request.method})
    
    # --- debug ---
    if path in ("debug", "/debug"):
        return jsonify({
            "path_seen": path,
            "request_path": request.path,
            "method": request.method,
            "environ": {k: v for k, v in request.environ.items() if "path" in k.lower() or "route" in k.lower() or "url" in k.lower()}
        })
    
    # --- 404 or SPA ---
    if request.method == "GET":
        return send_from_directory(STATIC, "index.html")
    return jsonify({"error": "Not found"}), 404


# ============ handler functions ============

def _list_notes():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"error": "SUPABASE_URL and SUPABASE_KEY are not configured"}), 503
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/notes", headers=_su(),
                         params={"order": "updated_at.desc"}, timeout=10)
        r.raise_for_status()
    except requests.exceptions.RequestException as error:
        return jsonify({"error": "Supabase request failed", "details": str(error)}), 502
    return jsonify(r.json())

def _create_note():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"error": "SUPABASE_URL and SUPABASE_KEY are not configured"}), 503
    d = request.get_json(silent=True) or {}
    if not d.get("title") or not d.get("content"):
        return jsonify({"error": "Title and content are required"}), 400
    now = datetime.now(timezone.utc).isoformat()
    body = {"title": d["title"], "content": d["content"], "created_at": now, "updated_at": now}
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/notes?select=*",
            json=body,
            headers={**_su(), "Prefer": "return=representation"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return jsonify({"error": "Supabase returned no created note", "details": rows}), 502
        return jsonify(rows[0]), 201
    except requests.exceptions.RequestException as error:
        status = error.response.status_code if error.response is not None else 502
        app.logger.error("Supabase insert failed: status=%s response=%s", status, getattr(error.response, "text", str(error)))
        return jsonify({"error": "Supabase insert failed", "status": status}), 502

def _get_note(nid):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"error": "SUPABASE_URL and SUPABASE_KEY are not configured"}), 503
    r = requests.get(f"{SUPABASE_URL}/rest/v1/notes", headers=_su(),
                     params={"id": f"eq.{nid}"}, timeout=10)
    r.raise_for_status()
    rows = r.json()
    return (jsonify(rows[0]), 200) if rows else (jsonify({"error": "Not found"}), 404)

def _update_note(nid):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"error": "SUPABASE_URL and SUPABASE_KEY are not configured"}), 503
    d = request.get_json(silent=True) or {}
    body = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if "title" in d: body["title"] = d["title"]
    if "content" in d: body["content"] = d["content"]
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/notes?id=eq.{nid}&select=*",
                       json=body, headers=_su(), timeout=10)
    r.raise_for_status()
    rows = r.json()
    return (jsonify(rows[0]), 200) if rows else (jsonify({"error": "Not found"}), 404)

def _delete_note(nid):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"error": "SUPABASE_URL and SUPABASE_KEY are not configured"}), 503
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/notes?id=eq.{nid}", headers=_su(), timeout=10)
    r.raise_for_status()
    return "", 204

def _search_notes():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"error": "SUPABASE_URL and SUPABASE_KEY are not configured"}), 503
    q = (request.args.get("q") or "").strip()
    if not q: return jsonify([])
    r = requests.get(f"{SUPABASE_URL}/rest/v1/notes", headers=_su(),
                     params={"order": "updated_at.desc"}, timeout=10)
    r.raise_for_status()
    ql = q.lower()
    return jsonify([n for n in r.json()
                    if ql in (n.get("title") or "").lower()
                    or ql in (n.get("content") or "").lower()])

def _translate():
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "OPENROUTER_API_KEY not set"}), 500
    d = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()
    target = (d.get("target_lang") or "en").strip()
    if not text: return jsonify({"error": "Text required"}), 400
    if target not in LANGUAGES:
        return jsonify({"error": f"Unsupported: {target}"}), 400
    ln = LANGUAGES[target]
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek/deepseek-chat",
                  "messages": [{"role": "system", "content": f"Translate to {ln}. Only the translation."},
                               {"role": "user", "content": text}],
                  "temperature": 0.3, "max_tokens": 4096},
            timeout=10)
        r.raise_for_status()
        result = r.json()["choices"][0]["message"]["content"].strip()
        return jsonify({"translated_text": result, "target_lang": target, "target_lang_name": ln})
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 502
    except (KeyError, IndexError):
        return jsonify({"error": "Bad response"}), 502

def _langs():
    return jsonify([{"code": c, "name": n} for c, n in LANGUAGES.items()])
