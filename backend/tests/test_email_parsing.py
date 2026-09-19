import pytest

from app.email_parsing import find_ticket_id


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("Re: [Ticket #123] Nouvelle demande de support de @alice", 123),
        ("[Ticket #7] Résolu via TELEGRAM", 7),
        ("ticket #42", 42),  # case-insensitive
        ("TICKET#5", 5),  # the space is optional
        ("Fwd: [Ticket #12] and also Ticket #99", 12),  # the first one wins
        ("Re: pas de référence", None),
        ("Ticket #", None),
        ("", None),
        (None, None),  # Brevo items may carry no subject
    ],
)
def test_find_ticket_id(subject, expected):
    assert find_ticket_id(subject) == expected
