from typing import Dict
from .db import DB


def _get_user_meta(chat_id, user_data, update_cache: bool = False):
    if update_cache is True or "metadata" not in user_data:
        doc = DB.collection("meta").document(str(chat_id)).get()
        metadata: Dict = {}
        if doc.exists:
            metadata = doc.to_dict()
            if "timezone" not in metadata or "end_of_day" not in metadata:
                metadata = {}
        user_data["metadata"] = metadata
    return user_data["metadata"]


def check_config_exists(update, chat_id, user_data, update_cache: bool = False):
    data = _get_user_meta(chat_id, user_data, update_cache)
    if "timezone" not in data or not data["timezone"]:
        update.message.reply_text("You need to run /config command first!")
        return False
    return data
