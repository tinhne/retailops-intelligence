"""Intent router of the deterministic provider (AI_ARCHITECTURE.md §7.1, §7.2).

No learned components: the behaviour is defined by the tables below and tested phrase by phrase.

1. Normalise (NFC, lower case, collapsed whitespace).
2. Refusals first: write requests, personal data, other stores, forecasts and out-of-scope topics
   are placed with high confidence and answered without any tool or LLM request.
3. Entities: UUIDs, exception references (``EXC-1042``), quoted titles, and identifier-like tokens
   (SKUs, order numbers). Candidates are resolved later by exact lookups through tools.
4. Parameters: severity, exception type, "top N", time window.
5. Scoring: each intent's patterns add their weight; the highest score at or above the threshold
   wins (ties go to the intent listed first). Below the threshold: HELP with low confidence, so a
   live model still gets a chance at the question.
"""

import re
import unicodedata
import uuid
from dataclasses import dataclass, replace
from enum import StrEnum

from app.domains.exceptions.models import ExceptionType, Severity


class Intent(StrEnum):
    ATTENTION_TODAY = "ATTENTION_TODAY"
    TOP_PRIORITY_EXCEPTIONS = "TOP_PRIORITY_EXCEPTIONS"
    OVERDUE_ORDERS = "OVERDUE_ORDERS"
    OVERSELL_RISK_SKUS = "OVERSELL_RISK_SKUS"
    CHANGES_SINCE_YESTERDAY = "CHANGES_SINCE_YESTERDAY"
    EXPLAIN_EXCEPTION = "EXPLAIN_EXCEPTION"
    TEAM_PRIORITIES = "TEAM_PRIORITIES"
    INVESTIGATION_SUMMARY = "INVESTIGATION_SUMMARY"
    NOTE_DRAFT = "NOTE_DRAFT"
    PRODUCT_LOOKUP = "PRODUCT_LOOKUP"
    ORDER_LOOKUP = "ORDER_LOOKUP"
    IMPORT_ISSUES = "IMPORT_ISSUES"
    TRENDS = "TRENDS"
    HELP = "HELP"
    UNSUPPORTED = "UNSUPPORTED"


class Unsupported(StrEnum):
    WRITE_REQUEST = "WRITE_REQUEST"
    PERSONAL_DATA = "PERSONAL_DATA"
    OTHER_STORE = "OTHER_STORE"
    FORECAST = "FORECAST"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class RoutedIntent:
    intent: Intent
    high_confidence: bool
    exception_ids: tuple[uuid.UUID, ...] = ()
    exception_refs: tuple[str, ...] = ()
    quoted: tuple[str, ...] = ()
    identifiers: tuple[str, ...] = ()
    search_terms: tuple[str, ...] = ()
    severities: tuple[Severity, ...] = ()
    exception_types: tuple[ExceptionType, ...] = ()
    limit: int | None = None
    window_days: int | None = None
    unsupported: Unsupported | None = None
    action: str | None = None
    score: int = 0


THRESHOLD = 2
HIGH_CONFIDENCE = 3
MAX_LIMIT = 20

_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_EXC_REF = re.compile(r"\bEXC-\d{3,}\b", re.I)
_QUOTED = re.compile(r"['\"‘“]([^'\"‘’“”]{3,200})['\"’”]")
_IDENTIFIER = re.compile(r"(?<![\w-])#?[A-Za-z0-9][A-Za-z0-9_#-]{2,63}(?![\w-])")

