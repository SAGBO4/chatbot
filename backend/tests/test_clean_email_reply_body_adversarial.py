"""
Adversarial QA suite for app.main.clean_email_reply_body().

Goal: break the function, not confirm it works. Sections:
  1. Nominal behavior (safety net for legitimate refactors)
  2. Edge cases (empty / whitespace-only / boundary positions)
  3. False-positive robustness (legit content resembling quote markers)
  4. Type / null handling (None -> "", non-str -> TypeError, by contract)
  5. Data-integrity / security cases
  6. Performance / pathological input
  7. Purity (no side effects, deterministic)

This suite was written adversarially first (see git history / PR discussion):
several tests below used to be `xfail`-marked confirmed bugs (zero-width
space bypassing quote detection, str.splitlines() over-splitting on exotic
unicode separators, a too-greedy "From:" false positive, and crashes on
None/non-str input). All of those have since been fixed in
clean_email_reply_body() and the tests now assert the corrected behavior
directly - kept in this file as permanent regression guards.
"""
import time
import pytest
from app.main import clean_email_reply_body


# ---------------------------------------------------------------------------
# 1. Nominal behavior
# ---------------------------------------------------------------------------

class TestNominalBehavior:
    def test_plain_reply_with_no_quote_is_kept_verbatim(self):
        body = "Bonjour,\n\nVoici la solution : redémarrez le service.\n\nCordialement"
        assert clean_email_reply_body(body) == body.strip()

    def test_reply_above_quote_marker_gt_is_kept(self):
        body = "Voici la solution.\n> question originale\n> deuxième ligne citée"
        assert clean_email_reply_body(body) == "Voici la solution."

    def test_reply_above_dash_separator_is_kept(self):
        body = "La solution est X.\n-----\nCorps du message original"
        assert clean_email_reply_body(body) == "La solution est X."

    def test_reply_above_on_wrote_marker_is_kept(self):
        body = "Fixed it.\nOn Mon, Jan 1, 2024 at 10:00 AM John Doe wrote:\n> original"
        assert clean_email_reply_body(body) == "Fixed it."

    def test_reply_above_french_a_ecrit_marker_is_kept(self):
        body = "Voici la réponse.\nLe 1 janv. 2024 à 10:00, Jean a écrit :\n> original"
        assert clean_email_reply_body(body) == "Voici la réponse."

    def test_reply_above_from_header_is_kept(self):
        body = "Solution : relancez le service.\nFrom: support@example.com\nSubject: Re: Ticket"
        assert clean_email_reply_body(body) == "Solution : relancez le service."

    def test_reply_above_from_header_with_display_name_is_kept(self):
        body = "Solution ici.\nFrom: Jean Dupont <jean@example.com>\n> quoted"
        assert clean_email_reply_body(body) == "Solution ici."


# ---------------------------------------------------------------------------
# 2. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string_returns_empty_string(self):
        assert clean_email_reply_body("") == ""

    def test_whitespace_only_returns_empty_string(self):
        assert clean_email_reply_body("   \n\t\n   ") == ""

    def test_quote_marker_on_first_line_returns_empty(self):
        # Bottom-posted reply: nothing precedes the quote.
        assert clean_email_reply_body("> entirely quoted, nothing new") == ""

    def test_single_char_gt_line_returns_empty(self):
        assert clean_email_reply_body(">") == ""

    def test_no_trailing_newline_still_processed(self):
        assert clean_email_reply_body("solution sans retour à la ligne final") == "solution sans retour à la ligne final"

    def test_only_separator_line_returns_empty(self):
        assert clean_email_reply_body("----") == ""

    def test_three_dashes_does_not_match_separator_regex(self):
        # Regex requires {4,} - exactly 3 dashes must NOT be treated as a separator.
        body = "texte avant\n---\ntexte après"
        result = clean_email_reply_body(body)
        assert "texte avant" in result
        assert "---" in result  # kept as ordinary content, not a break marker

    def test_leading_and_trailing_blank_lines_are_stripped_from_result(self):
        body = "\n\n  solution  \n\n"
        assert clean_email_reply_body(body) == "solution"

    def test_crlf_line_endings_are_handled_like_lf(self):
        body = "Solution ici.\r\n> quoted\r\nmore quoted"
        assert clean_email_reply_body(body) == "Solution ici."

    def test_bare_cr_line_endings_are_handled_like_lf(self):
        body = "Solution ici.\r> quoted"
        assert clean_email_reply_body(body) == "Solution ici."


# ---------------------------------------------------------------------------
# 3. False-positive robustness (legitimate content wrongly truncated)
# ---------------------------------------------------------------------------

class TestFalsePositiveRobustness:
    def test_legit_markdown_blockquote_mid_message_is_not_fully_lost(self):
        """
        Standard email-quoting convention: a line starting with '>' is
        always treated as quoted content, by design - this is intentional,
        universal behavior, not a bug (changing it would risk the opposite,
        worse failure mode: real quoted history leaking through).
        """
        body = "Voici le correctif :\n> Attention: sauvegardez avant de continuer\nRedémarrez ensuite le service."
        result = clean_email_reply_body(body)
        assert result == "Voici le correctif :"

    def test_signature_separator_swallows_legit_signature_block(self):
        """
        Documented heuristic trade-off, not a bug: 4+ dashes/underscores/
        equals alone on a line is treated as a quote separator, which also
        catches a plain visual divider in a signature block.
        """
        body = "Merci de relancer le service.\n----\nJean Dupont\nSupport Level 2"
        result = clean_email_reply_body(body)
        assert result == "Merci de relancer le service."

    def test_from_colon_in_ordinary_sentence_is_no_longer_a_false_positive(self):
        """
        Regression test for the fixed "From:"/"De :" false positive: the
        quoted-header regex now requires the email/bracket token to end the
        line, so an ordinary sentence that merely starts with "De : " and
        mentions an address mid-sentence is kept intact.
        """
        body = "De : notre point de vue technique <support@example.com>, le souci vient du DNS."
        result = clean_email_reply_body(body)
        assert result == body

    def test_real_header_line_with_only_address_is_still_stripped(self):
        # The fix must not regress detection of an actual bare header line.
        body = "Solution.\nDe : support@example.com"
        assert clean_email_reply_body(body) == "Solution."


