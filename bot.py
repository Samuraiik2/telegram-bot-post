import telebot
from telebot import types
import json
import os
import threading
from flask import Flask

# Flask сервер для Render
app = Flask("")

@app.route("/")
def home():
    return "Bot is running"

def run():
    app.run(host="0.0.0.0", port=8000)

# Отримання змінних середовища
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN не заданий у змінних середовища")

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002703116591"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

bot = telebot.TeleBot(TOKEN)

# Файли для збереження даних
SPONSORS_FILE = "sponsors.json"
JOIN_LINK_FILE = "join_link.txt"
POST_TEXT_FILE = "post_text.txt"

# Завантаження спонсорів
def load_sponsors():
    if not os.path.exists(SPONSORS_FILE):
        return []
    with open(SPONSORS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_sponsors(sponsors):
    with open(SPONSORS_FILE, "w", encoding="utf-8") as f:
        json.dump(sponsors, f, ensure_ascii=False, indent=2)

# Завантаження / збереження посилання кнопки "Вступити в команду"
def load_join_link():
    if not os.path.exists(JOIN_LINK_FILE):
        return {"text": "🚀 Вступити в команду", "url": ""}
    with open(JOIN_LINK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_join_link(data):
    with open(JOIN_LINK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Завантаження / збереження тексту поста
def load_post_text():
    if not os.path.exists(POST_TEXT_FILE):
        return ""
    with open(POST_TEXT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def save_post_text(text):
    with open(POST_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

# Перевірка підписки користувача на спонсорські канали
def check_user_subscriptions(user_id, sponsors):
    for sponsor in sponsors:
        if sponsor.get("enabled", True):
            try:
                member = bot.get_chat_member(sponsor["channel_id"], user_id)
                if member.status in ["left", "kicked"]:
                    return False
            except Exception:
                return False
    return True

# --- Команди адміністратора ---

# Привітання / старт
@bot.message_handler(commands=["start"])
def cmd_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Доступ заборонено.")
        return
    bot.reply_to(message, "Привіт! Керуйте ботом через меню.")
    show_main_menu(message)

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Редагувати текст поста")
    markup.row("Спонсори", "Кнопка Вступити в команду")
    markup.row("Передогляд поста", "Опублікувати пост")
    bot.send_message(message.chat.id, "Обери дію:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
def handle_admin_text(message):
    text = message.text.strip()

    if text == "Редагувати текст поста":
        msg = bot.send_message(message.chat.id, "Надішли новий текст поста (можна з емодзі):")
        bot.register_next_step_handler(msg, save_new_post_text)

    elif text == "Спонсори":
        show_sponsors_menu(message)

    elif text == "Кнопка Вступити в команду":
        show_join_button_menu(message)

    elif text == "Передогляд поста":
        send_post_preview(message)

    elif text == "Опублікувати пост":
        publish_post(message)

    else:
        bot.send_message(message.chat.id, "Обери дію з меню.")

def save_new_post_text(message):
    save_post_text(message.text)
    bot.send_message(message.chat.id, "Текст поста збережено ✅")
    show_main_menu(message)

# --- Меню спонсорів ---

def show_sponsors_menu(message):
    sponsors = load_sponsors()
    markup = types.InlineKeyboardMarkup()
    for i, sp in enumerate(sponsors):
        status = "✅" if sp.get("enabled", True) else "❌"
        btn_text = f"{sp['name']} {status}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"sponsor_toggle_{i}"))
        markup.add(types.InlineKeyboardButton("Видалити", callback_data=f"sponsor_delete_{i}"))
    markup.add(types.InlineKeyboardButton("Додати спонсора ➕", callback_data="sponsor_add"))
    markup.add(types.InlineKeyboardButton("Назад", callback_data="main_menu"))
    bot.send_message(message.chat.id, "Спонсори:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ заборонено.")
        return

    data = call.data
    sponsors = load_sponsors()

    if data == "main_menu":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message)
        return

    if data == "sponsor_add":
        msg = bot.send_message(call.message.chat.id, "Введи нову кнопку спонсора у форматі:\nНазва|https://посилання")
        bot.register_next_step_handler(msg, add_sponsor)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("sponsor_toggle_"):
        idx = int(data.split("_")[-1])
        sponsors[idx]["enabled"] = not sponsors[idx].get("enabled", True)
        save_sponsors(sponsors)
        bot.answer_callback_query(call.id, "Статус спонсора змінено.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_sponsors_menu(call.message)
        return

    if data.startswith("sponsor_delete_"):
        idx = int(data.split("_")[-1])
        sponsors.pop(idx)
        save_sponsors(sponsors)
        bot.answer_callback_query(call.id, "Спонсор видалений.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_sponsors_menu(call.message)
        return

    if data == "join_button_edit":
        msg = bot.send_message(call.message.chat.id, "Введи новий текст та посилання для кнопки у форматі:\nТекст кнопки|https://посилання")
        bot.register_next_step_handler(msg, edit_join_button)
        bot.answer_callback_query(call.id)
        return

def add_sponsor(message):
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Неправильний формат! Спробуй ще раз.")
        return
    name = parts[0].strip()
    url = parts[1].strip()
    sponsors = load_sponsors()
    sponsors.append({"name": name, "url": url, "enabled": True, "channel_id": extract_channel_id(url)})
    save_sponsors(sponsors)
    bot.send_message(message.chat.id, f"Спонсор '{name}' доданий.")
    show_sponsors_menu(message)

def extract_channel_id(url):
    if url.startswith("https://t.me/"):
        part = url.split("https://t.me/")[1]
        if part.startswith("+"):
            return None
        else:
            return part
    return None

def edit_join_button(message):
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Неправильний формат! Спробуй ще раз.")
        return
    text = parts[0].strip()
    url = parts[1].strip()
    save_join_link({"text": text, "url": url})
    bot.send_message(message.chat.id, "Кнопка 'Вступити в команду' оновлена.")
    show_main_menu(message)

# --- Передогляд і публікація поста ---

def send_post_preview(message):
    post_text = load_post_text()
    sponsors = load_sponsors()
    join_button = load_join_link()

    keyboard = types.InlineKeyboardMarkup()
    for sp in sponsors:
        if sp.get("enabled", True):
            keyboard.add(types.InlineKeyboardButton(sp["name"], url=sp["url"]))
    if join_button.get("url"):
        keyboard.add(types.InlineKeyboardButton(join_button.get("text", "🚀 Вступити в команду"), url=join_button["url"]))

    bot.send_message(message.chat.id, post_text or "(Пост порожній)", reply_markup=keyboard, parse_mode="HTML")

def publish_post(message):
    post_text = load_post_text()
    sponsors = load_sponsors()
    join_button = load_join_link()

    keyboard = types.InlineKeyboardMarkup()
    for sp in sponsors:
        if sp.get("enabled", True):
            keyboard.add(types.InlineKeyboardButton(sp["name"], url=sp["url"]))
    if join_button.get("url"):
        keyboard.add(types.InlineKeyboardButton(join_button.get("text", "🚀 Вступити в команду"), url=join_button["url"]))

    try:
        bot.send_message(CHANNEL_ID, post_text or "(Пост порожній)", reply_markup=keyboard, parse_mode="HTML")
        bot.send_message(message.chat.id, "Пост успішно опубліковано ✅")
    except Exception as e:
        bot.send_message(message.chat.id, f"Помилка публікації: {e}")

# Запускаємо Flask сервер у фоновому потоці
threading.Thread(target=run).start()

# Запуск бота
print("Бот запущено...")
bot.infinity_polling()
