import telebot
from telebot import types
import json
import os
import threading
from datetime import datetime
from flask import Flask

app = Flask("")

@app.route("/")
def home():
    return "Бот работает"

def run():
    app.run(host="0.0.0.0", port=8000)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN не задан в переменных окружения")

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002703116591"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

bot = telebot.TeleBot(TOKEN)

SPONSORS_FILE = "sponsors.json"
JOIN_LINK_FILE = "join_link.txt"
POST_TEXT_FILE = "post_text.txt"
LAST_POST_ID_FILE = "last_post_id.txt"
USERS_FILE = "users.json"

def load_sponsors():
    if not os.path.exists(SPONSORS_FILE):
        return []
    with open(SPONSORS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_sponsors(sponsors):
    with open(SPONSORS_FILE, "w", encoding="utf-8") as f:
        json.dump(sponsors, f, ensure_ascii=False, indent=2)

def load_join_link():
    if not os.path.exists(JOIN_LINK_FILE):
        return {"text": "🚀 Вступить в команду", "url": ""}
    with open(JOIN_LINK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_join_link(data):
    with open(JOIN_LINK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_post_text():
    if not os.path.exists(POST_TEXT_FILE):
        return ""
    with open(POST_TEXT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def save_post_text(text):
    with open(POST_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

def save_last_post_id(message_id):
    with open(LAST_POST_ID_FILE, "w") as f:
        f.write(str(message_id))

def load_last_post_id():
    if not os.path.exists(LAST_POST_ID_FILE):
        return None
    with open(LAST_POST_ID_FILE, "r") as f:
        return int(f.read())

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_user_to_db(user):
    users = load_users()
    if any(u['id'] == user.id for u in users):
        return
    users.append({
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_users(users)

def check_user_subscriptions(user_id, sponsors):
    for sponsor in sponsors:
        if sponsor.get("enabled", True) and sponsor.get("check", True):
            channel_id = sponsor.get("channel_id")
            if not channel_id:
                continue
            try:
                member = bot.get_chat_member(channel_id, user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    return False
            except:
                return False
    return True

@bot.message_handler(commands=["start"])
def cmd_start(message):
    if message.from_user.id == ADMIN_ID:
        show_main_menu(message)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Связь с владельцем", url="https://t.me/leader_tigers"))
        bot.send_message(message.chat.id, "Теперь кликай «Вступить в команду» в посте и получишь ссылку на команду", reply_markup=markup)

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Редактировать текст поста")
    markup.row("Спонсоры", "Кнопка Вступить в команду")
    markup.row("Предпросмотр поста", "Опубликовать пост")
    markup.row("Редактировать опубликованный пост", "Получить список пользователей")
    markup.row("Рассылка пользователям")
    bot.send_message(message.chat.id, "Выбери действие:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
def handle_admin_text(message):
    if message.text == "Редактировать текст поста":
        msg = bot.send_message(message.chat.id, "Пришли новый текст поста:")
        bot.register_next_step_handler(msg, save_new_post_text)
    elif message.text == "Спонсоры":
        show_sponsors_menu(message)
    elif message.text == "Кнопка Вступить в команду":
        show_join_button_menu(message)
    elif message.text == "Предпросмотр поста":
        send_post_preview(message)
    elif message.text == "Опубликовать пост":
        publish_post(message)
    elif message.text == "Редактировать опубликованный пост":
        edit_published_post(message)
    elif message.text == "Получить список пользователей":
        send_users_list(message)
    elif message.text == "Рассылка пользователям":
        msg = bot.send_message(message.chat.id, "Введи текст для рассылки:")
        bot.register_next_step_handler(msg, broadcast_message)

def save_new_post_text(message):
    save_post_text(message.text)
    bot.send_message(message.chat.id, "Текст сохранён ✅")
    show_main_menu(message)

def show_sponsors_menu(message):
    sponsors = load_sponsors()
    markup = types.InlineKeyboardMarkup()
    for i, sp in enumerate(sponsors):
        status = "✅" if sp.get("check", True) else "❌"
        markup.add(types.InlineKeyboardButton(f"{sp['name']} (проверка: {status})", callback_data=f"sponsor_toggle_{i}"))
        markup.add(types.InlineKeyboardButton("Удалить", callback_data=f"sponsor_delete_{i}"))
    markup.add(types.InlineKeyboardButton("Добавить спонсора ➕", callback_data="sponsor_add"))
    markup.add(types.InlineKeyboardButton("Назад", callback_data="main_menu"))
    bot.send_message(message.chat.id, "Спонсоры:", reply_markup=markup)

def show_join_button_menu(message):
    join = load_join_link()
    bot.send_message(message.chat.id, f"Текущая кнопка:\n{join.get('text')} → {join.get('url')}")
    msg = bot.send_message(message.chat.id, "Введи новый формат:\nТекст|https://ссылка")
    bot.register_next_step_handler(msg, edit_join_button)

def edit_join_button(message):
    parts = message.text.split("|")
    if len(parts) != 2:
        return bot.send_message(message.chat.id, "Неверный формат.")
    save_join_link({"text": parts[0].strip(), "url": parts[1].strip()})
    bot.send_message(message.chat.id, "Кнопка обновлена ✅")
    show_main_menu(message)

def send_post_preview(message):
    post_text = load_post_text()
    sponsors = load_sponsors()
    join_button = load_join_link()

    keyboard = types.InlineKeyboardMarkup()
    for sp in sponsors:
        keyboard.add(types.InlineKeyboardButton(sp["name"], url=sp["url"]))
    keyboard.add(types.InlineKeyboardButton(join_button.get("text", "🚀 Вступить в команду"), callback_data="check_subscription"))

    bot.send_message(message.chat.id, post_text or "(пустой пост)", reply_markup=keyboard, parse_mode="HTML")

def publish_post(message):
    post_text = load_post_text()
    sponsors = load_sponsors()
    join_button = load_join_link()

    keyboard = types.InlineKeyboardMarkup()
    for sp in sponsors:
        keyboard.add(types.InlineKeyboardButton(sp["name"], url=sp["url"]))
    keyboard.add(types.InlineKeyboardButton(join_button.get("text", "🚀 Вступить в команду"), callback_data="check_subscription"))

    try:
        msg = bot.send_message(CHANNEL_ID, post_text or "(пустой пост)", reply_markup=keyboard, parse_mode="HTML")
        save_last_post_id(msg.message_id)
        bot.send_message(message.chat.id, "✅ Пост опубликован!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def edit_published_post(message):
    post_text = load_post_text()
    sponsors = load_sponsors()
    join_button = load_join_link()
    last_post_id = load_last_post_id()

    if last_post_id is None:
        bot.send_message(message.chat.id, "Нет опубликованного поста для редактирования.")
        return

    keyboard = types.InlineKeyboardMarkup()
    for sp in sponsors:
        keyboard.add(types.InlineKeyboardButton(sp["name"], url=sp["url"]))
    keyboard.add(types.InlineKeyboardButton(join_button.get("text", "🚀 Вступить в команду"), callback_data="check_subscription"))

    try:
        bot.edit_message_text(chat_id=CHANNEL_ID, message_id=last_post_id, text=post_text or "(пустой пост)", reply_markup=keyboard, parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ Пост отредактирован!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    sponsors = load_sponsors()

    if data == "main_menu":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message)

    elif data == "sponsor_add":
        msg = bot.send_message(call.message.chat.id, "Введи название и ссылку через | (Название|https://...):")
        bot.register_next_step_handler(msg, add_sponsor)

    elif data.startswith("sponsor_toggle_"):
        idx = int(data.split("_")[-1])
        sponsors[idx]["check"] = not sponsors[idx].get("check", True)
        save_sponsors(sponsors)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)
        show_sponsors_menu(call.message)

    elif data.startswith("sponsor_delete_"):
        idx = int(data.split("_")[-1])
        sponsors.pop(idx)
        save_sponsors(sponsors)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)
        show_sponsors_menu(call.message)

    elif data == "check_subscription":
        user_id = call.from_user.id
        if check_user_subscriptions(user_id, sponsors):
            add_user_to_db(call.from_user)
            join = load_join_link()
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(join.get("text", "🚀 Вступить в команду"), url=join.get("url", "")))
            bot.send_message(user_id, "✅ Подписка подтверждена! Вот ссылка для вступления:", reply_markup=keyboard)
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "❌ Подписка не пройдена. Подпишись на все спонсорские каналы.", show_alert=True)

def add_sponsor(message):
    parts = message.text.split("|")
    if len(parts) != 2:
        return bot.send_message(message.chat.id, "Неверный формат.")
    name = parts[0].strip()
    url = parts[1].strip()
    sponsors = load_sponsors()
    sponsors.append({
        "name": name,
        "url": url,
        "check": True,
        "enabled": True,
        "channel_id": extract_channel_id(url)
    })
    save_sponsors(sponsors)
    bot.send_message(message.chat.id, f"✅ Спонсор '{name}' добавлен.")
    show_sponsors_menu(message)

def extract_channel_id(url):
    if url.startswith("https://t.me/"):
        part = url.split("https://t.me/")[1]
        if part.startswith("+"):
            return None
        if part.startswith("@"):
            return part
        return part.split("?")[0]
    elif url.startswith("@"):
        return url
    return None

def send_users_list(message):
    users = load_users()
    if not users:
        bot.send_message(message.chat.id, "База пользователей пуста ❌")
        return
    text = "<b>Пользователи:</b>\n"
    for u in users:
        username = f"@{u['username']}" if u['username'] else "(без username)"
        text += f"{username} — {u['first_name']} {u['last_name'] or ''} — {u['id']}\n"
    if len(text) > 4000:
        with open("users_list.txt", "w", encoding="utf-8") as f:
            for u in users:
                f.write(f"{u['id']},{u['username']},{u['first_name']},{u['last_name']},{u['timestamp']}\n")
        with open("users_list.txt", "rb") as f:
            bot.send_document(message.chat.id, f)
    else:
        bot.send_message(message.chat.id, text, parse_mode="HTML")

def broadcast_message(message):
    text = message.text
    users = load_users()
    count = 0
    for user in users:
        try:
            bot.send_message(user['id'], text)
            count += 1
        except:
            continue
    bot.send_message(message.chat.id, f"Рассылка завершена ✅ Отправлено {count} сообщений.")

@bot.message_handler(func=lambda message: True)
def all_messages_handler(message):
    add_user_to_db(message.from_user)

threading.Thread(target=run).start()
print("Бот запущен...")
bot.infinity_polling()
