from environs import Env
from pathlib import Path

env = Env()

# .env faylini avtomatik topish
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    env.read_env(str(env_path))

# Asosiy konfiguratsiya
CONFIG = {
    'token': env('ttoken'),
    'max_file_size': 20 * 1024 * 1024,  # 20 MB
    'max_audio_length': 600,  # 10 daqiqa
    'cache_timeout': 3600,  # 1 soat
    'requests_per_minute': 30
}