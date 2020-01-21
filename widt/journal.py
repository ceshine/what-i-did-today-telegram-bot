from datetime import datetime, timedelta

from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler
)
from telegram import ReplyKeyboardMarkup
from google.cloud import firestore

from .db import DB
from .meta import check_config_exists

CONFIRM, SELECT, EDIT = range(3)
YESNO_MARKUP = ReplyKeyboardMarkup(
    [["y", "n"]], one_time_keyboard=True, resize_keyboard=True)
YESNOABORT_MARKUP = ReplyKeyboardMarkup(
    [["y", "n", "Abort"]], one_time_keyboard=True, resize_keyboard=True)


def journal(update, context):
    if not check_config_exists(update, update.message.chat_id, context.user_data):
        return
    context.chat_data['pending'] = update.message.text
    update.message.reply_text(
        "Please confirm this entry (y/n):\n" + update.message.text,
        reply_markup=YESNO_MARKUP
    )
    return CONFIRM


def journal_confirm(update, context):
    response = update.message.text.lower()
    if response not in ("y", "n"):
        update.message.reply_text(
            "Please answer **y** or **n**.",
            reply_markup=YESNO_MARKUP
        )
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
        "\nPlease confirm (y/n/Abort)",
        reply_markup=YESNOABORT_MARKUP
    )
    return CONFIRM


def edit_rm(update, context):
    context.chat_data["edit"] = firestore.DELETE_FIELD
    entries = context.chat_data["entries"]
    update.message.reply_text(
        "Deleting this entry (truncated):\n" +
        entries[context.chat_data["picked"]][2][:30] +
        "\nPlease confirm (y/n/Abort)",
        reply_markup=YESNOABORT_MARKUP
    )
    return CONFIRM


def edit_confirm(update, context):
    response = update.message.text.lower()
    if response not in ("y", "n", "abort"):
        update.message.reply_markdown(
            "Please answer *y*, *n*, or *abort*.",
            reply_markup=YESNOABORT_MARKUP
        )
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


def add_journal_handlers(dp):
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
