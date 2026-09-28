"""SPA fallback & static file handler."""
import os
from flask import Flask, send_from_directory

STATIC = os.path.join(os.path.dirname(__file__), '..', 'src', 'static')

app = Flask(__name__)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path and os.path.isfile(os.path.join(STATIC, path)):
        return send_from_directory(STATIC, path)
    return send_from_directory(STATIC, 'index.html')


@app.route('/api/users', methods=['GET'])
def users():
    from flask import jsonify
    return jsonify([])