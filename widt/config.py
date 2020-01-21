import re

from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, Filters

from .db import DB
from .email_verification import send_code
from .meta import check_config_exists, _get_user_meta

TIMEZONE, END_OF_DAY, EMAIL = range(3)


def config(update, context):
    meta = _get_user_meta(update.message.chat_id, context.user_data)
    current = ""
    current = (
        f"Current config:\n\n" +
        f'Timezone: {meta["timezone"] or "Empty"}\n'
        f'End of Day: {meta["end_of_day"] or "Empty"}\n'
        f'Reminder: {"Yes" if meta.get("reminder", True) else "No"}\n'
        f'Email: {meta["email"] or "Empty"} Verified: {meta.get("email_verified", False)}\n\n'
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
        " \"skip\" to skip this step (and keep your current config) or"
        " \"none\" to erase the current config."
    )
    return EMAIL


def set_email(update, context):
    if update.message.text.lower() == "cancel":
        update.message.reply_text(
            "Alright. We can do this later."
        )
        return ConversationHandler.END
    if update.message.text.lower() == "skip":
        context.user_data["email_new"] = context.user_data.get(
            "metadata", {}).get("email", "")
        return done(update, context)
    if update.message.text.lower() == "none":
        context.user_data["email_new"] = ""
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
    metadata = context.user_data['metadata']
    metadata["end_of_day"] = user_data["end_of_day_new"]
    metadata["timezone"] = user_data["timezone_new"]
    if metadata.get("email", "") != user_data["email_new"]:
        # Got an new email address
        metadata["email"] = user_data["email_new"]
        if metadata["email"]:
            send_code(update, user_data)
    for field in ("end_of_day_new", "timezone_new", "email_new"):
        if field in user_data:
            del user_data[field]
    DB.collection("meta").document(str(update.message.chat_id)).set({
        "end_of_day": metadata["end_of_day"],
        "timezone": metadata["timezone"],
        "email": metadata.get("email", "")
    }, merge=True)
    update.message.reply_text(
        f'All set! Timezone: {metadata["timezone"]} End of day: {metadata["end_of_day"]}'
        + (
            f' Email: {metadata.get("email")} Verified: {metadata.get("email_verified", False)}'
            if metadata.get("email") else ""
        )
    )
    return ConversationHandler.END


def set_reminder(update, context):
    try:
        code = context.args[0]
        assert code.lower() in ("yes", "no")
    except (IndexError, ValueError, AssertionError):
        update.message.reply_text('Usage: /reminder [yes|no]')
    DB.collection("meta").document(str(update.message.chat_id)).set({
        "reminder": code == "yes"
    }, merge=True)
    context.user_data["reminder"] = (code == "yes")
    if code == "yes":
        update.message.reply_text(
            'Okay! We will send you reminders from now.'
        )
    else:
        update.message.reply_text(
            'Okay! We will stop bugging you with reminders from now. Use `reminder yes` to turn it back on.'
        )


def add_config_handler(dp):
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
    dp.add_handler(CommandHandler(
        "reminder", set_reminder, pass_args=True))
