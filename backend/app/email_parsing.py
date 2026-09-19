"""Reading support reply emails: which ticket a subject refers to, and the reply without the quoted thread."""
import re
from typing import Optional

TICKET_SUBJECT_REGEX = re.compile(r"Ticket\s*#(\d+)", re.IGNORECASE)

# Zero-width characters must not hide a quote marker (e.g. a zero-width space before ">").
# They are stripped for marker detection only, never from the text that is kept.
_INVISIBLE_CHARS_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")

# Quoted email header line, e.g. "From: support@example.com" or
# "De : Jean <jean@example.com>".
_FROM_PREFIX_RE = re.compile(r"^(?:From|De)\s*:\s*(.*)$", re.IGNORECASE)


def _is_quoted_header_line(text: str) -> bool:
    """
    True if `text` is only a "From:" / "De :" header whose value ends in an email address
    (bare or bracketed). A sentence that merely starts that way and mentions an address
    mid-sentence ("De : notre point de vue <a@b.c>, le souci vient du DNS.") must not match.

    Plain string operations on purpose: a single regex with two overlapping unbounded
    quantifiers backtracked catastrophically (a ~200KB line took 100+ seconds; see the ReDoS test).
    """
    match = _FROM_PREFIX_RE.match(text)
    if not match:
        return False
    remainder = match.group(1).strip()
    if not remainder:
        return False

    if remainder.endswith(">"):
        open_idx = remainder.rfind("<")
        if open_idx == -1:
            return False
        inner = remainder[open_idx + 1 : -1]
        return "@" in inner and "<" not in inner and ">" not in inner

    last_token = remainder.split()[-1]
    return "@" in last_token and not last_token.startswith("@") and not last_token.endswith("@")


def clean_email_reply_body(body: Optional[str]) -> str:
    """
    Strip quoted thread history from an email reply: keep what precedes the first quote marker.

    The result is legitimately empty when the marker is on the first line (bottom-posted reply,
    forward): the reply added no content. Callers must treat "" as "nothing to resolve" and never
    fall back to the raw body, which would leak the quoted thread into the ticket solution and the
    knowledge base. `None` gives ""; any other non-str raises TypeError.
    """
    if body is None:
        return ""
    if not isinstance(body, str):
        raise TypeError(f"clean_email_reply_body expects a str or None, got {type(body).__name__!r}")

    # Split on real line breaks only: str.splitlines() also splits on \x0b, \x0c, \x1c-\x1e, \x85
    # and U+2028/2029, which would cut one sentence into several "lines".
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Detect markers on a copy without invisible characters; the original `line` is what is kept.
        detection_text = _INVISIBLE_CHARS_RE.sub("", stripped)

        # Common email quote markers: standard email quote prefix '>'
        if detection_text.startswith(">"):
            break
        # Common email separator lines: 4+ dashes, underscores, or equals alone on a line
        if re.match(r"^[-_=]{4,}\s*$", detection_text):
            break
        # Standard "Original Message" / "Forwarded message" / French equivalents
        if re.search(r"[-_]{2,}\s*(?:Original Message|Message d'origine|Forwarded message|Message transféré)\s*[-_]{2,}", detection_text, re.IGNORECASE):
            break
        # Apple Mail / standard forwarded message headers
        if re.search(r"^(?:Begin forwarded message|Début du message transféré)\s*:", detection_text, re.IGNORECASE):
            break
        # Quoted reply markers like "On ... wrote:" or "Le ... a écrit :"
        if re.search(r"^(On\s+.+wrote:|Le\s+.+a écrit\s*:)", detection_text, re.IGNORECASE):
            break
        # Quoted email header lines like "From: support@..." or "De : Jean <...>"
        if _is_quoted_header_line(detection_text):
            break
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()