_WRITE = re.compile(
    r"^(?:please\s+|pls\s+|now\s+|go ahead and\s+|(?:can|could|would|will) you\s+(?:please\s+)?)?"
    r"(resolve|assign|reassign|unassign|dismiss|close|acknowledge|ack|reopen|update|change|set"
    r"|delete|remove|import|apply|upload|mark|cancel|refund|adjust|edit|claim|start working on"
    r"|add a note|save|approve|ship|fulfil|fulfill|restock)\b"
)
_PERSONAL = re.compile(
    r"\b(?:e-?mail(?: address)?|phone(?: number)?|home address|mailing address|shipping address"
    r"|personal (?:data|details|information)|customer'?s? (?:name|details|contact))\b"
    r"|\bwho (?:bought|ordered|is the customer)\b"
)
_OTHER_STORE = re.compile(
    r"\b(?:other|another|different|all|every|each) stores?\b|\bswitch (?:to )?(?:the )?store\b"
    r"|\bstore b1?\b|\bcompare (?:the )?stores\b|\bacross stores\b"
)
_FORECAST = re.compile(
    r"\b(?:forecast|predict(?:ion)?|projection|project(?:ed)? (?:sales|demand))\b"
    r"|\bnext (?:week|month|quarter|year)'?s? (?:sales|demand|revenue|orders)\b"
    r"|\bhow (?:much|many) will\b|\bwill (?:we|i) sell\b"
)
_OUT_OF_SCOPE = re.compile(
    r"\bcompetitors?'?s?\b|\bweather\b|\bstock market\b|\bshare price\b|\bwrite (?:me )?a poem\b"
)

