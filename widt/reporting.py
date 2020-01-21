import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

import requests
from telegram.ext import CallbackContext
from jinja2 import FileSystemLoader, Environment

from .db import DB

MAILGUN_DOMAIN = os.environ.get("MG_DOMAIN", "")
MAILGUN_API_KEY = os.environ.get("MG_KEY", "")
LOGGER = logging.getLogger(__name__)


def _send_email(recipient: str, user_time: datetime, entries: List, message: str):
    if MAILGUN_DOMAIN == "" or MAILGUN_API_KEY == "":
        LOGGER.warning(
            "MAILGUN_DOMAIN and/or MAILGUN_API_KEY environment "
            "variable is not set! Skipping emailing...")
        return
    template_loader = FileSystemLoader(
        searchpath=str(Path(__file__).parent / "templates")
    )
    template_env = Environment(loader=template_loader)
    if len(entries) == 0:
        template = template_env.get_template("skip.jinja")
        output = template.render(
            formatted_date=user_time.strftime("%Y-%m-%d")
        )
        subject = f"{user_time.strftime('%Y%m%d')} — Remember that You Are Awesome!"
    else:
        template = template_env.get_template("normal.jinja")
        output = template.render(
            formatted_date=user_time.strftime("%Y-%m-%d"),
            entries=entries
        )
        subject = f"{user_time.strftime('%Y%m%d')} — Congratulation on Another Awesome Day!"
    res = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": f"What I Did Today <bot@{MAILGUN_DOMAIN}>",
            "to": [recipient],
            "subject": subject,
            "text": message,
            "html": output
        }
    )
    LOGGER.info("Report email: %s %d" % (recipient, res.status_code))
    if res.status_code != 200:
        LOGGER.error(res.text)


def get_all_metadata():
    # Then query for documents
    meta_ref = DB.collection(u'meta')
    user_meta = []
    for doc in meta_ref.stream():
        data = doc.to_dict()
        data["chat_id"] = doc.id
        user_meta.append(data)
    return user_meta


def _archive_journal(user_time, chat_id, archive):
    doc = DB.collection("live").document(str(chat_id)).get()
    if doc.exists is False:
        return None
    if archive:
        DB.collection("archive").document(str(chat_id)).set(
            {user_time.strftime("%Y%m%d-%H"): doc.to_dict()},
            merge=True
        )
        DB.collection("live").document(str(chat_id)).delete()
    entries = sorted(
        [(key, item) for key, item in doc.to_dict().items()],
        key=lambda x: x[0]
    )
    return entries


def _parse_timestamp(timestamp, metadata):
    return datetime.utcfromtimestamp(int(timestamp)) + timedelta(hours=metadata["timezone"])


def _send_report(context: CallbackContext, user_time, entries, metadata):
    if not entries:
        if metadata.get("reminder", True):
            context.bot.send_message(
                metadata["chat_id"],
                text=(
                    "You don't have any entries today.\nNo worries. Tomorrow's a brand new day!\n"
                    "(Use the  `/reminder no` command to stop receiving this message.)"
                )
            )
        message = ""
        entries = []
    else:
        formatted = [
            "* {} — {}".format(
                _parse_timestamp(
                    key, metadata
                ).strftime('%H:%M:%S'),
                item
            ) for key, item in entries
        ]
        message = (
            "What you did today:\n" +
            "\n".join(formatted) +
            "\nGood job!"
        )
        context.bot.send_message(
            int(metadata["chat_id"]),
            text=message
        )
    if "email" in metadata and metadata["email"] != "":
        if not metadata.get("email_verified"):
            LOGGER.info(
                f"Email of {metadata['chat_id']} ({metadata['email']}) not verified."
                " Skipped..."
            )
            return
        if metadata.get("reminder", True) or entries:
            _send_email(
                metadata["email"],
                user_time,
                message=message,
                entries=[
                    (
                        _parse_timestamp(key, metadata).strftime('%H:%M'),
                        item
                    ) for key, item in entries
                ]
            )


def check_and_make_report(context: CallbackContext, archive: bool = True, whitelist=None):
    LOGGER.info("Check and make reports...")
    user_meta = get_all_metadata()
    current_time = datetime.utcnow()
    for metadata in user_meta:
        LOGGER.debug("Processing chat_id: %s", metadata["chat_id"])
        if "timezone" not in metadata or "end_of_day" not in metadata:
            continue
        if whitelist and metadata["chat_id"] not in whitelist:
            continue
        user_time = current_time + timedelta(hours=metadata["timezone"])
        if user_time.hour == metadata["end_of_day"]:
            LOGGER.info(f"Making report for {metadata['chat_id']}")
            entries = _archive_journal(user_time, metadata["chat_id"], archive)
            _send_report(context, user_time, entries, metadata)
