from flask import Blueprint, request, jsonify, send_file, current_app
import os
import tempfile
import uuid
import logging
from app.services.transcription import TranscriptionService
from app.services.speech import SpeechService

voice_bp = Blueprint('voice', __name__)
logger = logging.getLogger(__name__)

@voice_bp.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    temp_path = None
    try:
        # Save to temp file
        ext = os.path.splitext(file.filename)[1] or '.webm' # Default to webm if blob
        temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
        os.close(temp_fd)
        file.save(temp_path)

        service = TranscriptionService()
        # We rely on service to pick up prefs from DB
        # User might want to override provider via params?
        # For now, stick to DB prefs + global default
        
        segments = service.transcribe(temp_path)
        
        # Flatten text
        full_text = " ".join([s['text'] for s in segments])
        
        return jsonify({
            'text': full_text,
            'segments': segments
        })

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except: pass

@voice_bp.route('/synthesize', methods=['POST'])
def synthesize_speech():
    data = request.get_json()
    text = data.get('text')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        service = SpeechService()
        audio_content = service.synthesize(text)
        
        # Return as audio file
        # We need a BytesIO wrapper
        from io import BytesIO
        return send_file(
            BytesIO(audio_content),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="speech.mp3"
        )

    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        return jsonify({'error': str(e)}), 500

@voice_bp.route('/message/<message_id>/audio', methods=['GET'])
def get_message_audio(message_id):
    from app.extensions import db
    from app.models.conversation import Message
    
    msg = db.session.query(Message).get(message_id)
    if not msg:
        return jsonify({'error': 'Message not found'}), 404
        
    # 1. Check if audio already exists
    audio_path = msg.audio_path
    if audio_path and os.path.exists(audio_path):
        return send_file(audio_path, mimetype="audio/mpeg")
        
    # 2. If not, synthesize it
    if not msg.content:
        return jsonify({'error': 'No content to synthesize'}), 400
        
    try:
        service = SpeechService()
        audio_content = service.synthesize(msg.content)
        
        # 3. Save to file
        # Use simple local storage in app/static/audio
        # Ensure dir exists
        static_audio_dir = os.path.join(current_app.root_path, 'static', 'audio')
        if not os.path.exists(static_audio_dir):
            os.makedirs(static_audio_dir)
            
        filename = f"{message_id}.mp3"
        filepath = os.path.join(static_audio_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(audio_content)
            
        # 4. Update DB
        msg.audio_path = filepath
        db.session.commit()
        
        # 5. Serve
        return send_file(filepath, mimetype="audio/mpeg")
        
    except Exception as e:
        logger.error(f"Lazy synthesis error: {e}")
        return jsonify({'error': str(e)}), 500
