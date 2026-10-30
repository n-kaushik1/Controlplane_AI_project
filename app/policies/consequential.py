"""
Detection of consequential-action requests.

Policy profiles set ``require_human_for_consequential_action``, but the
policy engine needs to be told when a request is one. This module makes
that call from the prompt text. It is deliberately conservative: it only
fires for decisions that materially affect a specific person (credit,
employment, housing, care, legal status), not for generic questions
about those topics.
"""

import re


_PERSON_IMPACTING_VERBS = (
    r"deny|reject|decline|hire|fire|dismiss|terminate|evict|"
    r"diagnose|prescribe|sentence|deport|arrest|revoke"
)

_DECISION_NOUNS = (
    r"loan|mortgage|claim|application|applicant|candidate|employee|"
    r"patient|tenant|visa|benefits?|insurance|medication|treatment|"
    r"scholarship|parole|licen[sc]e"
)

# "should we deny ...", "decide whether to hire ..."
_DECISION_QUESTION = re.compile(
    rf"\b(?:should|shall|can|could|must|do|does|will)\s+"
    rf"(?:we|i|the\s+\w+)\s+(?:{_PERSON_IMPACTING_VERBS})\b"
    rf"|\b(?:decide|determine|recommend)\s+whether\s+(?:to|we\s+should)\s+"
    rf"(?:{_PERSON_IMPACTING_VERBS}|approve)\b",
    re.IGNORECASE,
)

# "deny this loan", "approve the applicant", "reject their claim"
_DECISION_COMMAND = re.compile(
    rf"\b(?:{_PERSON_IMPACTING_VERBS}|approve)\s+"
    rf"(?:this|the|that|his|her|their)\s+(?:\w+\s+){{0,2}}"
    rf"(?:{_DECISION_NOUNS})\b",
    re.IGNORECASE,
)


def is_consequential_action(text: str) -> bool:
    """Return True if ``text`` asks for a decision about a person."""

    if not text or not isinstance(text, str):
        return False

    return bool(
        _DECISION_QUESTION.search(text)
        or _DECISION_COMMAND.search(text)
    )
