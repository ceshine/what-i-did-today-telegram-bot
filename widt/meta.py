from .db import DB


def check_config_exists(update, chat_id, user_data, force_update: bool = False):
    data = load_meta(chat_id, user_data, force_update)
    if "timezone" not in data or not data["timezone"]:
        update.message.reply_text("You need to run /config command first!")
        return False
    return data


def load_meta(chat_id, user_data, force_update: bool = False):
    empty = {"timezone": None, "end_of_day": None,
             "email": None, "verified": False}
    if force_update is True or "metadata" not in user_data:
        doc = DB.collection("meta").document(str(chat_id)).get()
        if doc.exists is False:
            return empty
        metadata = doc.to_dict()
        if "timezone" not in metadata or "end_of_day" not in metadata:
            return empty
        user_data["metadata"] = metadata
    else:
        metadata = user_data["metadata"]
    return {
        "timezone": metadata["timezone"],
        "end_of_day": metadata["end_of_day"],
        "email": metadata.get("email"),
        "verified": metadata.get("email_verified", False)
    }
