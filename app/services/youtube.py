import yt_dlp
import os
from uuid import uuid4
from typing import Dict
from config.settings import settings

class YouTubeService:
    def download_audio(self, url: str) -> Dict:
        """
        Download audio from YouTube video.
        Returns dict with file_path and title.
        """
        output_filename = f"yt_{uuid4().hex}"
        output_path = os.path.join(settings.UPLOAD_FOLDER, output_filename)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_path,
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'YouTube Video')
            duration = info.get('duration', 0)
            author = info.get('uploader') or info.get('channel') or 'Unknown'
            description = info.get('description', '')
            
        # yt-dlp might append extension to filename
        final_path = output_path + ".mp3"
        if not os.path.exists(final_path):
            # Fallback check
            for ext in ['m4a', 'opus', 'webm']:
                 if os.path.exists(output_path + f".{ext}"):
                     final_path = output_path + f".{ext}"
                     break
        
        if not os.path.exists(final_path):
             raise FileNotFoundError("Could not locate downloaded YouTube file")

        return {
            "file_path": final_path,
            "filename": os.path.basename(final_path),
            "title": title,
            "duration": float(duration) if duration else 0.0,
            "author": author,
            "description": description
        }
