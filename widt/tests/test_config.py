from telegram.ext import ConversationHandler

from widt.config import (
    config, set_timezone, set_end_of_day, set_email,
    done, set_reminder, TIMEZONE, END_OF_DAY, EMAIL
)
import widt.config


def test_config_start_empty(mocker):
    mocker.patch('widt.config._get_user_meta')
    widt.config._get_user_meta.return_value = {}
    update = mocker.MagicMock()
    assert config(update, mocker.MagicMock()) == TIMEZONE
    assert "Current config" in update.message.reply_text.call_args[0][0]


def test_config_start_filled(mocker):
    mocker.patch('widt.config._get_user_meta')
    widt.config._get_user_meta.return_value = {
        "timezone": -3,
        "end_of_day": 22,
        "reminder": False,
        "email": "this@is.us",
        "email_verified": False
    }
    update = mocker.MagicMock()
    assert config(update, mocker.MagicMock()) == TIMEZONE
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Current config" in reply_text
    assert "Email: this@is.us" in reply_text
    assert "Verified: False" in reply_text
    assert "Timezone: -3" in reply_text
    assert "End of Day: 22" in reply_text
    assert "Reminder: No" in reply_text


def test_set_timezone_success(mocker):
    context = mocker.MagicMock()
    user_data = {}
    context.user_data.__setitem__.side_effect = user_data.__setitem__
    update = mocker.MagicMock()
    update.message.text = "-5"
    assert set_timezone(update, context) == END_OF_DAY
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Great!" in reply_text
    assert user_data['timezone_new'] == -5


def test_set_end_of_day_success(mocker):
    context = mocker.MagicMock()
    user_data = {}
    context.user_data.__setitem__.side_effect = user_data.__setitem__
    update = mocker.MagicMock()
    update.message.text = "21"
    assert set_end_of_day(update, context) == EMAIL
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Awesome!" in reply_text
    assert user_data['end_of_day_new'] == 21


def test_set_email_yes(mocker):
    # disable done function for now
    mocker.patch('widt.config.done')
    context = mocker.MagicMock()
    user_data = {}
    context.user_data.__setitem__.side_effect = user_data.__setitem__
    update = mocker.MagicMock()
    update.message.text = "this@is.us"
    set_email(update, context)
    assert user_data['email_new'] == "this@is.us"


def test_set_email_wrong(mocker):
    # disable done function for now
    mocker.patch('widt.config.done')
    context = mocker.MagicMock()
    update = mocker.MagicMock()
    update.message.text = "this@isus"
    assert set_email(update, context) == EMAIL
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Please try again" in reply_text


def test_set_email_skip(mocker):
    mocker.patch('widt.config.done')
    context = mocker.MagicMock()
    user_data = {
        "metadata": {"email": "good@place.ea"}
    }
    context.user_data.__setitem__.side_effect = user_data.__setitem__
    context.user_data.__getitem__.side_effect = user_data.__getitem__
    context.user_data.get = user_data.get
    update = mocker.MagicMock()
    update.message.text = "skip"
    set_email(update, context)
    print(user_data)
    assert user_data['email_new'] == "good@place.ea"


def test_done(mocker):
    mocker.patch('widt.config.send_code')
    mocker.patch('widt.config.DB')
    context = mocker.MagicMock()
    user_data = {
        "timezone_new": 5,
        "end_of_day_new": 3,
        "email_new": "good@place.ea",
        "metadata": {}
    }
    context.user_data.__contains__.side_effect = user_data.__contains__
    context.user_data.__getitem__.side_effect = user_data.__getitem__
    context.user_data.__delitem__.side_effect = user_data.__delitem__
    update = mocker.MagicMock()
    assert done(update, context) == ConversationHandler.END
    assert widt.config.send_code.call_args[0][0] is update
    assert widt.config.send_code.call_args[0][1] is context.user_data
    reply_text = update.message.reply_text.call_args[0][0]
    assert reply_text.startswith("All set!")
    print(user_data)
    assert "end_of_day_new" not in user_data
    assert "timezone_new" not in user_data
    assert "email_new" not in user_data
    widt.config.DB.collection.return_value.document.\
        return_value.set.assert_called_once()
    set_args = widt.config.DB.collection.return_value.\
        document.return_value.set.call_args[0][0]
    assert set_args["end_of_day"] == 3
    assert set_args["timezone"] == 5
    assert set_args["email"] == "good@place.ea"
    assert user_data["metadata"]["email"] == "good@place.ea"
    assert user_data["metadata"]["timezone"] == 5
    assert user_data["metadata"]["end_of_day"] == 3


def test_done_same_email(mocker):
    mocker.patch('widt.config.send_code')
    mocker.patch('widt.config.DB')
    context = mocker.MagicMock()
    user_data = {
        "timezone_new": 5,
        "end_of_day_new": 3,
        "email_new": "good@place.ea",
        "metadata": {"email": "good@place.ea"}
    }
    context.user_data.__contains__.side_effect = user_data.__contains__
    context.user_data.__getitem__.side_effect = user_data.__getitem__
    context.user_data.__delitem__.side_effect = user_data.__delitem__
    update = mocker.MagicMock()
    assert done(update, context) == ConversationHandler.END
    reply_text = update.message.reply_text.call_args[0][0]
    assert widt.config.send_code.called == False
    assert reply_text.startswith("All set!")
    widt.config.DB.collection.return_value.document.\
        return_value.set.assert_called_once()
    set_args = widt.config.DB.collection.return_value.\
        document.return_value.set.call_args[0][0]
    assert set_args["end_of_day"] == 3
    assert set_args["timezone"] == 5
    assert set_args["email"] == "good@place.ea"
    assert user_data["metadata"]["email"] == "good@place.ea"
    assert user_data["metadata"]["timezone"] == 5
    assert user_data["metadata"]["end_of_day"] == 3


def test_set_reminder_yes(mocker):
    mocker.patch('widt.config.set_reminder')
    mocker.patch('widt.config.DB')
    user_data = {}
    context = mocker.MagicMock()
    context.args = ["yes"]
    context.user_data.__setitem__.side_effect = user_data.__setitem__
    update = mocker.MagicMock()
    set_reminder(update, context)
    reply_text = update.message.reply_text.call_args[0][0]
    assert "will send you reminder" in reply_text
    widt.config.DB.collection.return_value.document.\
        return_value.set.assert_called_once()
    set_args = widt.config.DB.collection.return_value.\
        document.return_value.set.call_args[0][0]
    assert set_args["reminder"] is True
    assert user_data["reminder"] is True


def test_set_reminder_yes(mocker):
    mocker.patch('widt.config.set_reminder')
    mocker.patch('widt.config.DB')
    user_data = {}
    context = mocker.MagicMock()
    context.args = ["no"]
    context.user_data.__setitem__.side_effect = user_data.__setitem__
    update = mocker.MagicMock()
    set_reminder(update, context)
    reply_text = update.message.reply_text.call_args[0][0]
    assert "will stop bugging you" in reply_text
    widt.config.DB.collection.return_value.document.\
        return_value.set.assert_called_once()
    set_args = widt.config.DB.collection.return_value.\
        document.return_value.set.call_args[0][0]
    assert set_args["reminder"] is False
    assert user_data["reminder"] is False
