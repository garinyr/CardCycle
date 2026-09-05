from core import menu


def test_cmd_for_label_maps_every_button():
    for row in menu.MENU:
        for label in row:
            assert menu.cmd_for_label(label) is not None


def test_cmd_for_label_expected_commands():
    assert menu.cmd_for_label("💳 Expense") == "expense"
    assert menu.cmd_for_label("📄 Statement") == "statement"
    assert menu.cmd_for_label("📊 Running") == "running"
    assert menu.cmd_for_label("🗂 Cards") == "cards"
    assert menu.cmd_for_label("📊 Summary") == "summary"
    assert menu.cmd_for_label("ℹ️ Help") == "help"


def test_cmd_for_label_unknown_and_whitespace():
    assert menu.cmd_for_label("gibberish") is None
    assert menu.cmd_for_label("") is None
    assert menu.cmd_for_label(None) is None
    assert menu.cmd_for_label("  💳 Expense  ") == "expense"


def test_reply_keyboard_shape():
    kb = menu.reply_keyboard()
    assert kb["resize_keyboard"] is True
    assert "input_field_placeholder" in kb
    # one row per menu row, one {"text": ...} per button
    assert len(kb["keyboard"]) == len(menu.MENU)
    for row, menu_row in zip(kb["keyboard"], menu.MENU):
        assert [btn["text"] for btn in row] == menu_row


def test_menu_text_mentions_buttons():
    text = menu.menu_text()
    assert "💳 Expense" in text
    assert "🗂 Cards" in text
    assert "📊 Summary" in text
