from flask import Blueprint, jsonify, request
from src.store import get_all_users, get_user, create_user, update_user, delete_user

user_bp = Blueprint('user', __name__)


@user_bp.route('/users', methods=['GET'])
def list_users():
    return jsonify(get_all_users())


@user_bp.route('/users', methods=['POST'])
def create_new_user():
    data = request.json
    user = create_user(data['username'], data['email'])
    return jsonify(user), 201


@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_single_user(user_id):
    user = get_user(user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user)


@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_existing_user(user_id):
    user = update_user(user_id, **request.json)
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user)


@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_existing_user(user_id):
    if delete_user(user_id):
        return '', 204
    return jsonify({'error': 'User not found'}), 404