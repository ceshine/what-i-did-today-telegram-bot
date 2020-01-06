import os
import re
import sys
import logging
import traceback
from datetime import datetime, timedelta

from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler
)
from google.cloud import firestore

from .db import DB
from .meta import check_config_exists
from .config import add_config_handler
from .reporting import check_and_make_report
from .email_verification import send_code, resend_code, verify_code

CONFIRM, SELECT, EDIT = range(3)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

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


def journal(update, context):
    if not check_config_exists(update, update.message.chat_id, context.user_data):
        return
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
        DB.collection("live").document(
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


def get_live_list(update, context):
    doc = DB.collection("live").document(str(update.message.chat_id)).get()
    if doc.exists is False or len(doc.to_dict()) == 0:
        update.message.reply_text("No entries has yet been logged today!")
        return None, None
    offset = timedelta(hours=context.user_data["metadata"]["timezone"])
    entries = sorted(
        [
            (
                datetime.utcfromtimestamp(
                    int(key)
                ) + offset,
                key,
                item
            )
            for key, item in doc.to_dict().items()],
        key=lambda x: x[0]
    )
    formatted = [
        f"{i + 1}. {timestamp.strftime('%H:%M:%S')} — {item[:30]}"
        for i, (timestamp, _, item) in enumerate(entries)
    ]
    return entries, formatted


def list_current(update, context) -> None:
    if not check_config_exists(update, update.message.chat_id, context.user_data):
        return
    _, formatted = get_live_list(update, context)
    if formatted:
        update.message.reply_text(
            "(Truncated) Entries so far:\n" + "\n".join(formatted)
        )


def edit_list(update, context):
    if not check_config_exists(update, update.message.chat_id, context.user_data):
        return
    entries, formatted = get_live_list(update, context)
    if entries:
        context.chat_data["entries"] = entries
        update.message.reply_text(
            "(Truncated) Entries so far:\n" + "\n".join(formatted) +
            f"\n pick one you'd like to edit (1 - {len(entries)})"
        )
        return SELECT
    else:
        return ConversationHandler.END


def edit_select(update, context):
    try:
        idx = int(update.message.text)
    except ValueError:
        update.message.reply_text(
            "Please input an index (number)!"
        )
        return ConversationHandler.END
    entries = context.chat_data["entries"]
    if len(entries) < idx or idx < 1:
        update.message.reply_text(
            "Cannot find the entry!"
        )
        return ConversationHandler.END
    context.chat_data["picked"] = idx - 1
    update.message.reply_text(
        "Editing this entry:\n" +
        entries[idx-1][2] +
        "\nWrite the new content of this entry, or use /delete to delete the entry"
    )
    return EDIT


def edit_op(update, context):
    context.chat_data["edit"] = update.message.text
    entries = context.chat_data["entries"]
    update.message.reply_text(
        "Replacing this entry (truncated):\n" +
        entries[context.chat_data["picked"]][2][:30] +
        "\nwith:\n" +
        update.message.text +
        "\nPlease confirm (y/n/Abort)"
    )
    return CONFIRM


def edit_rm(update, context):
    context.chat_data["edit"] = firestore.DELETE_FIELD
    entries = context.chat_data["entries"]
    update.message.reply_text(
        "Deleting this entry (truncated):\n" +
        entries[context.chat_data["picked"]][2][:30] +
        "\nPlease confirm (y/n/Abort)"
    )
    return CONFIRM


def edit_confirm(update, context):
    response = update.message.text.lower()
    if response not in ("y", "n", "abort"):
        update.message.reply_markdown(
            "Please answer *y*, *n*, or *abort*.")
        return CONFIRM
    if response == "y":
        DB.collection("live").document(
            str(update.message.chat_id)
        ).update({
            context.chat_data["entries"][
                context.chat_data["picked"]
            ][1]: context.chat_data["edit"]
        })
        update.message.reply_text("Done!")
    elif response == "abort":
        update.message.reply_text("Roger. Aborted.")
    else:
        update.message.reply_text(
            "Write the new content of this entry, or use /delete to delete the entry"
        )
        return EDIT
    del context.chat_data["edit"]
    del context.chat_data["picked"]
    del context.chat_data["entries"]
    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    LOGGER.warning('Update "%s" caused error "%s"', update, context.error)
    _, _, exc_traceback = sys.exc_info()
    traceback.print_tb(exc_traceback)
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

    add_config_handler(dp)

    dp.add_handler(CommandHandler(
        "verify", verify_code, pass_args=True))
    dp.add_handler(CommandHandler(
        "resend", resend_code))

    dp.add_handler(CommandHandler('help', help_))
    dp.add_handler(CommandHandler('current', list_current))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler(
            "edit", edit_list, pass_chat_data=True)],
        states={
            SELECT: [
                MessageHandler(
                    Filters.text, edit_select,
                    pass_chat_data=True)
            ],
            EDIT: [
                CommandHandler(
                    "delete", edit_rm,
                    pass_chat_data=True),
                MessageHandler(
                    Filters.text, edit_op,
                    pass_chat_data=True)
            ],
            CONFIRM: [
                MessageHandler(
                    Filters.text, edit_confirm,
                    pass_chat_data=True)
            ]
        },
        fallbacks=[]
    ))

    # on noncommand i.e message - echo the messgage on Telegram
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
