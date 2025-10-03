import telebot
from telebot import types
from config import CONFIG
from keyboard import MAIN_MARKUP, generate_music_markup
from musiceffect import apply_8d_effect
from music_search import music_search
import logging.handlers
import time
import json
from typing import Dict, List
from pathlib import Path
from keep_alive import keep_alive

keep_alive()

# Foydalanuvchilar uchun qidiruv natijalarini saqlash
class SearchCache:
    def __init__(self):
        self.cache: Dict[int, Dict] = {}
        self.cache_timeout = 3600  # 1 soat

    def set(self, chat_id: int, results: List[Dict]):
        """Qidiruv natijalarini saqlash"""
        self.cache[chat_id] = {
            'results': results,
            'timestamp': time.time()
        }

    def get(self, chat_id: int) -> List[Dict]:
        """Qidiruv natijalarini olish"""
        if chat_id in self.cache:
            cache_data = self.cache[chat_id]
            if time.time() - cache_data['timestamp'] < self.cache_timeout:
                return cache_data['results']
            else:
                self.cache.pop(chat_id)
        return None

    def clear(self, chat_id: int):
        """Berilgan chat uchun keshni tozalash"""
        self.cache.pop(chat_id, None)

    def clean_old(self):
        """Eski natijalarni tozalash"""
        current_time = time.time()
        for chat_id in list(self.cache.keys()):
            if current_time - self.cache[chat_id]['timestamp'] > self.cache_timeout:
                self.cache.pop(chat_id)

# Cache obyektini yaratish
search_cache = SearchCache()

# Logging sozlamalari
log_file = Path('logs') / 'bot.log'
log_file.parent.mkdir(exist_ok=True)

logger = logging.getLogger('BotLogger')
logger.setLevel(logging.INFO)

# Faylga va konsolga log yozish
file_handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8'
)
console_handler = logging.StreamHandler()

# Format
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Bot yaratish
bot = telebot.TeleBot(CONFIG['token'], parse_mode='html')

