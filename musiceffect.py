import librosa
import numpy as np
import soundfile as sf
import io
import warnings
from pydub import AudioSegment
from typing import Optional
from functools import lru_cache

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Tez-tez ishlatiladigan parametrlar uchun konstantalar
SAMPLE_RATE = 32000
MAX_AUDIO_LENGTH = 600  # 10 daqiqa
AUDIO_PARAMETERS = ["-q:a", "2", "-b:a", "128k", "-ac", "2"]

@lru_cache(maxsize=32)
def generate_wave_patterns(duration: float, sr: int, duration_per_cycle: float = 4) -> tuple:
    """
    To'lqin patternlarini generatsiya qilish va keshlab saqlash
    """
    t = np.linspace(0, duration, int(duration * sr))
    mod_freq = 1 / duration_per_cycle
    sin_wave = np.sin(2 * np.pi * mod_freq * t)
    cos_wave = np.cos(2 * np.pi * mod_freq * t)
    return sin_wave, cos_wave

def apply_8d_effect(audio_bytes: bytes, duration_per_cycle: float = 4, smooth_factor: float = 0.7) -> Optional[io.BytesIO]:
    try:
        # Audio uzunligini tekshirish
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        if len(audio) > MAX_AUDIO_LENGTH * 1000:  # milliseconds
            raise ValueError("Audio fayl juda uzun")

        # Mono va sample rate ni optimallashtirish
        audio = audio.set_channels(1).set_frame_rate(SAMPLE_RATE)
        
        # WAV formatiga konvertatsiya
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format='wav')
        wav_buffer.seek(0)
        
        # Librosa orqali yuklash va normallashtirish
        y, sr = librosa.load(wav_buffer, sr=SAMPLE_RATE, mono=True)
        duration = len(y) / sr
        
        # To'lqin patternlarini olish (keshdan)
        sin_wave, cos_wave = generate_wave_patterns(duration, sr, duration_per_cycle)
        
        # 8D effektni qo'llash va normalizatsiya
        y = y / (np.max(np.abs(y)) + 1e-7)  # Division by zero oldini olish
        left = np.int16(y * (0.5 + 0.5 * sin_wave * smooth_factor) * 32767)
        right = np.int16(y * (0.5 + 0.5 * cos_wave * smooth_factor) * 32767)
        
        # Stereo konvertatsiya
        stereo_sound = np.vstack((left, right)).T
        
        # MP3 ga konvertatsiya
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, stereo_sound, sr, format='WAV', subtype='PCM_16')
        wav_buffer.seek(0)
        
        output_buffer = io.BytesIO()
        audio = AudioSegment.from_wav(wav_buffer)
        audio.export(output_buffer, format='mp3', parameters=AUDIO_PARAMETERS)
        
        output_buffer.seek(0)
        return output_buffer
        
    except Exception as e:
        raise Exception(f"Audio qayta ishlashda xatolik: {str(e)}")