from app.i18n import t


def test_known_key_french():
    result = t("welcome", "fr")
    assert "bienvenue" in result.lower()


def test_known_key_english():
    result = t("welcome", "en")
    assert "welcome" in result.lower()


def test_format_substitution():
    result = t("question_too_long", "fr", max_length=100)
    assert "100" in result


def test_format_substitution_english():
    result = t("question_too_long", "en", max_length=50)
    assert "50" in result
    assert "too long" in result.lower()


def test_unknown_language_falls_back_to_french():
    result = t("welcome", "de")
    assert "bienvenue" in result.lower()


def test_missing_key_returns_key_without_crashing():
    result = t("this_key_does_not_exist", "fr")
    assert result == "this_key_does_not_exist"


def test_missing_format_arg_falls_back_to_unformatted_text(caplog):
    result = t("question_too_long", "fr")
    assert "{max_length}" in result
