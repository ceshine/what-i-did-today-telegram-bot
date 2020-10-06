import io
import logging
from typing import Tuple
from itertools import chain
from datetime import datetime, timedelta

import markdown2
from telegram.ext import CommandHandler

from .db import DB
from .meta import check_config_exists


def remove_month_field(x):
    del x["month"]
    return x


def _get_archive(update, context, date_range: Tuple[datetime, datetime]):
    new_query = DB.collection(
        str(update.message.chat_id)
    ).where(
        "month", ">=", int(date_range[0].strftime("%Y%m"))
    ).where(
        "month", "<=", int(date_range[1].strftime("%Y%m"))
    ).stream()
    legacy_doc = DB.collection("archive").document(
        str(update.message.chat_id)
    ).get()
    new_docs = [x for x in new_query if x is not None]
    offset = timedelta(hours=context.user_data["metadata"]["timezone"])
    all_docs = [
        remove_month_field(doc.to_dict())
        for doc in filter(
            lambda x: x.to_dict() is not None,
            chain([legacy_doc], new_docs)
        )
    ]
    entries = sorted(
        [
            (
                datetime.utcfromtimestamp(
                    int(key)
                ) + offset,
                item
            )
            for doc in all_docs
            for row in doc.values()
            for key, item in row.items()
        ],
        key=lambda x: x[0]
    )
    entries = list(filter(
        lambda x: x[0] >= date_range[0] and x[0] <= date_range[1],
        entries
    ))
    return entries


def prepare_file(entries):
    buffer = []
    current_date = None
    for row in entries:
        if current_date is None or row[0].date() != current_date:
            current_date = row[0].date()
            buffer.append(f"\n## {current_date.strftime('%Y-%m-%d')}\n\n")
        buffer.append(f"+ {row[1].strip()}\n")
    html_str = markdown2.markdown("".join(buffer))
    return io.BytesIO(str(html_str).encode("utf8"))


def list_archive(update, context) -> None:
    if not check_config_exists(update, update.message.chat_id, context.user_data):
        update.message.reply_text(
            "Please run /config first!"
        )
        return
    try:
        date_range = (
            datetime.strptime(context.args[0], "%Y%m%d"),
            datetime.strptime(context.args[1], "%Y%m%d")
        )
    except Exception as e:
        print(e)
        update.message.reply_text(
            "Failed to parse dates. Please try again\n"
            "Format: /export <from_date:YYYYMMDD> <to_date:YYYYMMDD> \n"
        )
        return
    entries = _get_archive(update, context, date_range)
    logging.info("Collected %d entries", len(entries))
    update.effective_chat.send_document(
        prepare_file(entries),
        filename=f"export-{context.args[0]}-{context.args[1]}.html"
    )
    update.message.reply_text(
        "There you go!"
    )
    return


def add_export_handlers(dp):
    dp.add_handler(CommandHandler('export', list_archive))
