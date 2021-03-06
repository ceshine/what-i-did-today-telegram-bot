import os
import random
import logging
from datetime import datetime, timedelta

import requests

from .db import DB
from .meta import check_config_exists, _get_user_meta

MAILGUN_DOMAIN = os.environ.get("MG_DOMAIN", "")
MAILGUN_API_KEY = os.environ.get("MG_KEY", "")
LOGGER = logging.getLogger(__name__)
EXPIRES = timedelta(hours=2)
MIN_RESEND_GAP = timedelta(minutes=5)


def _send_email(email, code) -> bool:
    if MAILGUN_DOMAIN == "" or MAILGUN_API_KEY == "":
        LOGGER.warning(
            "MAILGUN_DOMAIN and/or MAILGUN_API_KEY environment "
            "variable is not set! Skipping emailing...")
        return False
    res = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": f"What I Did Today <bot@{MAILGUN_DOMAIN}>",
            "to": [email],
            "subject": "Verification Code for What I Did Today Bot",
            "text": f"Please send \"/verify {code}\" (text inside the quote) to the bot to verify your email."
        }
    )
    LOGGER.info("Verification email: %s %d" % (code, res.status_code))
    if res.status_code != 200:
        LOGGER.error(res.text)
        return False
    return True


def send_code(update, user_data):
    data = user_data["metadata"]
    assert data.get("email")
    previous_timestamp = data.get("email_verification_timestamp")
    if (
        previous_timestamp and
        datetime.now() - datetime.fromtimestamp(previous_timestamp) <= MIN_RESEND_GAP
    ):
        update.message.reply_text(
            "Please wait until %s before sending another verification email." %
            (datetime.fromtimestamp(previous_timestamp) +
             MIN_RESEND_GAP).strftime("%H:%M:%S")
        )
        return
    code = "%06d" % (random.random() * 1000000)
    assert _send_email(data["email"], code)
    DB.collection("meta").document(str(update.message.chat_id)).set({
        "email_verification_code": code,
        "email_verified": False,
        "email_verification_timestamp": int(datetime.now().timestamp())
    }, merge=True)
    user_data["metadata"]["email_verified"] = False
    update.message.reply_text(
        "Verification email sent! Please check your inbox.")


def verify_code(update, context):
    if not check_config_exists(
        update, update.message.chat_id, context.user_data,
        update_cache=True
    ):
        update.message.reply_text(
            'Please run /config first to set your email.')
        return
    try:
        code = context.args[0]
        data = _get_user_meta(str(update.message.chat_id), context.user_data)
        if not data.get("email") or not data.get("email_verification_code"):
            update.message.reply_text(
                "No verification email has been sent to you yet!")
            return
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /verify <code>')
        return
    # LOGGER.info("%s, %s", data["email_verification_code"], code)
    if data["email_verification_code"] == code:
        DB.collection("meta").document(str(update.message.chat_id)).set({
            "email_verification_code": "",
            "email_verified": True
        }, merge=True)
        context.user_data["metadata"]["email_verified"] = True
        update.message.reply_text("We've successfully verified your email!")
    else:
        update.message.reply_text(
            'The code does not match our record. Please try again.')


def resend_code(update, context):
    if not check_config_exists(update, update.message.chat_id, context.user_data):
        return
    data = _get_user_meta(str(update.message.chat_id), context.user_data)
    if not data.get("email"):
        update.message.reply_text(
            "You haven't added an email address in /config command. Please run /config first.")
    elif data.get("email_verified") is True:
        update.message.reply_text(
            "Your email has already been verified. No need to resend the verificaion code.")
    else:
        send_code(update, context.user_data)
