#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import os.path
import logging
import requests
import json
import random
import threading
import datetime
import re

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Bot, BotCommand
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from urllib3.exceptions import InsecureRequestWarning
from http.server import HTTPServer, BaseHTTPRequestHandler
from transliterate import translit

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Disable SSL certificate warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Define the /help command as BotCommand objects
help_command = BotCommand('help', 'Показать справку')

digit_emojis = {
    "0": "\u0030\u20E3",  # 0️⃣
    "1": "\u0031\u20E3",  # 1️⃣
    "2": "\u0032\u20E3",  # 2️⃣
    "3": "\u0033\u20E3",  # 3️⃣
    "4": "\u0034\u20E3",  # 4️⃣
    "5": "\u0035\u20E3",  # 5️⃣
    "6": "\u0036\u20E3",  # 6️⃣
    "7": "\u0037\u20E3",  # 7️⃣
    "8": "\u0038\u20E3",  # 8️⃣
    "9": "\u0039\u20E3"   # 9️⃣
}

def replace_digits_with_emojis(text):
    for digit, emoji in digit_emojis.items():
        text = text.replace(digit, emoji)
    return text

class PrometheusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write((f'tbilisi_bus_timetable_bot_users {metrics.users_counter}\n'
                              f'tbilisi_bus_timetable_bot_requests {metrics.requests_counter}\n').encode())

class Metrics:
    def __init__(self):
        self.users_counter = 0
        self.requests_counter = 0

    def log_request(self, param):
        if param == "start":
            self.users_counter += 1
        elif param == "request":
            self.requests_counter += 1

    def reset_counter(self):
        self.users_counter = 0
        self.requests_counter = 0

metrics = Metrics()

def run_server():
    server = HTTPServer(('127.0.0.1', 9123), PrometheusHandler)
    threading.Thread(target=server.serve_forever).start()

run_server()

