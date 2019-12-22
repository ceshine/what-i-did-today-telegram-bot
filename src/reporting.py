from datetime import datetime, timedelta

from telegram.ext import CallbackContext

from db import DB


def get_all_metadata():
    # Then query for documents
    meta_ref = DB.collection(u'meta')
    user_meta = []
    for doc in meta_ref.stream():
        data = doc.to_dict()
        data["chat_id"] = doc.id
        user_meta.append(data)
    return user_meta


def _archive_journal(user_time, chat_id):
    doc = DB.collection("live").document(str(chat_id)).get()
    if doc.exists is False:
        return None
    DB.collection("archive").document(str(chat_id)).set(
        {user_time.strftime("%Y%m%d-%H"): doc.to_dict()},
        merge=True
    )
    DB.collection("live").document(str(chat_id)).delete()
    entries = [(key, item) for key, item in doc.to_dict().items()]
    return entries


def _parse_timestamp(timestamp, metadata):
    return datetime.utcfromtimestamp(int(timestamp)) + timedelta(hours=metadata["timezone"])


def _send_report(context: CallbackContext, entries, metadata):
    if entries is None:
        context.bot.send_message(
            metadata["chat_id"],
            text="You don't have any entries today.\nNo worry. Tomorrow's a brand new day!"
        )
        return
    formatted = [
        "* {} — {}".format(
            _parse_timestamp(
                key, metadata
            ).strftime('%H:%M:%S'),
            item
        ) for key, item in entries
    ]
    context.bot.send_message(
        int(metadata["chat_id"]),
        text=(
            "This is what you did today:\n" +
            "\n".join(formatted) +
            "\nGood job!"
        )
    )


def check_and_make_report(context: CallbackContext):
    user_meta = get_all_metadata()
    current_time = datetime.utcnow()
    for metadata in user_meta:
        if "timezone" not in metadata or "end_of_day" not in metadata:
            continue
        user_time = current_time + timedelta(hours=metadata["timezone"])
        if user_time.hour == metadata["end_of_day"]:
            print(f"Making report for {metadata['chat_id']}")
            entries = _archive_journal(user_time, metadata["chat_id"])
            _send_report(context, entries, metadata)
