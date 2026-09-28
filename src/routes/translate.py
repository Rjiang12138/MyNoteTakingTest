import os
import requests
from flask import Blueprint, jsonify, request

translate_bp = Blueprint('translate', __name__)

# Read API key from environment (never hardcode in production)
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')

# Target languages supported
LANGUAGES = {
    'zh': 'Chinese',
    'en': 'English',
    'ja': 'Japanese',
    'ko': 'Korean',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ar': 'Arabic',
    'th': 'Thai',
    'vi': 'Vietnamese',
}


@translate_bp.route('/translate', methods=['POST'])
def translate_text():
    """Translate text to the target language via OpenRouter (DeepSeek)."""
    data = request.json
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    text = data.get('text', '').strip()
    target_lang = data.get('target_lang', 'en').strip()

    if not text:
        return jsonify({'error': 'Text to translate is required'}), 400

    if target_lang not in LANGUAGES:
        return jsonify({'error': f'Unsupported language code: {target_lang}'}), 400

    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY environment variable is not set'}), 500

    lang_name = LANGUAGES[target_lang]

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'deepseek/deepseek-chat',
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            f'You are a professional translator. Translate the user\'s text '
                            f'into {lang_name}. Only return the translated text, nothing else. '
                            f'Do not add explanations, notes, or quotation marks.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': text,
                    },
                ],
                'temperature': 0.3,
                'max_tokens': 4096,
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()

        translated = result['choices'][0]['message']['content'].strip()
        return jsonify({
            'translated_text': translated,
            'source_lang': 'auto',
            'target_lang': target_lang,
            'target_lang_name': lang_name,
        })

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Translation service timed out'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Translation service error: {str(e)}'}), 502
    except (KeyError, IndexError) as e:
        return jsonify({'error': f'Unexpected response from translation service: {str(e)}'}), 502


@translate_bp.route('/translate/languages', methods=['GET'])
def get_languages():
    """Return supported languages."""
    return jsonify([
        {'code': code, 'name': name} for code, name in LANGUAGES.items()
    ])