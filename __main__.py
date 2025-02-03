from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from database import init_db
from handlers import start, handle_message, button_callback

def main():
    init_db()
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    message_handler = MessageHandler(Filters.text & (~Filters.command), handle_message)
    callback_handler = CallbackQueryHandler(button_callback)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(message_handler)
    dispatcher.add_handler(callback_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
