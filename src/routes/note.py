from flask import Blueprint, jsonify, request
from src.store import get_all_notes, get_note, create_note, update_note, delete_note, search_notes

note_bp = Blueprint('note', __name__)


@note_bp.route('/notes', methods=['GET'])
def list_notes():
    """Get all notes, ordered by most recently updated."""
    return jsonify(get_all_notes())


@note_bp.route('/notes', methods=['POST'])
def create_new_note():
    """Create a new note."""
    data = request.json
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Title and content are required'}), 400
    note = create_note(data['title'], data['content'])
    return jsonify(note), 201


@note_bp.route('/notes/<int:note_id>', methods=['GET'])
def get_single_note(note_id):
    """Get a specific note by ID."""
    note = get_note(note_id)
    if note is None:
        return jsonify({'error': 'Note not found'}), 404
    return jsonify(note)


@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
def update_existing_note(note_id):
    """Update a specific note."""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    note = update_note(note_id, data.get('title'), data.get('content'))
    if note is None:
        return jsonify({'error': 'Note not found'}), 404
    return jsonify(note)


@note_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_existing_note(note_id):
    """Delete a specific note."""
    if delete_note(note_id):
        return '', 204
    return jsonify({'error': 'Note not found'}), 404


@note_bp.route('/notes/search', methods=['GET'])
def search_notes_list():
    """Search notes by title or content."""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    return jsonify(search_notes(query))