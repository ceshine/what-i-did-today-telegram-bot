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
from .reporting import check_and_make_report

TIMEZONE, END_OF_DAY, EMAIL = range(3)
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


def load_meta(chat_id, user_data):
    empty = {"timezone": None, "end_of_day": None, "email": None}
    if "timezone" not in user_data or "end_of_day" not in user_data:
        doc = DB.collection("meta").document(str(chat_id)).get()
        if doc.exists is False:
            return empty
        metadata = doc.to_dict()
        if "timezone" not in metadata or "end_of_day" not in metadata:
            return empty
        user_data["timezone"] = metadata["timezone"]
        user_data["end_of_day"] = metadata["end_of_day"]
        user_data["email"] = metadata.get("email")
    return {
        "timezone": user_data["timezone"],
        "end_of_day": user_data["end_of_day"],
        "email": user_data["email"]
    }


def get_live_list(update, context):
    meta = load_meta(update.message.chat_id, context.user_data)
    if meta is None:
        update.message.reply_text("You need to run /config command first!")
        return None, None
    doc = DB.collection("live").document(str(update.message.chat_id)).get()
    if doc.exists is False or len(doc.to_dict()) == 0:
        update.message.reply_text("No entries has yet been logged today!")
        return None, None
    offset = timedelta(hours=meta["timezone"])
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
    _, formatted = get_live_list(update, context)
    if formatted:
        update.message.reply_text(
            "(Truncated) Entries so far:\n" + "\n".join(formatted)
        )


def edit_list(update, context):
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


def config(update, context):
    meta = load_meta(update.message.chat_id, context.user_data)
    current = ""
    current = (
        f"Current config:\n\n" +
        f'Timezone: {meta["timezone"] or "Empty"}\n'
        f'End of Day: {meta["end_of_day"] or "Empty"}\n'
        f'Email: {meta["email"] or "Empty"}\n\n'
    )
    update.message.reply_text(
        current +
        "Specify the timezone you're in (e.g., -8, +1, +8).\n"
        "Type \'cancel\' to stop the process in any step."
    )
    return TIMEZONE


def set_timezone(update, context):
    if update.message.text.lower() == "cancel":
        update.message.reply_text(
            "Alright. We can do this later."
        )
        return ConversationHandler.END
    try:
        timezone = int(update.message.text)
        if timezone < -12 or timezone > 14:
            raise ValueError()
    except ValueError:
        update.message.reply_text(
            "Timezone should be in the range of [-12, +14]."
        )
        return TIMEZONE
    context.user_data['timezone_new'] = timezone
    update.message.reply_text(
        "Great! Now specify at which hour your day ends (0-23):\n"
        "(We'll collect the entries and send you a summary at that time)"
    )
    return END_OF_DAY


def set_end_of_day(update, context):
    if update.message.text.lower() == "cancel":
        update.message.reply_text(
            "Alright. We can do this later."
        )
        return ConversationHandler.END
    try:
        end_of_day = int(update.message.text)
        if end_of_day < 0 or end_of_day > 23:
            raise ValueError()
    except:
        update.message.reply_text(
            "The end of day should be in the range of [0, 23]."
        )
        return END_OF_DAY
    context.user_data['end_of_day_new'] = end_of_day
    update.message.reply_text(
        "Awesome! Finally, you can leave us your email to receive a daily"
        " summary email of your fantastic achievements. Reply "
        " \"skip\" to skip this step (and keep your current config)."
    )
    return EMAIL


def set_email(update, context):
    if update.message.text.lower() == "cancel":
        update.message.reply_text(
            "Alright. We can do this later."
        )
        return ConversationHandler.END
    if update.message.text.lower() == "skip":
        user_data["email_new"] = context.user_data.get("email", "")
        return done(update, context)
    try:
        email = update.message.text
        assert re.match(
            r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)",
            email
        )
    except:
        update.message.reply_text(
            "That doesn't seem like an email address. Please try again..."
        )
        return EMAIL
    context.user_data['email_new'] = email
    return done(update, context)


def done(update, context):
    user_data = context.user_data
    user_data["end_of_day"] = user_data["end_of_day_new"]
    user_data["timezone"] = user_data["timezone_new"]
    user_data["email"] = user_data.get["email_new"]
    for field in ("end_of_day_new", "timezone_new", "email_new"):
        if field in user_data:
            del user_data[field]
    DB.collection("meta").document(str(update.message.chat_id)).set({
        "end_of_day": user_data["end_of_day"],
        "timezone": user_data["timezone"],
        "email": user_data["email"]
    })
    update.message.reply_text(
        f'All set! Timezone: {user_data["timezone"]} End of day: {user_data["end_of_day"]}'
        + (f' Email: {user_data["email"]}' if user_data["email"] else "")
    )
    return ConversationHandler.END


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

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('config', config)],
        states={
            TIMEZONE: [
                MessageHandler(Filters.text, set_timezone)
            ],
            END_OF_DAY: [
                MessageHandler(Filters.text, set_end_of_day)
            ],
            EMAIL: [
                MessageHandler(Filters.text, set_email)
            ],
        },
        fallbacks=[]
    ))

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
            func, interval=3600, first=5,
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
