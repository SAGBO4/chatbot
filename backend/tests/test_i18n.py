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


def test_every_message_exists_in_every_supported_language():
    from app.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS

    for key, versions in TRANSLATIONS.items():
        assert set(versions) == set(SUPPORTED_LANGUAGES), f"{key}: languages are {sorted(versions)}"
        for lang, text in versions.items():
            assert text.strip(), f"{key} is empty in {lang}"


def test_translations_use_the_same_placeholders_in_every_language():
    import string

    from app.i18n import TRANSLATIONS

    def fields(text):
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}

    for key, versions in TRANSLATIONS.items():
        found = {lang: fields(text) for lang, text in versions.items()}
        assert len({frozenset(v) for v in found.values()}) == 1, f"{key}: placeholders differ {found}"
