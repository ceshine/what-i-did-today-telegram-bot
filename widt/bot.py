import os
import re
import sys
import logging
from datetime import datetime, timedelta

from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler
)
from google.cloud import firestore

from .db import DB
from .meta import check_config_exists
from .config import add_config_handler
from .journal import add_journal_handlers
from .reporting import check_and_make_report
from .email_verification import send_code, resend_code, verify_code

LOGGER = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# Pass the chat_id to be debugged in DEBUG environment variable
DEBUG = os.environ.get("DEBUG", None)

HELP_TEXT = (
    "How to use this bot:\n\n"
    "First step — run /config command to tell us your timezone and when does your day end\n"
    "Then when you achieve something in the day, describe it to the bot. "
    "The bot will ask for your confirmation. Confirm and that's it!\n\n"
    "Other commands:\n"
    "+ /current — show entries collected so far today.\n"
    "+ /edit — edit or delete entries today.\n"
    "\nNote: currently we archive your daily achievement automatically. "
    "In the future we'll provide you a way to view your archive and "
    "also let you decide to keep an archive or not."
)


def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text(
        f'Hi, {update.message.from_user.first_name}. Welcome to "What I Did Today"(WIDT)!\n\n'
        'Feeling depressed? WIDT wants to help! '
        'Talk to this bot about your achievements, small or big, at any time of the day, '
        'and we will show you those achievements at the end of the day as a reminder '
        'of how fantastic you are.\n\n'
        '(Please don\'t tell the bot any sensitive information, e.g., your home address or bank account.)\n\n'
        + HELP_TEXT)


def help_(update, context):
    update.message.reply_text(HELP_TEXT)


def error(update, context):
    """Log Errors caused by Updates."""
    LOGGER.exception('Update "%s" caused error "%s"', update, context.error)
    update.message.reply_text(
        "Oops... Something went wrong..."
    )


def _get_nearest_start(minute=10):
    now = datetime.now()
    if now.minute < minute:
        return now.replace(minute=minute, second=0)
    return (now.replace(minute=minute, second=0) +
            timedelta(hours=1))


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    if BOT_TOKEN == "":
        raise ValueError("BOT_TOKEN environment variable is not set.")
    updater = Updater(BOT_TOKEN, use_context=True)
    job_queue = updater.job_queue

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler('help', help_))

    add_config_handler(dp)

    dp.add_handler(CommandHandler(
        "verify", verify_code, pass_args=True))
    dp.add_handler(CommandHandler(
        "resend", resend_code))

    add_journal_handlers(dp)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Enable logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG if DEBUG else logging.INFO)

    if DEBUG:
        # For testing:
        from functools import partial
        func = partial(check_and_make_report, archive=False, whitelist=[DEBUG])
        func.__name__ = "check_and_make_report"
        job_queue.run_repeating(
            func, interval=300, first=5,
        )
    else:
        job_queue.run_repeating(
            check_and_make_report, interval=3600, first=_get_nearest_start()
        )

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
