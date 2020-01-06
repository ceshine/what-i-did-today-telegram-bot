from widt.bot import start, help_
import widt.bot


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