def reset_counter():
    metrics.reset_counter()
    next_minute = (datetime.datetime.now() + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
    delay = (next_minute - datetime.datetime.now()).total_seconds()
    threading.Timer(delay, reset_counter).start()

reset_counter()

def is_bus_number(string):
    pattern = r'\d'  # Regular expression pattern for a single digit
    digit_count = len(re.findall(pattern, string))
    return digit_count == 3 and string.startswith("#")

def remove_extra_quotes(string):
    if string.count('"') <= 2:
        return string
    else:
        first_quote_index = string.index('"')
        last_quote_index = string.rindex('"')
        new_string = string[:first_quote_index] + string[first_quote_index+1:last_quote_index] + string[last_quote_index+1:]
        return remove_extra_quotes(new_string)

def replace_quotes(string):
    result = ''
    quote_count = 0
    for char in string:
        if char == '"':
            quote_count += 1
            if quote_count % 2 == 1:
                result += '«'
            else:
                result += '»'
        else:
            result += char
    return result

def get_bus_schedule(route_number, direction):
    response = requests.get(
        f"https://transfer.msplus.ge:2443/otp/routers/ttc/buses?routeNumber={route_number}&forward={direction}",
        verify=False
    )
    json_response = response.json()
    buses = json_response.get("bus", []) if "bus" in json_response else []
    if not buses:
        return False

    response_stops = requests.get(
        f"https://transfer.msplus.ge:2443/otp/routers/ttc/routeStops?routeNumber={route_number}&forward={direction}",
        verify=False
    )
    json_response_stops = response_stops.json()
    stops = json_response_stops.get("Stops", []) if "Stops" in json_response_stops else []
    if not stops:
        return False

    if not direction == 0:
        stops.reverse()

    start_stop = translit(stops[0]["Name"].split(" - ")[0], 'ka', reversed=True)
    start_stop = start_stop.lower().title()
    end_stop = translit(stops[-1]["Name"].split(" - ")[0], 'ka', reversed=True)
    end_stop = end_stop.lower().title()
    result = ""

    if direction == 0:
        result += f"🚌 <b>Маршрут № {route_number}</b> ({replace_quotes(remove_extra_quotes(start_stop))} → {replace_quotes(remove_extra_quotes(end_stop))}):\n\n<code>"
    else:
        result += f"🚌 <b>Маршрут № {route_number}</b> ({replace_quotes(remove_extra_quotes(end_stop))} → {replace_quotes(remove_extra_quotes(start_stop))}):\n\n<code>"

    for stop in stops:
        stop_name = translit(stop["Name"].split(" - ")[0], 'ka', reversed=True)
        stop_name = replace_quotes(remove_extra_quotes(stop_name.lower().title()))
        stop_id = stop["StopId"]
        forward_true = any(bus["nextStopId"] == stop_id and bus["forward"] is True for bus in buses)
        forward_false = any(bus["nextStopId"] == stop_id and bus["forward"] is False for bus in buses)

        if forward_true:
            result += " ▲" + "  " + stop_name + "\n"
        elif forward_false:
            result += " ▼" + "  " + stop_name + "\n"
        else:
            result += " ┃" + "  " + stop_name + "\n"

    result += "</code>"

    return result

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text(text='🤖 <b>Привет, человек!</b>\n\nЭтот бот показывает информацию с табло автобусных остановок в Тбилиси.\n\nЧтобы получить информацию с табло, введи его номер (четыре цифры, которые отображаются внизу табло).\n\nНапример, если на табло написано <code>ID:3569 SMS:93344</code>, номер табло — <code>3569</code>.\n\nЭмодзи 🔥 показывает, что до прибытия автобуса осталось меньше пяти минут.\n\n⸻\n\n🚌 <b>Где мой автобус?</b>\n\nЧтобы узнать, на какой остановке сейчас находится ваш автобус, введите номер вашего автобуса и добавьте к нему символ <code>#</code>. Например, <code>#519</code>.', parse_mode='html')
    metrics.log_request("start")

def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text(text='ℹ️ <b>Как пользоваться ботом</b>\n\nЭтот бот показывает информацию с табло автобусных остановок в Тбилиси.\n\nЧтобы получить информацию с табло, введи его номер (четыре цифры, которые отображаются внизу табло).\n\nНапример, если на табло написано <code>ID:3569 SMS:93344</code>, номер табло — <code>3569</code>.\n\nЭмодзи 🔥 показывает, что до прибытия автобуса осталось меньше пяти минут.\n\n⸻\n\n🚌 <b>Где мой автобус?</b>\n\nЧтобы узнать, на какой остановке сейчас находится ваш автобус, введите номер вашего автобуса и добавьте к нему символ <code>#</code>. Например, <code>#519</code>.', parse_mode='html')

def default(update, context):
    """Answer the user message."""
    if not (update.message.text.startswith('#') and update.message.text[1:].isdigit()):
        # Set the stop ID
        route_id = update.message.text

        # Log request body for debug purposes
        logger.info('A request for a bus timetable has been received: "%s"', update.message.text)

        if route_id.isdigit():
            # Make the request
            url = f"https://transfer.msplus.ge:2443/otp/routers/ttc/stopArrivalTimes?stopId={route_id}"
            try:
                response = requests.get(url, verify=False, timeout=5)
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection Error: {e}")
            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout Error: {e}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error: {e}")

            # Extract the relevant data from the JSON response and create a string with all the arrivals
            data = json.loads(response.text)
            arrival_times = data['ArrivalTime']
            arrivals_string = ""
            for arrival in arrival_times:
                route_number = arrival['RouteNumber']
                destination_stop_name = arrival['DestinationStopName']
                arrival_time = arrival['ArrivalTime']
                if arrival_time <= 5:
                    arrivals_string += f"🔥 {replace_digits_with_emojis(route_number)} → {arrival_time} мин.  <code>{destination_stop_name}</code>\n"
                else:
                    arrivals_string += f"🕒 {replace_digits_with_emojis(route_number)} → {arrival_time} мин.  <code>{destination_stop_name}</code>\n"

            if arrivals_string:
                update.message.reply_text(text=arrivals_string + '\n⸻\n\n🚌 <b>Где мой автобус?</b>\n\nЧтобы узнать, на какой остановке сейчас находится ваш автобус, введите номер вашего автобуса и добавьте к нему символ <code>#</code>. Например, <code>#519</code>.', parse_mode='html')
            else:
                update.message.reply_text(text='🔎 <b>Ничего не нашлось</b>\n\nВозможно, все автобусы уже разъехались по домам или табло с таким идентификатором не существует.', parse_mode='html')
            metrics.log_request("request")
        else:
            update.message.reply_text(text='🙅‍♂️ <b>Так дело не пойдёт</b>\n\nЭтот бот показывает информацию с табло, которое стоит рядом с автобусной остановкой.\n\nЧтобы получить информацию с табло, введи его номер (четыре цифры, которые отображаются внизу табло).\n\nНапример, если на табло написано <code>ID:3569 SMS:93344</code>, номер табло — <code>3569</code>.', parse_mode='html')
    else:
        if is_bus_number(update.message.text):
            logger.info('A request for a bus schedule has been received: "%s"', update.message.text)
            update.message.reply_text(text='🔎 <b>Ищу автобусы...</b>', parse_mode='html')

            schedule_0 = get_bus_schedule(update.message.text.lstrip('#'), 0)
            schedule_1 = get_bus_schedule(update.message.text.lstrip('#'), 1)

            if schedule_0 and schedule_1:
                update.message.reply_text(text=schedule_0 + "\n" + schedule_1, parse_mode='html')
            elif schedule_0 and not schedule_1:
                update.message.reply_text(text=schedule_0 + "\n" + "⸻\n\n" + "ℹ️ Сейчас автобусы движутся только в этом направлении.", parse_mode='html')
            elif not schedule_0 and schedule_1:
                update.message.reply_text(text=schedule_1 + "\n" + "⸻\n\n" + "ℹ️ Сейчас автобусы движутся только в этом направлении.", parse_mode='html')
            elif not schedule_0 and not schedule_1:
                update.message.reply_text(text="❌ <b>Ничего не нашлось</b>\n\nВозможно, все автобусы уже разъехались по домам или такого маршрута не существует.", parse_mode='html')
            metrics.log_request("request")
        else:
                update.message.reply_text(text="❌ <b>Такого маршрута нет</b>\n\nНомер автобуса должен состоять из трёх цифр.", parse_mode='html')

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    """Start the bot."""
    # Initialize bot with token
    bot = Bot(token="")

    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(bot=bot, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))

    # set the bot's commands
    bot.set_my_commands([help_command])

    # on noncommand i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text, default))

    # log all errors
    dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