# ---------------------------------------------------------------------------
# 4. Type / null handling
# ---------------------------------------------------------------------------

class TestTypeHandling:
    def test_none_input_returns_empty_string(self):
        # None means "no body" - consistent with the "nothing to resolve"
        # contract already used for an empty/whitespace-only body.
        assert clean_email_reply_body(None) == ""

    def test_integer_input_raises_type_error(self):
        with pytest.raises(TypeError):
            clean_email_reply_body(12345)

    def test_list_input_raises_type_error(self):
        with pytest.raises(TypeError):
            clean_email_reply_body(["not", "a", "string"])

    def test_bytes_input_raises_type_error(self):
        with pytest.raises(TypeError):
            clean_email_reply_body(b"some bytes content")

    def test_type_error_message_names_the_offending_type(self):
        with pytest.raises(TypeError, match="int"):
            clean_email_reply_body(12345)


# ---------------------------------------------------------------------------
# 5. Data-integrity / security findings
# ---------------------------------------------------------------------------

class TestDataIntegrityFindings:
    def test_zero_width_space_before_quote_marker_is_detected(self):
        """
        Regression test for the fixed critical bug: a zero-width space
        (U+200B) placed before '>' used to defeat quote detection entirely,
        leaking quoted thread history into the ticket solution and the
        knowledge base.
        """
        zwsp = "​"
        body = f"Fixed.\n{zwsp}> old quoted content that should never leak through"
        result = clean_email_reply_body(body)
        assert "old quoted content" not in result
        assert result == "Fixed."

    def test_other_invisible_characters_before_quote_marker_are_also_detected(self):
        for invisible in ("‌", "‍", "⁠", "﻿"):
            body = f"Fixed.\n{invisible}> old quoted content"
            result = clean_email_reply_body(body)
            assert "old quoted content" not in result, f"bypassed via U+{ord(invisible):04X}"

    def test_nbsp_before_quote_marker_is_still_detected(self):
        # NBSP (U+00A0) is whitespace to Python's str.strip(), so this was
        # already safe before the fix - kept as an explicit regression guard.
        nbsp = " "
        body = f"Fixed.\n{nbsp}> old quoted content"
        result = clean_email_reply_body(body)
        assert "old quoted content" not in result

    def test_invisible_characters_are_not_stripped_from_kept_content(self):
        # The detection-only stripping must never alter text that is
        # actually retained in the result.
        zwsp = "​"
        body = f"So{zwsp}lution valide"
        assert clean_email_reply_body(body) == body

    def test_unicode_line_separator_does_not_fragment_a_legit_sentence(self):
        """
        Regression test: str.splitlines() used to also split on U+2028
        (LINE SEPARATOR), fragmenting one legitimate sentence into two
        independently-matched "lines" and silently truncating the reply.
        clean_email_reply_body now only splits on \\r\\n / \\r / \\n.
        """
        body = "Contactez notre équipe  pour plus d'infos"
        result = clean_email_reply_body(body)
        assert result == body

    def test_result_never_contains_quote_marker_prefix_for_plain_gt(self):
        body = "Solution ici.\n> historique cité"
        result = clean_email_reply_body(body)
        assert ">" not in result
        assert "historique cité" not in result


# ---------------------------------------------------------------------------
# 6. Performance / pathological input
# ---------------------------------------------------------------------------

class TestPathologicalInput:
    def test_many_short_lines_completes_quickly(self):
        body = "\n".join(f"ligne légitime numéro {i}" for i in range(50_000))
        start = time.monotonic()
        result = clean_email_reply_body(body)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"took {elapsed:.2f}s for 50k lines - possible perf regression"
        assert result.startswith("ligne légitime numéro 0")

    def test_single_very_long_line_completes_quickly(self):
        body = "a" * 5_000_000
        start = time.monotonic()
        result = clean_email_reply_body(body)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"took {elapsed:.2f}s for a 5MB single line - possible perf issue"
        assert result == body

    def test_long_line_ending_near_but_not_matching_wrote_pattern(self):
        # Crafted to maximize backtracking on the '.+wrote:' greedy pattern
        # without ever matching, to rule out catastrophic backtracking.
        body = "On " + ("x" * 200_000) + " nope"
        start = time.monotonic()
        clean_email_reply_body(body)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"took {elapsed:.2f}s - possible catastrophic backtracking"

    def test_long_line_ending_near_but_not_matching_quoted_header_pattern(self):
        # Same idea targeting the new _QUOTED_HEADER_RE.
        body = "From: " + ("x" * 200_000) + " not an address"
        start = time.monotonic()
        clean_email_reply_body(body)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"took {elapsed:.2f}s - possible catastrophic backtracking"


# ---------------------------------------------------------------------------
# 7. Purity / determinism
# ---------------------------------------------------------------------------

class TestPurity:
    def test_function_does_not_mutate_input_string(self):
        body = "solution\n> quoted"
        body_copy = body
        clean_email_reply_body(body)
        assert body == body_copy

    def test_function_is_deterministic_across_repeated_calls(self):
        body = "solution\n> quoted\nFrom: x@y.com"
        results = {clean_email_reply_body(body) for _ in range(50)}
        assert len(results) == 1
