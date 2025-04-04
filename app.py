from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

app.config['DOWNLOAD_FOLDER'] = os.path.join(os.getcwd(), 'downloads')
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

def sanitize_filename(filename):
    tr_to_en = {
        'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c',
        'Ğ': 'G', 'Ü': 'U', 'Ş': 'S', 'İ': 'I', 'Ö': 'O', 'Ç': 'C'
    }
    for tr, en in tr_to_en.items():
        filename = filename.replace(tr, en)
    return re.sub(r'[^\w\-_. ]', '', filename).strip()

@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': str(e)}), e.code
    return render_template('error.html', error=str(e)), e.code

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL gereklidir'}), 400

        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'URL gereklidir'}), 400

        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': False}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    formats.append({
                        'id': f.get('format_id'),
                        'res': f.get('resolution', 'Unknown'),
                        'ext': f.get('ext', 'mp4')
                    })
            
            return jsonify({
                'title': info.get('title'),
                'channel': info.get('uploader'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'formats': formats
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        if not data or 'url' not in data or 'type' not in data:
            return jsonify({'error': 'Geçersiz istek'}), 400

        url = data['url']
        format_type = data['type']
        format_id = data.get('format_id', '')

        if format_type == 'video':
            ydl_opts = {
                'format': format_id or 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(app.config['DOWNLOAD_FOLDER'], '%(title)s.%(ext)s'),
                'quiet': True
            }
        elif format_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(app.config['DOWNLOAD_FOLDER'], '%(title)s.%(ext)s'),
                'quiet': True
            }
        else:
            return jsonify({'error': 'Geçersiz format türü'}), 400

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = sanitize_filename(ydl.prepare_filename(info))
            if format_type == 'audio':
                filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            
            return jsonify({
                'filename': filename,
                'path': os.path.join('downloads', filename)
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)