# Scoring table: (intent, weight, pattern). The order of intents breaks ties (catalogue order).
_PATTERNS: tuple[tuple[Intent, int, str], ...] = (
    (Intent.ATTENTION_TODAY, 3, r"\bneeds? (?:my |our )?attention\b"),
    (Intent.ATTENTION_TODAY, 2, r"\battention\b"),
    (Intent.ATTENTION_TODAY, 2, r"\burgent\b"),
    (Intent.ATTENTION_TODAY, 2, r"\bwhat'?s (?:going on|happening)\b"),
    (
        Intent.ATTENTION_TODAY,
        2,
        r"\b(?:overview|store status|status of the store|how is the store)\b",
    ),
    (Intent.ATTENTION_TODAY, 2, r"\banything (?:i|we) should (?:know|look at)\b"),
    (Intent.ATTENTION_TODAY, 1, r"\btoday\b"),
    (Intent.TOP_PRIORITY_EXCEPTIONS, 3, r"\b(?:highest|top|most important|biggest)[- ]priority\b"),
    (
        Intent.TOP_PRIORITY_EXCEPTIONS,
        3,
        r"\b(?:critical|biggest|most important|worst|top) "
        r"(?:\d+ )?(?:issues|exceptions|problems)\b",
    ),
    (Intent.TOP_PRIORITY_EXCEPTIONS, 2, r"\bpriority exceptions?\b"),
    (Intent.TOP_PRIORITY_EXCEPTIONS, 2, r"\btop \d+\b"),
    (Intent.TOP_PRIORITY_EXCEPTIONS, 2, r"\bp1\b"),
    (Intent.TOP_PRIORITY_EXCEPTIONS, 1, r"\bexceptions?\b"),
    (Intent.OVERDUE_ORDERS, 3, r"\boverdue\b"),
    (Intent.OVERDUE_ORDERS, 3, r"\blate (?:orders?|shipments?|deliveries)\b"),
    (Intent.OVERDUE_ORDERS, 3, r"\bpast (?:their |its |the )?ship[- ]?by\b"),
    (Intent.OVERDUE_ORDERS, 2, r"\bnot (?:yet )?shipped\b"),
    (Intent.OVERDUE_ORDERS, 1, r"\borders\b"),
    (Intent.OVERSELL_RISK_SKUS, 3, r"\boversell(?:ing)?\b"),
    (Intent.OVERSELL_RISK_SKUS, 3, r"\boversold\b"),
    (Intent.OVERSELL_RISK_SKUS, 2, r"\brun(?:ning)? out\b"),
    (Intent.OVERSELL_RISK_SKUS, 1, r"\b(?:at risk|risk)\b"),
    (Intent.OVERSELL_RISK_SKUS, 1, r"\bskus\b"),
    (Intent.CHANGES_SINCE_YESTERDAY, 3, r"\bsince yesterday\b"),
    (Intent.CHANGES_SINCE_YESTERDAY, 3, r"\bwhat'?s new\b"),
    (Intent.CHANGES_SINCE_YESTERDAY, 2, r"\b(?:what|anything) (?:has )?changed\b"),
    (Intent.CHANGES_SINCE_YESTERDAY, 2, r"\bwhat happened\b"),
    (Intent.CHANGES_SINCE_YESTERDAY, 2, r"\bnew since\b"),
    (Intent.CHANGES_SINCE_YESTERDAY, 1, r"\byesterday\b"),
    (Intent.EXPLAIN_EXCEPTION, 2, r"\bwhy (?:is|was|does|did|has)\b"),
    (Intent.EXPLAIN_EXCEPTION, 2, r"\bexplain\b"),
    (Intent.EXPLAIN_EXCEPTION, 2, r"\bhow (?:was|is) (?:its |the |this )?priority\b"),
    (Intent.EXPLAIN_EXCEPTION, 2, r"\bthis exception\b"),
    (Intent.TEAM_PRIORITIES, 2, r"\bteam\b"),
    (Intent.TEAM_PRIORITIES, 2, r"\bpriori(?:ti[sz]e|ties)\b"),
    (Intent.TEAM_PRIORITIES, 3, r"\bplan (?:for|of) (?:today|the day)\b"),
    (
        Intent.TEAM_PRIORITIES,
        3,
        r"\bwhat should (?:we|i|the team) (?:do|work on|focus on|tackle)"
        r"(?: first| next)?\b",
    ),
    (Intent.TEAM_PRIORITIES, 3, r"\b(?:order of work|work on first)\b"),
    (Intent.PRODUCT_LOOKUP, 3, r"\bstock (?:for|of|level|levels)\b"),
    (Intent.PRODUCT_LOOKUP, 3, r"\b(?:inventory|on hand|available) (?:for|of)\b"),
    (Intent.PRODUCT_LOOKUP, 3, r"\bhow many .* (?:in stock|left|on hand)\b"),
    (Intent.PRODUCT_LOOKUP, 2, r"\btell me about\b"),
    (Intent.PRODUCT_LOOKUP, 1, r"\b(?:product|sku|item)\b"),
    (Intent.ORDER_LOOKUP, 3, r"\b(?:status of|where is|look up|show me|find) order\b"),
    (Intent.ORDER_LOOKUP, 3, r"\border (?:number |no\.? |#)?[a-z]*-?\d"),
    (Intent.IMPORT_ISSUES, 3, r"\b(?:imports?|uploads?|csv)\b"),
    (Intent.IMPORT_ISSUES, 1, r"\b(?:errors?|rejected|failed)\b"),
    (Intent.TRENDS, 3, r"\btrend(?:s|ing|ed)?\b"),
    (Intent.TRENDS, 2, r"\bover time\b"),
    (Intent.TRENDS, 2, r"\b(?:sales|gmv|orders placed|units sold)\b"),
    (Intent.TRENDS, 2, r"\bhow (?:have|did|has|are) .* (?:gone|going|trended|changed|developed)\b"),
    (Intent.TRENDS, 1, r"\b(?:this|last|past) (?:week|month)\b"),
    (Intent.TRENDS, 1, r"\blast \d+ days\b"),
    (Intent.HELP, 3, r"\bhelp\b"),
    (Intent.HELP, 3, r"\bwhat can (?:you|i) (?:do|ask)\b"),
)
_COMPILED = tuple((intent, weight, re.compile(p)) for intent, weight, p in _PATTERNS)
_ORDER = list(Intent)

