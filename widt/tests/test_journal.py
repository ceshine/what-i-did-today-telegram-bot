from telegram.ext import ConversationHandler

from widt.journal import journal, journal_confirm, CONFIRM
import widt.journal


def test_journal_positive(mocker):
    # pretend hat the test user already has config set
    mocker.patch('widt.journal.check_config_exists')
    widt.journal.check_config_exists.return_value = True
    context = mocker.MagicMock()
    context.chat_data = {}
    update = mocker.MagicMock()
    text = "Test entry"
    update.message.text = text
    assert journal(update, context) == CONFIRM
    assert context.chat_data["pending"] == text
    args, _ = update.message.reply_text.call_args
    assert text in args[0]
    # confirm
    mocker.patch('widt.journal.DB')
    update = mocker.MagicMock()
    update.message.text = "y"
    update.message.chat_id = 123
    assert journal_confirm(update, context) == ConversationHandler.END
    args, _ = update.message.reply_text.call_args
    assert args[0] == "Done!"
    widt.journal.DB.collection.assert_called_once_with("live")
    widt.journal.DB.collection.return_value.document.assert_called_once_with(
        "123")
    widt.journal.DB.collection.return_value.document.return_value.set.assert_called_once()
    args, kwargs = widt.journal.DB.collection.return_value.document.return_value.set.call_args
    assert list(args[0].values())[0] == text
    assert kwargs["merge"] is True


def test_journal_negative(mocker):
    # pretend hat the test user already has config set
    mocker.patch('widt.journal.check_config_exists')
    widt.journal.check_config_exists.return_value = True
    context = mocker.MagicMock()
    context.chat_data = {}
    update = mocker.MagicMock()
    text = "Test entry"
    update.message.text = text
    assert journal(update, context) == CONFIRM
    assert context.chat_data["pending"] == text
    args, _ = update.message.reply_text.call_args
    assert text in args[0]
    # confirm
    mocker.patch('widt.journal.DB')
    update = mocker.MagicMock()
    update.message.text = "n"
    update.message.chat_id = 123
    assert journal_confirm(update, context) == ConversationHandler.END
    args, _ = update.message.reply_text.call_args
    assert args[0] == "Canceled!"
    assert widt.journal.DB.collection.called == False
    assert widt.journal.DB.collection.return_value.document.called == False
    assert widt.journal.DB.collection.return_value.document.return_value.set.called == False
