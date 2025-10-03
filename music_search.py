import requests
import json
from typing import Optional, List, Dict
from functools import lru_cache
import time

# API parametrlari
API_CONFIG = {
    "base_url": "https://deezerdevs-deezer.p.rapidapi.com/search",
    "headers": {
        "x-rapidapi-key": "dc521e16e1msh8a91d612c2d7f38p1e17cajsnd665a5824996",
        "x-rapidapi-host": "deezerdevs-deezer.p.rapidapi.com"
    }
}

# Kesh va rate limiting uchun
CACHE_TIMEOUT = 3600  # 1 soat
REQUESTS_PER_MINUTE = 30
request_timestamps = []

def check_rate_limit():
    """Rate limitni tekshirish"""
    current_time = time.time()
    global request_timestamps
    
    # Eski timestamplarni o'chirish
    request_timestamps = [t for t in request_timestamps if current_time - t < 60]
    
    if len(request_timestamps) >= REQUESTS_PER_MINUTE:
        raise Exception("Rate limit exceeded")
    
    request_timestamps.append(current_time)

@lru_cache(maxsize=100)
def music_search(music_name: str) -> Optional[List[Dict]]:
    """
    Musiqalarni qidirish va natijani keshlash
    
    Args:
        music_name: Qidirilayotgan musiqa/ijrochi nomi
        
    Returns:
        Optional[List[Dict]]: Topilgan musiqalar ro'yxati
    """
    try:
        check_rate_limit()
        
        response = requests.get(
            API_CONFIG["base_url"],
            headers=API_CONFIG["headers"],
            params={"q": music_name},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json().get('data', [])
            # Kerakli maydonlarni olish
            return [
                {
                    'title': track['title'],
                    'duration': track['duration'],
                    'rank': track['rank'],
                    'preview': track['preview'],
                    'artist': {
                        'name': track['artist']['name'],
                        'picture_big': track['artist']['picture_big']
                    }
                }
                for track in data[:10]  # Eng ko'pi bilan 10 ta natija
            ]
        return None
        
    except requests.RequestException as e:
        print(f"Qidiruv xatosi: {e}")
        return None