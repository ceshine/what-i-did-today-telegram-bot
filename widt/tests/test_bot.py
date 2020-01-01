from widt.bot import (
    start, help_, journal, journal_confirm,
    CONFIRM
)
import widt.bot
from telegram.ext import ConversationHandler


def test_start(mocker):
    update = mocker.MagicMock()
    update.message.from_user.first_name = "TestBot"
    start(update, None)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    # Test the greeting message
    assert args[0].startswith("Hi, TestBot.")


def test_help(mocker):
    update = mocker.MagicMock()
    update.message.from_user.first_name = "TestBot"
    help_(update, None)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    # Test the help message
    assert args[0].startswith("How to use this bot:")


def test_journal_positive(mocker):
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
    mocker.patch('widt.bot.DB')
    update = mocker.MagicMock()
    update.message.text = "y"
    update.message.chat_id = 123
    assert journal_confirm(update, context) == ConversationHandler.END
    args, _ = update.message.reply_text.call_args
    assert args[0] == "Done!"
    widt.bot.DB.collection.assert_called_once_with("live")
    widt.bot.DB.collection.return_value.document.assert_called_once_with("123")
    widt.bot.DB.collection.return_value.document.return_value.set.assert_called_once()
    args, kwargs = widt.bot.DB.collection.return_value.document.return_value.set.call_args
    assert list(args[0].values())[0] == text
    assert kwargs["merge"] is True


def test_journal_negative(mocker):
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
    mocker.patch('widt.bot.DB')
    update = mocker.MagicMock()
    update.message.text = "n"
    update.message.chat_id = 123
    assert journal_confirm(update, context) == ConversationHandler.END
    args, _ = update.message.reply_text.call_args
    assert args[0] == "Canceled!"
    assert widt.bot.DB.collection.called == False
    assert widt.bot.DB.collection.return_value.document.called == False
    assert widt.bot.DB.collection.return_value.document.return_value.set.called == False