_TYPE_WORDS: tuple[tuple[str, ExceptionType], ...] = (
    (r"\boversell(?:ing)?(?: risk)?\b", ExceptionType.INVENTORY_OVERSELL_RISK),
    (r"\boversold\b", ExceptionType.INVENTORY_OVERSOLD),
    (r"\bout of stock\b", ExceptionType.INVENTORY_OUT_OF_STOCK),
    (r"\breorder\b", ExceptionType.INVENTORY_BELOW_REORDER_POINT),
    (r"\b(?:overdue|late shipments?)\b", ExceptionType.ORDER_FULFILLMENT_OVERDUE),
    (r"\bstalled\b", ExceptionType.ORDER_STALLED_AFTER_PAYMENT),
    (r"\brefunds?\b", ExceptionType.ORDER_REFUND_PENDING),
    (r"\bmismatch(?:es)?\b", ExceptionType.DATA_ORDER_TOTAL_MISMATCH),
    (r"\bnegative (?:stock|on[- ]hand)\b", ExceptionType.DATA_NEGATIVE_ON_HAND),
)
_SEVERITY_WORDS = (
    (r"\bcritical\b", Severity.CRITICAL),
    (r"\bhigh[- ]severity\b|\bseverity (?:is )?high\b", Severity.HIGH),
    (r"\bmedium[- ]severity\b|\bseverity (?:is )?medium\b", Severity.MEDIUM),
    (r"\blow[- ]severity\b|\bseverity (?:is )?low\b", Severity.LOW),
)
_TOP_N = re.compile(r"\btop (\d{1,3})\b|\b(\d{1,3}) (?:most|highest|biggest|top)\b")
_LAST_N_DAYS = re.compile(r"\b(?:last|past) (\d{1,3}) days\b")
_STOP_WORDS = frozenset(
    {
        *("a", "an", "the", "of", "for", "about", "me", "tell", "show", "what", "is", "are"),
        *("how", "many", "much", "stock", "level", "levels", "sku", "skus", "product"),
        *("products", "item", "items", "in", "on", "hand", "left", "do", "we", "have", "our"),
        *("my", "please", "inventory", "available", "status"),
    }
)
_SEARCH_TRIGGER = re.compile(r"\b(?:about|for|of)\s+(?:the\s+)?(.+)$")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip()


def _identifiers(original: str) -> tuple[str, ...]:
    """SKU- or order-number-like tokens: a digit plus a letter or hyphen (``KHK-10481``), or an
    upper-case hyphenated code (``KHK-BCB-L``)."""
    found: list[str] = []
    for match in _IDENTIFIER.finditer(original):
        token = match.group(0).lstrip("#").rstrip(".,;:!?")
        has_digit = any(c.isdigit() for c in token)
        has_letter = any(c.isalpha() for c in token)
        coded = (has_digit and (has_letter or "-" in token)) or (
            has_letter and "-" in token and token == token.upper()
        )
        if len(token) >= 3 and coded and token not in found:
            found.append(token)
    return tuple(found)


def _search_terms(text: str) -> tuple[str, ...]:
    """Product search phrases: the words after "about/for/of", then the longest single word."""
    match = _SEARCH_TRIGGER.search(text.rstrip("?.! "))
    phrase = match.group(1) if match else text
    words = [w for w in re.findall(r"[a-z][a-z0-9'-]+", phrase) if w not in _STOP_WORDS]
    terms: list[str] = []
    if words:
        terms.append(" ".join(words)[:100])
        longest = max(words, key=len)
        if len(longest) >= 4 and longest not in terms:
            terms.append(longest)
    return tuple(t for t in terms if len(t) >= 2)


def _window_days(text: str) -> int | None:
    match = _LAST_N_DAYS.search(text)
    if match:
        return max(1, min(int(match.group(1)), 60))
    if re.search(r"\b(?:since )?yesterday\b", text):
        return 2
    if re.search(r"\b(?:this|last|past) week\b", text):
        return 7
    if re.search(r"\b(?:this|last|past) month\b", text):
        return 30
    if re.search(r"\btoday\b", text):
        return 1
    return None


