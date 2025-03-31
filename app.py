from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS
import yt_dlp
import os
import re
from datetime import datetime

# Flask uygulamasını oluştur
app = Flask(__name__, static_folder=None)
CORS(app)  # Tüm origin'lere izin ver (production'da kısıtlayın)

# Yapılandırmalar
app.config['DOWNLOAD_FOLDER'] = os.path.join(os.getcwd(), 'downloads')
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

def sanitize_filename(filename):
    """Güvenli dosya adı oluşturma"""
    # Türkçe karakter dönüşümü
    tr_to_en = {
        'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c',
        'Ğ': 'G', 'Ü': 'U', 'Ş': 'S', 'İ': 'I', 'Ö': 'O', 'Ç': 'C'
    }
    for tr, en in tr_to_en.items():
        filename = filename.replace(tr, en)
    
    # Özel karakterleri temizle
    return re.sub(r'[^\w\-_. ]', '', filename).strip()

@app.route('/')
def home():
    """Ana sayfa"""
    return send_from_directory('.', 'index.html')

@app.route('/api/info', methods=['POST'])
def get_video_info():
    """Video bilgilerini döndürür"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL gereklidir'}), 400
        
        # YouTube URL kontrolü
        if not ('youtube.com' in url or 'youtu.be' in url):
            return jsonify({'error': 'Geçersiz YouTube URL'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 10
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    formats.append({
                        'id': f.get('format_id'),
                        'res': f.get('resolution', 'Bilinmiyor'),
                        'ext': f.get('ext', 'mp4'),
                        'note': f.get('format_note', '')
                    })
            
            return jsonify({
                'title': info.get('title', 'Başlıksız Video'),
                'channel': info.get('uploader', 'Bilinmeyen Kanal'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'formats': formats
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    """Video indirme endpoint'i"""
    try:
        data = request.get_json()
        url = data.get('url')
        format_type = data.get('type')
        format_id = data.get('format_id', '')
        
        if not url or not format_type:
            return jsonify({'error': 'Eksik parametre'}), 400
        
        # İndirme ayarları
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
        
        # İndirme işlemi
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = sanitize_filename(ydl.prepare_filename(info))
            
            if format_type == 'audio':
                filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            
            # Dosya yolunu kontrol et
            filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            if not os.path.exists(filepath):
                raise Exception('Dosya oluşturulamadı')
            
            return jsonify({
                'filename': filename,
                'size': os.path.getsize(filepath)
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/downloads/<path:filename>')
def download_file(filename):
    """İndirilen dosyayı sunar"""
    try:
        # Güvenlik kontrolü
        if '..' in filename or filename.startswith('/'):
            raise FileNotFoundError
        
        return send_from_directory(
            app.config['DOWNLOAD_FOLDER'],
            filename,
            as_attachment=True,
            mimetype='video/mp4' if filename.endswith('.mp4') else 'audio/mpeg'
        )
    except FileNotFoundError:
        return jsonify({'error': 'Dosya bulunamadı'}), 404

@app.errorhandler(404)
def page_not_found(e):
    """404 hataları için"""
    return render_template('error.html', error="Sayfa bulunamadı"), 404

if __name__ == '__main__':
    app.run(debug=True)