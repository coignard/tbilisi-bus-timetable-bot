import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
import requests
from transliterate import translit
from database import add_station, get_stations, delete_station, add_message, get_message_id, delete_message_id
from config import API_KEY
from telegram.error import BadRequest
from datetime import datetime, timedelta
import pytz

# Configure logging
logging.basicConfig(filename='bot.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def log_action(user, action, extra_info=""):
    if extra_info:
        logging.info(f"User: {user.id} - {user.username} - {user.full_name} | Action: {action} ({extra_info})")
    else:
        logging.info(f"User: {user.id} - {user.username} - {user.full_name} | Action: {action}")

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    log_action(user, "start", "Bot started")

    delete_message_id(user.id)  # Ensure the old message ID is deleted
    stations = get_stations(user.id)

    if stations:
        message = context.bot.send_message(
            chat_id=user.id,
            text="🚌 Куда поедем сегодня?",
            reply_markup=main_menu_keyboard(user.id)
        )
    else:
        message = context.bot.send_message(
            chat_id=user.id,
            text="👋 <b>Гамарджоба!</b>\n\nЧтобы начать пользоваться ботом, введи номер остановки (четыре цифры после <code>ID</code> на информационном табло автобусной остановки) и я покажу, что сейчас отображается на этом табло.\n\nБотом будет удобнее пользоваться, если сохранить автобусные остановки в избранное. Для этого напиши номер остановки и то, как хочешь её назвать. Например, <code>3855 Метро «Марджанишвили»</code>",
            parse_mode='HTML'
        )

    add_message(user.id, message.message_id)
    context.bot.delete_message(chat_id=user.id, message_id=update.message.message_id)

def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    text = update.message.text
    log_action(user, "handle_message", text)

    context.bot.delete_message(chat_id=user.id, message_id=update.message.message_id)

    if ' ' in text:
        stop_number, stop_name = text.split(' ', 1)
        add_station(user.id, stop_number, stop_name)
        response_text = f'✅ Остановка «{stop_name}» добавлена в «Мои остановки»'
        reply_markup = main_menu_keyboard(user.id)
    else:
        stop_number = text
        response_text = get_schedule(stop_number)
        reply_markup = schedule_keyboard(stop_number)

    previous_message_id = get_message_id(user.id)
    if previous_message_id:
        try:
            context.bot.edit_message_text(
                text=response_text,
                chat_id=user.id,
                message_id=previous_message_id[0],
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
    else:
        message = context.bot.send_message(
            chat_id=user.id,
            text=response_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        add_message(user.id, message.message_id)

def get_schedule(stop_number):
    url = f'https://transit.ttc.com.ge/pis-gateway/api/v2/stops/1:{stop_number}/arrival-times?locale=en&ignoreScheduledArrivalTimes=false'
    headers = {'X-api-key': API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        buses = response.json()
        if not buses:
            return "☕️ <b>Все автобусы уехали</b>\n\nИли табло с таким идентификатором не существует."

        schedule = ""
        tz = pytz.timezone('Asia/Tbilisi')
        now = datetime.now(tz)
        for bus in buses:
            route = bus['shortName']
            headsign = translit(bus['headsign'], 'ka', reversed=True).title()
            headsign = re.sub(r'(\s-\s|«-|-»|-\s|-\b|\b-)', ' → ', headsign)
            headsign = re.sub(r'""(.*?)""', r'«\1»', headsign)
            headsign = re.sub(r"''(.*?)''", r'«\1»', headsign)
            headsign = re.sub(r'"(.*?)"', r'«\1»', headsign)
            headsign = re.sub(r'“(.*?)”', r'«\1»', headsign)
            headsign = re.sub(r'‘(.*?)’', r'«\1»', headsign)
            headsign = re.sub(r'»(.*?)«', r'«\1»', headsign)
            headsign = re.sub(r'»(.*?)»', r'«\1»', headsign)
            headsign = re.sub(r'«(.*?)»', r'«\1»', headsign)
            time = bus['realtimeArrivalMinutes']
            arrival_time = now + timedelta(minutes=time)
            arrival_time_str = arrival_time.strftime("%H:%M")
            color = "🟢" if time > 5 else "🟡" if time > 1 else "🔥"
            schedule += f"<code>{arrival_time_str}</code> {color} <code>{route}</code> <b>{headsign}</b> через <b>{time} мин.</b>\n"
            #schedule += f"<code>{route}</code> {color} <b>{headsign}</b> через <b>{time} мин.</b>\n"
        return schedule
    else:
        return "👀 Что-то поломалось, похоже. Напишите <code>contact@renecoignard.com</code>, если не починится само"

def show_help(update: Update, context: CallbackContext):
    user = update.callback_query.message.chat
    log_action(user, "show_help")

    help_text = "<b>Где найти расписание</b>\nЧтобы получить расписание, введи номер остановки (четыре цифры после <code>ID</code> на информационном табло автобусной остановки) и я покажу, что сейчас отображается на этом табло.\n\n<b>Как сохранить остановку</b>\nБотом будет удобнее пользоваться, если сохранить автобусные остановки в избранное. Для этого напиши номер остановки и то, как хочешь её назвать. Например, <code>3855 Метро «Марджанишвили»</code>\n\n<b>Как удалить остановку</b>\nЧтобы удалить остановку, нажмите на её название в меню «Мои остановки».\n\n<b>Индикаторы</b>\n🔥 Автобус уедет меньше чем через минуту\n🟡 Автобус скоро отправится (от 2 до 5 минут)\n🟢 Автобус отправится больше чем через 5 минут\n\n<b>Обратная связь</b>\nЕсли что-то сломалось, напишите мне: <code>contact@renecoignard.com</code>"
    query = update.callback_query

    previous_message_id = get_message_id(user.id)
    if previous_message_id:
        context.bot.edit_message_text(
            text=help_text,
            chat_id=user.id,
            message_id=previous_message_id[0],
            reply_markup=help_keyboard_with_back(),
            parse_mode="HTML"
        )
    else:
        message = context.bot.send_message(
            chat_id=user.id,
            text=help_text,
            reply_markup=help_keyboard_with_back(),
            parse_mode="HTML"
        )
        add_message(user.id, message.message_id)
    query.answer()

def show_my_stations(update: Update, context: CallbackContext):
    user = update.callback_query.message.chat
    log_action(user, "show_my_stations")

    stations = get_stations(user.id)
    if (stations):
        keyboard = [[InlineKeyboardButton(f"❌ Удалить: {stop_name}", callback_data=f"remove_{stop_number}")] for stop_number, stop_name in stations]
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "Сохранённые остановки:"
    else:
        reply_markup = main_menu_keyboard(user.id)
        text = "Нет сохранённых остановок ¯\\_(ツ)_/¯"

    previous_message_id = get_message_id(user.id)
    if previous_message_id:
        context.bot.edit_message_text(
            text=text,
            chat_id=user.id,
            message_id=previous_message_id[0],
            reply_markup=reply_markup
        )
    else:
        message = context.bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=reply_markup
        )
        add_message(user.id, message.message_id)
    update.callback_query.answer()

def show_schedule(update: Update, context: CallbackContext):
    user = update.callback_query.message.chat
    log_action(user, "show_schedule")

    stations = get_stations(user.id)
    if (stations):
        keyboard = [[InlineKeyboardButton(f"{stop_name}", callback_data=f"schedule_{stop_number}")] for stop_number, stop_name in stations]
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "Выбери остановку:"
    else:
        reply_markup = main_menu_keyboard(user.id)
        text = "Нет сохранённых остановок ¯\\_(ツ)_/¯"

    previous_message_id = get_message_id(user.id)
    if previous_message_id:
        context.bot.edit_message_text(
            text=text,
            chat_id=user.id,
            message_id=previous_message_id[0],
            reply_markup=reply_markup
        )
    else:
        message = context.bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=reply_markup
        )
        add_message(user.id, message.message_id)
    update.callback_query.answer()

def show_schedule_for_station(update: Update, context: CallbackContext, stop_number: str):
    user = update.callback_query.message.chat
    log_action(user, "show_schedule_for_station", stop_number)

    schedule_text = get_schedule(stop_number)
    keyboard = [
        [InlineKeyboardButton("« Назад", callback_data="back_to_schedule"), InlineKeyboardButton("Обновить", callback_data=f"refresh_{stop_number}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    previous_message_id = get_message_id(update.callback_query.message.chat_id)
    if previous_message_id:
        try:
            context.bot.edit_message_text(
                text=schedule_text,
                chat_id=update.callback_query.message.chat_id,
                message_id=previous_message_id[0],
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
    else:
        message = context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=schedule_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        add_message(update.callback_query.message.chat_id, message.message_id)

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.message.chat
    log_action(user, "button_callback", query.data)

    previous_message_id = get_message_id(user.id)  # Move this outside the conditional blocks
    if query.data == "back":
        if previous_message_id:
            context.bot.edit_message_text(
                text="🚌 Куда поедем сегодня?",
                chat_id=user.id,
                message_id=previous_message_id[0],
                reply_markup=main_menu_keyboard(user.id),
                parse_mode='HTML'
            )
    elif query.data.startswith("remove_"):
        stop_number = query.data.split("_")[1]
        delete_station(user.id, stop_number)
        stations = get_stations(user.id)
        if stations:
            show_my_stations(update, context)
        else:
            context.bot.edit_message_text(
                text="Нет сохранённых остановок ¯\\_(ツ)_/¯",
                chat_id=user.id,
                message_id=previous_message_id[0],
                reply_markup=main_menu_keyboard(user.id)
            )
    elif query.data == "schedule":
        show_schedule(update, context)
    elif query.data == "help":
        show_help(update, context)
    elif query.data == "my_stations":
        show_my_stations(update, context)
    elif query.data.startswith("schedule_"):
        stop_number = query.data.split("_")[1]
        show_schedule_for_station(update, context, stop_number)
    elif query.data.startswith("refresh_"):
        stop_number = query.data.split("_")[1]
        show_schedule_for_station(update, context, stop_number)
    elif query.data == "back_to_schedule":
        show_schedule(update, context)
    query.answer()

def main_menu_keyboard(user_id):
    stations = get_stations(user_id)
    if stations:
        keyboard = [
            [InlineKeyboardButton("🕒 Расписание", callback_data='schedule'), InlineKeyboardButton("🛟 Помощь", callback_data='help')],
            [InlineKeyboardButton("⭐️ Мои остановки", callback_data='my_stations')]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🛟 Помощь", callback_data='help')]
        ]
    return InlineKeyboardMarkup(keyboard)

def schedule_keyboard(stop_number):
    keyboard = [
        [InlineKeyboardButton("« Назад", callback_data="back_to_schedule"), InlineKeyboardButton("Обновить", callback_data=f"refresh_{stop_number}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def help_keyboard_with_back():
    keyboard = [
        [InlineKeyboardButton("« Назад", callback_data='back')]
    ]
    return InlineKeyboardMarkup(keyboard)