def route(question: str, *, context_exception_id: uuid.UUID | None = None) -> RoutedIntent:
    original = question.strip()
    text = normalise(original)

    exception_ids = tuple(uuid.UUID(m) for m in dict.fromkeys(_UUID.findall(original)))
    refs = tuple(dict.fromkeys(m.upper() for m in _EXC_REF.findall(original)))
    quoted = tuple(dict.fromkeys(q.strip() for q in _QUOTED.findall(original) if q.strip()))
    unquoted = _QUOTED.sub(" ", original)
    unquoted = _EXC_REF.sub(" ", _UUID.sub(" ", unquoted))
    scoring_text = normalise(unquoted)
    identifiers = _identifiers(unquoted)

    severities = tuple(s for p, s in _SEVERITY_WORDS if re.search(p, scoring_text))
    types = tuple(t for p, t in _TYPE_WORDS if re.search(p, scoring_text))
    top = _TOP_N.search(scoring_text)
    limit = min(int(top.group(1) or top.group(2)), MAX_LIMIT) if top else None
    base = RoutedIntent(
        intent=Intent.HELP,
        high_confidence=False,
        exception_ids=exception_ids,
        exception_refs=refs,
        quoted=quoted,
        identifiers=identifiers,
        severities=severities,
        exception_types=types,
        limit=limit if limit else None,
        window_days=_window_days(scoring_text),
    )

    write = _WRITE.search(text)
    refusals = (
        (write is not None, Unsupported.WRITE_REQUEST),
        (_PERSONAL.search(text) is not None, Unsupported.PERSONAL_DATA),
        (_OTHER_STORE.search(text) is not None, Unsupported.OTHER_STORE),
        (_FORECAST.search(text) is not None, Unsupported.FORECAST),
        (_OUT_OF_SCOPE.search(text) is not None, Unsupported.OUT_OF_SCOPE),
    )
    for matched, reason in refusals:
        if matched:
            return replace(
                base,
                intent=Intent.UNSUPPORTED,
                high_confidence=True,
                unsupported=reason,
                action=write.group(1) if write and reason is Unsupported.WRITE_REQUEST else None,
                score=HIGH_CONFIDENCE,
            )

    scores = dict.fromkeys(Intent, 0)
    for intent, weight, pattern in _COMPILED:
        if pattern.search(scoring_text):
            scores[intent] += weight
    if exception_ids or refs or quoted:
        scores[Intent.EXPLAIN_EXCEPTION] += 3
    if identifiers:
        for intent in (Intent.PRODUCT_LOOKUP, Intent.ORDER_LOOKUP):
            if scores[intent]:
                scores[intent] += 1
    best = max(_ORDER, key=lambda i: (scores[i], -_ORDER.index(i)))
    score = scores[best]

    names_entity = bool(exception_ids or refs or quoted or identifiers)
    if (
        context_exception_id is not None
        and not names_entity
        and (best in (Intent.EXPLAIN_EXCEPTION, Intent.TEAM_PRIORITIES) or score < THRESHOLD)
    ):
        # Context shortcut: "why is this critical?" inside an exception conversation.
        return replace(
            base,
            intent=Intent.EXPLAIN_EXCEPTION,
            high_confidence=True,
            exception_ids=(context_exception_id,),
            score=max(score, HIGH_CONFIDENCE),
        )
    if score < THRESHOLD:
        return replace(base, score=score)
    return replace(
        base,
        intent=best,
        high_confidence=score >= HIGH_CONFIDENCE,
        search_terms=_search_terms(scoring_text) if best is Intent.PRODUCT_LOOKUP else (),
        score=score,
    )


def table_text() -> str:
    """The routing table as text, hashed into ``prompts.lock.json`` (deterministic.router@N)."""
    lines = [f"{i.value}|{w}|{p}" for i, w, p in _PATTERNS]
    lines += [f"type|{p}|{t.value}" for p, t in _TYPE_WORDS]
    lines += [f"severity|{p}|{s.value}" for p, s in _SEVERITY_WORDS]
    lines += [
        f"refusal|{r.pattern}" for r in (_WRITE, _PERSONAL, _OTHER_STORE, _FORECAST, _OUT_OF_SCOPE)
    ]
    return "\n".join(lines)