# Foydalanuvchi ma'lumotlarini saqlash
class UserData:
    def __init__(self, filename: str = 'data.json'):
        self.filename = filename
        self.data: Dict = self._load_data()

    def _load_data(self) -> Dict:
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_data(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def update_user(self, user_id: int, update_dict: Dict):
        if str(user_id) not in self.data:
            self.data[str(user_id)] = {}
        self.data[str(user_id)].update(update_dict)
        self.save_data()

user_data = UserData()

# Rate limiting dekoratori
def rate_limit(limit: int, interval: int = 60):
    def decorator(func):
        requests = {}

        def wrapper(message):
            user_id = message.from_user.id
            current_time = time.time()

            if user_id in requests:
                requests[user_id] = [t for t in requests[user_id]
                                   if current_time - t < interval]

                if len(requests[user_id]) >= limit:
                    bot.reply_to(
                        message,
                        "⚠️ <b>Iltimos, biroz kuting!</b>"
                    )
                    return
            else:
                requests[user_id] = []

            requests[user_id].append(current_time)
            return func(message)
        return wrapper
    return decorator

# Bot handlerlari
@bot.message_handler(commands=['start'])
@rate_limit(5)  # 1 daqiqada 5 ta start
def start(message):
    """Botni ishga tushirish va foydalanuvchini ro'yxatga olish"""
    user_data.update_user(
        message.from_user.id,
        {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name,
            'joined_date': time.time(),
            'processed_songs': 0
        }
    )

    welcome_text = (
        f"🎧 <b>Assalomu alaykum {message.from_user.first_name}!</b>\n\n"
        "<i><b>Menga audio fayllarni yuboring, men ularga 8D effekt qo'shib beraman.</b></i>\n"
        f"⚠️ <u>Eslatma: Faylning maksimal hajmi</u> <code>{CONFIG['max_file_size'] // (1024*1024)} MB.</code>\n"
        f"🤖 <i>Botdan foydalanish bo'yicha ma'lumot olish uchun</i> /help <b>komandasi ustiga bosing</b>"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=MAIN_MARKUP)
    logger.info(f"Yangi foydalanuvchi: {message.from_user.username} (ID: {message.from_user.id})")

@bot.message_handler(commands=['help'])
@rate_limit(5)
def help_command(message):
    """Yordam xabarini yuborish"""
    help_text = (
        "🎵 <b>Bot imkoniyatlari:</b>\n\n"
        "1. Audio faylga 8D effekt qo'shish\n"
        "2. Musiqa qidirish\n"
        "3. Topilgan musiqani yuklab olish\n\n"
        "💡 <i>Musiqa nomini yoki ijrochisini yuboring</i>"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=MAIN_MARKUP)

search_results_cache: Dict[int, List[Dict]] = {}

@bot.message_handler(func=lambda message: True)
@rate_limit(10)  # 1 daqiqada 10 ta qidiruv
def search_music(message):
    """Musiqa qidirish"""
    try:
        logger.info(f"Qidiruv: {message.text} (User: {message.from_user.username})")

        results = music_search(message.text)
        if not results:
            bot.reply_to(
                message,
                "😞 <i>Qo'shiq topilmadi. Iltimos, boshqa qo'shiq nomini kiriting.</i>"
            )
            return

        # Qidiruv natijalarini saqlash
        search_cache.set(message.chat.id, results)

        # Natijalarni yuborish
        result_text = "📑 <b>Natijalar:</b> 👇\n" + "\n".join(
            f"<code>{i + 1}</code>. <b>{music['artist']['name']}</b> - <u>{music['title']}</u>"
            for i, music in enumerate(results)
        )

        bot.send_message(
            message.chat.id,
            result_text,
            reply_markup=generate_music_markup(results),
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Qidiruv xatoligi: {str(e)}")
        bot.reply_to(
            message,
            "⚠️ Qidirishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('music_'))
def handle_music_selection(call):
    """Tanlangan musiqani yuborish"""
    try:
        # Foydalanuvchining qidiruv natijalarini olish
        user_results = search_cache.get(call.message.chat.id)

        if not user_results:
            logger.warning(f"Cache topilmadi: {call.message.chat.id}")
            bot.answer_callback_query(
                call.id,
                "⚠️ Qidiruv muddati tugagan. Iltimos, qayta qidiruv qiling."
            )
            return

        # Tanlangan musiqa indeksini olish
        index = int(call.data.split('_')[1])
        if index >= len(user_results):
            bot.answer_callback_query(
                call.id,
                "⚠️ Noto'g'ri tanlov. Iltimos, qayta tanlang."
            )
            return

        # Musiqa ma'lumotlarini olish
        music_data = user_results[index]

        # Ma'lumotlar borligini tekshirish
        if not all(key in music_data for key in ['title', 'duration', 'rank', 'preview', 'artist']):
            raise KeyError("Musiqa ma'lumotlari to'liq emas")

        texts = (
            f"🎙 <b>Qo'shiq reytingi:</b> <code>{music_data['rank']} ta</code>\n"
            f"⏳ <u>Davomiyligi:</u> <code>{music_data['duration']} sekund</code>\n"
            f"📝 <i>Musiqa nomi: </i><code>{music_data['title']}</code>\n"
            f"🎤 <u>Ijrochi: </u><b>{music_data['artist']['name']}</b>\n\n"
            "👉 @eightDbot"
        )

        # Rasm va audio yuborish
        try:
            bot.send_photo(
                chat_id=call.message.chat.id,
                photo=music_data['artist']['picture_big'],
                caption=texts,
                parse_mode='HTML'
            )
        except Exception as photo_error:
            logger.error(f"Rasm yuborishda xatolik: {str(photo_error)}")

        try:
            bot.send_audio(
                chat_id=call.message.chat.id,
                audio=music_data['preview'],
                caption=texts,
                title=f"{music_data['title']} - {music_data['artist']['name']}",
                parse_mode='HTML'
            )
        except Exception as audio_error:
            logger.error(f"Audio yuborishda xatolik: {str(audio_error)}")
            bot.send_message(
                call.message.chat.id,
                "⚠️ Audio yuklashda xatolik yuz berdi."
            )

        # Foydalanuvchi ma'lumotlarini yangilash
        user_data.update_user(
            call.from_user.id,
            {
                'last_search': music_data['title'],
                'last_search_time': time.time()
            }
        )

        # Qidiruv keshini tozalash
        search_cache.clear(call.message.chat.id)

        # Callback ni yopish
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Musiqa tanlashda xatolik: {str(e)}")
        bot.answer_callback_query(
            call.id,
            "⚠️ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )

# Vaqti-vaqti bilan keshni tozalash uchun funksiya
def clean_search_cache():
    """Eski qidiruv natijalarini o'chirish"""
    current_time = time.time()
    for chat_id in list(search_results_cache.keys()):
        if current_time - search_results_cache[chat_id].get('timestamp', 0) > 3600:  # 1 soatdan eski
            search_results_cache.pop(chat_id, None)

@bot.message_handler(content_types=['audio'])
@rate_limit(3)  # 1 daqiqada 3 ta audio
def handle_audio(message):
    """Audio fayllarni qayta ishlash"""
    logger.info(f"Audio qabul qilindi: {message.audio.file_name}")

    if message.audio.file_size > CONFIG['max_file_size']:
        bot.reply_to(
            message,
            f"⚠️ Fayl hajmi {CONFIG['max_file_size'] // (1024*1024)}MB dan katta!"
        )
        return

    try:
        status_message = bot.reply_to(
            message,
            "🎵 <i>Audio qayta ishlanmoqda...</i>"
        )

        file_info = bot.get_file(message.audio.file_id)
        audio_bytes = bot.download_file(file_info.file_path)

        output_buffer = apply_8d_effect(audio_bytes)

        bot.send_audio(
            message.chat.id,
            output_buffer.getvalue(),
            caption="🎧 8D effekt qo'shildi!",
            title=f"{message.audio.title} @eightDbot"
        )

        # Statistikani yangilash
        user_info = user_data.data.get(str(message.from_user.id), {})
        user_data.update_user(
            message.from_user.id,
            {'processed_songs': user_info.get('processed_songs', 0) + 1}
        )

        bot.delete_message(
            message.chat.id,
            status_message.message_id
        )

    except Exception as e:
        logger.error(f"Audio qayta ishlashda xatolik: {e}")
        bot.reply_to(
            message,
            "⚠️ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )

def main():
    """Asosiy bot tsikli"""
    logger.info("Bot ishga tushdi")

    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.error(f"Bot xatosi: {e}")
            time.sleep(15)

if __name__ == '__main__':
    main()
