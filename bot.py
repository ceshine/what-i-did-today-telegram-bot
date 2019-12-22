import os
import logging
from datetime import datetime

from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler
)
from google.cloud import firestore

TIMEZONE, END_OF_DAY = range(2)
CONFIRM = range(0)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

LOGGER = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "keyfile.json"
DB = firestore.Client()

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.


def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text(
        f'Hi! {update.message.from_user.first_name}')


def journal(update, context):
    context.chat_data['pending'] = update.message.text
    update.message.reply_text(
        "Please confirm this entry (y/n):\n" + update.message.text
    )
    return CONFIRM


def journal_confirm(update, context):
    response = update.message.text.lower()
    if response not in ("y", "n"):
        update.message.reply_text("Please answer **y** or **n**.")
        return CONFIRM
    if response == "y":
        assert DB.collection("live").document(
            str(update.message.chat_id)
        ).set(
            {
                f"{int(datetime.now().timestamp())}": context.chat_data['pending']
            },
            merge=True
        )
        update.message.reply_text("Done!")
    else:
        update.message.reply_text("Canceled!")
    del context.chat_data["pending"]
    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    LOGGER.warning('Update "%s" caused error "%s"', update, context.error)


def config(update, context):
    update.message.reply_text(
        "Specify the timezone you're in (e.g. -8, +1, +8).")
    return TIMEZONE


def set_timezone(update, context):
    if update.message.text.lower() == "cancel":
        return done(update, context)
    try:
        timezone = int(update.message.text)
        if timezone < -12 or timezone > 14:
            raise ValueError()
    except ValueError:
        update.message.reply_text(
            "Timezone should be in the range of [-12, +14].")
        return TIMEZONE
    context.user_data['timezone'] = timezone
    update.message.reply_text(
        "Great! Now specify at what time your day ends (0-23):")
    return END_OF_DAY


def set_end_of_day(update, context):
    if update.message.text.lower() == "cancel":
        return done(update, context)
    try:
        end_of_day = int(update.message.text)
        if end_of_day < 0 or end_of_day > 23:
            raise ValueError()
    except:
        update.message.reply_text(
            "The end of day should be in the range of [0, 23]."
        )
        return END_OF_DAY
    context.user_data['end_of_day'] = end_of_day
    return done(update, context)


def done(update, context):
    if "end_of_day" not in context.user_data or "timezone" not in context.user_data:
        update.message.reply_text(
            "Alright. We can do this later."
        )
    else:
        user_data = context.user_data
        assert DB.collection("meta").document(str(update.message.chat_id)).set({
            "end_of_day": user_data["end_of_day"],
            "timezone": user_data["timezone"]
        })
    update.message.reply_text(
        f'All set! Timezone: {user_data["timezone"]} End of day: {user_data["end_of_day"]}'
    )
    return ConversationHandler.END


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(BOT_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('config', config)],
        states={
            TIMEZONE: [
                MessageHandler(Filters.text, set_timezone)
            ],
            END_OF_DAY: [
                MessageHandler(Filters.text, set_end_of_day)
            ]
        },
        fallbacks=[]
    ))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(ConversationHandler(
        entry_points=[MessageHandler(
            Filters.text, journal, pass_chat_data=True)],
        states={
            CONFIRM: [
                MessageHandler(
                    Filters.text, journal_confirm,
                    pass_chat_data=True)
            ]
        },
        fallbacks=[]
    ))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
