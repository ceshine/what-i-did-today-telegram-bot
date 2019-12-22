import os
import logging
from datetime import datetime, timedelta

from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler
)
from google.cloud import firestore

from db import DB
from reporting import check_and_make_report

TIMEZONE, END_OF_DAY = range(2)
CONFIRM, SELECT, EDIT = range(3)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

LOGGER = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]


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
    if "timezone" not in user_data or "end_of_day" not in user_data:
        doc = DB.collection("meta").document(str(chat_id)).get()
        if doc.exists is False:
            return None
        metadata = doc.to_dict()
        if "timezone" not in metadata or "end_of_day" not in metadata:
            return None
        user_data["timezone"] = metadata["timezone"]
        user_data["end_of_day"] = metadata["end_of_day"]
    return {
        "timezone": user_data["timezone"],
        "end_of_day": user_data["end_of_day"],
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
        DB.collection("meta").document(str(update.message.chat_id)).set({
            "end_of_day": user_data["end_of_day"],
            "timezone": user_data["timezone"]
        })
    update.message.reply_text(
        f'All set! Timezone: {user_data["timezone"]} End of day: {user_data["end_of_day"]}'
    )
    return ConversationHandler.END


def _get_nearest_start(minute=10):
    now = datetime.now()
    if now.minute < minute:
        return now.replace(minute=minute, second=0)
    return (now.replace(minute=minute, second=0) +
            datetime.timedelta(hours=1))


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
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
            ]
        },
        fallbacks=[]
    ))

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

    # job_queue.run_repeating(
    #     check_and_make_report, interval=3600, first=_get_nearest_start()
    # )
    job_queue.run_repeating(
        check_and_make_report, interval=3600, first=5
    )

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
