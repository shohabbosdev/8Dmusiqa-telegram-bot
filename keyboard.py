from telebot.util import quick_markup
from telebot import types
from typing import List, Dict

# Asosiy tugmalar - konstantalar sifatida saqlash
MAIN_MARKUP = quick_markup({
    '👥 Telegram kanalimiz': {'url': 'https://t.me/shohabbos94'},
}, row_width=2)

def generate_music_markup(search_results: List[Dict]) -> types.InlineKeyboardMarkup:
    """
    Musiqa qidiruv natijalaridan tugmalar yaratish
    
    Args:
        search_results: Topilgan musiqalar ro'yxati
        
    Returns:
        InlineKeyboardMarkup: Yaratilgan tugmalar to'plami
    """
    markup = types.InlineKeyboardMarkup(row_width=1)  # Bir qatorda bitta tugma
    buttons = [
        types.InlineKeyboardButton(
            text=f"{i+1}. {music['title'][:40]}...",  # Uzun nomlarni qisqartirish
            callback_data=f"music_{i}"
        ) 
        for i, music in enumerate(search_results[:10])  # Eng ko'pi bilan 10 ta natija
    ]
    markup.add(*buttons)  # Barcha tugmalarni bir vaqtda qo'shish
    return markup