"""Smart Context Resolver for Web Search Queries and Database Follow-ups.

Determines whether a user message is an independent question or a follow-up
to a previous topic.  When it IS a follow-up, resolves pronouns and generates
a standalone query.  When it is NOT, returns only the current message.

Rules implemented:
  1. New independent questions -> search query = current message only.
  2. Follow-up questions -> resolve topic anchor, produce standalone query.
  3. Topic-change detection -> detect when user switches topics.
  4. Pronoun/reference resolution -> map he/she/it/iska/ye to topic anchor.
  5. Database context follow-ups -> preserve entity references from prior DB results.
  6. Cross-domain context -> detect when follow-ups bridge knowledge + database.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Follow-up phrase patterns (English + Hindi/Hinglish)
# ---------------------------------------------------------------------------
FOLLOW_UP_PHRASES: List[str] = [
    # English
    r"\btell me more\b",
    r"\bmore info(?:rmation)?\b",
    r"\bexplain (?:this|it|more|in)\b",
    r"\bgive me (?:an )?example\b",
    r"\bwhy is (?:it|this) important\b",
    r"\bwhat happened next\b",
    r"\bhow does (?:it|this) work\b",
    r"\bwhat about (?:its|his|her|their)\b",
    r"\bhow long has\b",
    r"\bwhere is (?:it|this|he|she)\b",
    r"\bhow many (?:of|are)\b",
    r"\bcan you (?:explain|elaborate|clarify)\b",
    r"\bwhat do you mean\b",
    r"\bcan you (?:speak|write|translate)\b.*\b(hindi|english|hinglish)\b",
    # Database-specific follow-ups
    r"\bwhat about\b",
    r"\bhow about\b",
    r"\band for\b",
    r"\band the\b",
    r"\bsame (?:for|as)\b",
    r"\bnow (?:show|list|give|tell)\b",
    r"\bnext\b",
    r"\balso\b",
    r"\bwith (?:this|that|these|those)\b",
    r"\bbreak (?:it|that|this) down\b",
    r"\bcompare (?:it|that|this|them)\b",
    r"\bhow (?:does|do) (?:it|that|this) compare\b",
    r"\bwhat's (?:the|its) (?:difference|trend|pattern)\b",
    r"\bdeeper\b",
    r"\bmoredetail\b",
    # Hindi / Hinglish
    r"\biske baare mein aur\b",
    r"\baur batao\b",
    r"\baur .*batao\b",
    r"\baur explain karo\b",
    r"\baur bataye\b",
    r"\bphir se batao\b",
    r"\bdetail mein batao\b",
    r"\biska simple example do\b",
    r"\bsamajh nahi aaya\b",
    r"\bsamajh nhi aaya\b",
    r"\bthoda aur batao\b",
    r"\bthoda detail mein batao\b",
    r"\bye kaise\b",
    r"\biske baare mein\b",
    r"\biska advantage\b",
    r"\biske baad\b",
    r"\buska kya\b",
    r"\buske baare\b",
    r"\bkyun hota hai\b",
    r"\bkyaise kaam\b",
    r"\bkaise karta hai\b",
    r"\bkyu zaroorat\b",
]

FOLLOW_UP_RE = re.compile(
    "|".join(FOLLOW_UP_PHRASES), re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Pronouns / reference words that imply a follow-up
# ---------------------------------------------------------------------------
PRONOUN_RE = re.compile(
    r"\b(it|this|that|he|she|they|his|her|its|them|"
    r"iska|iske|uska|uske|ye|woh|unka|unke)\b",
    re.IGNORECASE,
)

# Database result entity reference patterns (names extracted from prior results)
ENTITY_REFERENCE_RE = re.compile(
    r"\b(that|the above|the first|the top|the previous|the last)\b",
    re.IGNORECASE,
)

# Comparison follow-up patterns (e.g., "How much higher is it than Sales?")
COMPARISON_FOLLOWUP_RE = re.compile(
    r"\b(how much|what|by how much|compared to|versus|vs|than)\b.*\b(it|that|this|he|she|they)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _word_count(text: str) -> int:
    return len(text.split())


def is_follow_up(message: str) -> bool:
    """Return True if the message is clearly a follow-up to a prior topic.

    Follow-up signals:
    - Contains explicit follow-up phrases ("tell me more", "iska simple example do")
    - Is very short (<=4 words) AND contains a pronoun reference ("it", "this", "iska")
    - Contains database comparison patterns ("How much higher is it than Sales?")
    - Contains entity reference patterns ("What about the first one?")
    """
    norm = _normalize(message)

    # 1. Explicit follow-up phrases -> definitely a follow-up.
    if FOLLOW_UP_RE.search(norm):
        return True

    # 2. Very short message with pronoun -> likely follow-up.
    wc = _word_count(norm)
    has_pronoun = bool(PRONOUN_RE.search(norm))

    if wc <= 4 and has_pronoun:
        return True

    # 3. Short message (<=5 words) with a pronoun -> likely follow-up.
    if wc <= 5 and has_pronoun:
        return True

    # 4. Database comparison follow-ups
    if COMPARISON_FOLLOWUP_RE.search(norm):
        return True

    # 5. Entity reference patterns
    if ENTITY_REFERENCE_RE.search(norm) and wc <= 6:
        return True

    return False


def detect_topic_change(message: str, previous_user: Optional[str]) -> bool:
    """Detect whether the user has switched to a completely new topic.

    Returns True if the new message is clearly on a different topic than
    the previous user message.
    """
    if not previous_user:
        return True  # No prior context -> treat as new.

    norm_msg = _normalize(message)
    norm_prev = _normalize(previous_user)

    # If the new message contains follow-up phrases, it's NOT a topic change.
    if is_follow_up(message):
        return False

    # Extract content words (non-stopwords) from both messages.
    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "what", "how", "why",
        "who", "when", "where", "which", "do", "does", "did", "have", "has",
        "had", "can", "could", "should", "would", "will", "shall", "may",
        "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
        "about", "into", "through", "during", "before", "after", "above",
        "below", "between", "under", "again", "then", "once", "here",
        "there", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "no", "not", "only", "same", "than",
        "too", "very", "just", "kya", "hai", "ka", "ke", "ki", "ko",
        "mein", "se", "aur", "bhi", "ya", "nahi", "ho", "ye", "wo",
        "yeh", "woh", "kaise", "kyun", "kab", "kaun",
    }

    def _content_words(text: str) -> set:
        return {
            w for w in re.findall(r"[a-z0-9]+", text)
            if w not in stopwords and len(w) > 2
        }

    msg_words = _content_words(norm_msg)
    prev_words = _content_words(norm_prev)

    if not msg_words:
        return False  # Can't determine -> assume not a change.

    # If there is significant overlap in content words -> same topic.
    if prev_words:
        overlap = len(msg_words & prev_words)
        min_len = min(len(msg_words), len(prev_words))
        if min_len > 0 and overlap / min_len >= 0.3:
            return False  # Enough overlap -> same topic.

    # No meaningful overlap -> topic change.
    return True


def find_topic_anchor(history: List[Dict[str, str]]) -> Optional[str]:
    """Find the most recent substantive user message as a topic anchor.

    Walks backwards through history looking for a user message that is
    substantive enough to serve as a topic (not a follow-up itself).
    """
    user_messages = [
        m.get("content", "")
        for m in history
        if m.get("role") == "user"
    ]

    # Walk backwards, skip follow-ups.
    for msg in reversed(user_messages[:-1]):  # exclude current
        if not is_follow_up(msg) and _word_count(msg) > 3:
            return msg

    # Fallback: return the most recent user message regardless.
    if len(user_messages) >= 2:
        return user_messages[-2]

    return None


def _extract_named_entity(text: str) -> Optional[str]:
    """Try to extract the main subject/named entity from a message.

    Simple heuristic: take capitalized words (except sentence-initial).
    """
    words = text.split()
    entities = []
    for i, w in enumerate(words):
        # Skip very first word (likely sentence-initial capitalization).
        if i == 0:
            continue
        # Capitalized word that isn't a common start-of-sentence word.
        if w[0].isupper() and len(w) > 1:
            entities.append(w)
    if entities:
        return " ".join(entities)
    return None


def extract_entities_from_result(result: Dict[str, Any]) -> List[str]:
    """Extract entity names from a prior database result.

    Scans result rows for name-like columns and returns them as
    entity references for follow-up resolution.
    """
    entities: List[str] = []
    rows = result.get("rows", [])
    if not isinstance(rows, list):
        return entities

    for row in rows[:10]:  # Limit to first 10 rows
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            if ("name" in k or k.endswith("_name")) and v is not None:
                entity = str(v).strip()
                if entity and entity not in entities:
                    entities.append(entity)
    return entities


def resolve_pronouns(message: str, topic_anchor: str) -> str:
    """Replace pronouns/references in the message with the topic anchor subject.

    This is a simple heuristic resolver — not full coreference resolution.
    """
    norm_msg = _normalize(message)

    # If the message already has a clear named entity, don't resolve.
    entity = _extract_named_entity(message)
    if entity:
        return message

    # If the message is a follow-up and short, resolve pronouns.
    if is_follow_up(message) and _word_count(norm_msg) <= 10:
        # Extract the main subject from the topic anchor.
        anchor_entity = _extract_named_entity(topic_anchor)
        if anchor_entity:
            return message  # Keep original but the caller will combine.

    return message


def resolve_database_followup(
    message: str,
    history: List[Dict[str, str]],
    prior_result: Optional[Dict[str, Any]] = None,
) -> str:
    """Resolve a database follow-up question using prior context.

    Handles cases like:
    - "How much higher is it than Sales?" after "Engineering has the highest count at 45"
    - "What about the other departments?" after showing department results
    - "Break it down by month" after a total query

    Returns a resolved standalone question for the query planner.
    """
    norm = _normalize(message)

    # Extract entities from prior result
    entities: List[str] = []
    if prior_result:
        entities = extract_entities_from_result(prior_result)

    # Get prior user question for context
    prior_user = [
        m.get("content", "")
        for m in history
        if m.get("role") == "user"
    ]
    previous_question = prior_user[-2] if len(prior_user) >= 2 else None

    # Handle "What about X?" pattern — X is likely an entity from prior results
    what_about_match = re.search(r"what about (\w+)", norm)
    if what_about_match:
        target = what_about_match.group(1)
        # Check if target matches a prior entity
        for entity in entities:
            if target.lower() in entity.lower() or entity.lower() in target.lower():
                # Reconstruct the query context
                if previous_question:
                    return f"{previous_question} for {entity}"
                return f"details for {entity}"

    # Handle comparison follow-ups ("How much higher is it than X?")
    comparison_match = re.search(
        r"how much (?:higher|lower|more|less|bigger|smaller) is (?:it|that|this) than (\w+)",
        norm,
    )
    if comparison_match:
        other = comparison_match.group(1)
        if previous_question and entities:
            # Reconstruct as a comparison query
            return f"compare {entities[0]} with {other} in {previous_question}"

    # Handle "Break it down by X" pattern
    breakdown_match = re.search(r"break (?:it|that|this) down by (\w+)", norm)
    if breakdown_match:
        dimension = breakdown_match.group(1)
        if previous_question:
            return f"{previous_question} grouped by {dimension}"

    # Handle "Show me the same for X" pattern
    same_for_match = re.search(r"same (?:for|as) (\w+)", norm)
    if same_for_match:
        target = same_for_match.group(1)
        if previous_question:
            return f"{previous_question} for {target}"

    # Handle "Now show/list/give me X" pattern
    now_match = re.search(r"now (?:show|list|give|tell) (?:me )?(.+)", norm)
    if now_match:
        new_request = now_match.group(1).strip()
        if previous_question:
            return f"{new_request} from the same data as {previous_question}"

    # If we have entities from prior result and the message is short,
    # try to infer the context
    if entities and _word_count(norm) <= 6:
        # Check for comparison patterns
        if any(w in norm for w in ("compare", "vs", "versus", "difference", "higher", "lower")):
            return f"compare {' and '.join(entities[:3])} from the previous query"

    # Default: return original message
    return message


def build_web_search_query(
    message: str,
    history: List[Dict[str, str]],
) -> str:
    """Build the optimal search query for a web search.

    This is the main entry point.  It determines:
    1. Is this a follow-up or independent question?
    2. If follow-up -> resolve context and produce standalone query.
    3. If independent -> use only the current message.

    Returns a clean, standalone search query.
    """
    norm_msg = _normalize(message)

    # Get previous user messages (excluding current).
    prior_user = [
        m.get("content", "")
        for m in history
        if m.get("role") == "user"
    ][:-1]

    # If no prior messages, the current message IS the query.
    if not prior_user:
        return message.strip()

    last_prior = prior_user[-1]

    # Check if this is a follow-up.
    if not is_follow_up(message):
        # Not a follow-up -> check for topic change.
        if detect_topic_change(message, last_prior):
            # Topic changed -> search only the current message.
            return message.strip()
        else:
            # Same topic but not a follow-up -> still use current message
            # as it likely already contains the relevant keywords.
            return message.strip()

    # This IS a follow-up -> resolve context.
    topic_anchor = find_topic_anchor(history)

    if not topic_anchor:
        return message.strip()

    # Extract the main entity/subject from the topic anchor.
    anchor_entity = _extract_named_entity(topic_anchor)
    if not anchor_entity:
        # Can't extract entity -> just use the anchor as context.
        return f"{topic_anchor} {message}".strip()

    # Build a resolved query by combining the entity with the follow-up.
    # Remove pronouns from the follow-up and replace with the entity.
    resolved = _combine_follow_up(message, topic_anchor, anchor_entity)
    return resolved.strip()


def _combine_follow_up(
    follow_up: str,
    topic_anchor: str,
    anchor_entity: str,
) -> str:
    """Combine a follow-up question with its topic anchor into a standalone query."""
    norm_follow_up = _normalize(follow_up)
    norm_anchor = _normalize(topic_anchor)

    # Simple resolution: if the follow-up contains a pronoun reference,
    # replace it with the anchor entity.
    pronoun_patterns = [
        (r"\bit\b", anchor_entity),
        (r"\bthis\b", anchor_entity),
        (r"\bthat\b", anchor_entity),
        (r"\bhe\b", anchor_entity),
        (r"\bshe\b", anchor_entity),
        (r"\bhis\b", f"{anchor_entity}'s"),
        (r"\bher\b", f"{anchor_entity}'s"),
        (r"\bits\b", f"{anchor_entity}'s"),
        (r"\bthey\b", anchor_entity),
        (r"\bthem\b", anchor_entity),
        (r"\biska\b", anchor_entity),
        (r"\biske\b", anchor_entity),
        (r"\buska\b", anchor_entity),
        (r"\buske\b", anchor_entity),
        (r"\bye\b", anchor_entity),
        (r"\bwoh\b", anchor_entity),
        (r"\bunka\b", anchor_entity),
        (r"\bunke\b", anchor_entity),
    ]

    resolved = follow_up
    for pattern, replacement in pronoun_patterns:
        new_resolved = re.sub(pattern, replacement, resolved, flags=re.IGNORECASE)
        if new_resolved != resolved:
            resolved = new_resolved
            break  # Replace first pronoun match only.

    # If no pronouns were replaced, prepend the anchor entity.
    if resolved == follow_up:
        # Clean up the follow-up: remove Hindi/English filler phrases.
        cleaned = _clean_follow_up(norm_follow_up)
        if cleaned:
            return f"{anchor_entity} {cleaned}"
        return f"{anchor_entity} {follow_up}"

    return resolved


def _clean_follow_up(text: str) -> str:
    """Remove common follow-up filler phrases to extract the core question."""
    fillers = [
        r"^iske baare mein aur ",
        r"^aur batao",
        r"^aur explain karo",
        r"^tell me more",
        r"^more info(?:rmation)?",
        r"^explain (?:this|it|more)\b",
        r"^give me (?:an )?example",
        r"^iska simple example do",
        r"^samajh nahi aaya",
        r"^samajh nhi aaya",
        r"^thoda aur batao",
        r"^thoda detail mein batao",
        r"^detail mein batao",
        r"^phir se batao",
    ]
    cleaned = text
    for filler in fillers:
        cleaned = re.sub(filler, "", cleaned).strip()

    # Remove leading connectors.
    cleaned = re.sub(r"^[,;\s]+", "", cleaned).strip()
    return cleaned


def extract_search_category(message: str) -> str:
    """Classify the web search into a category for query optimization."""
    norm = _normalize(message)

    if re.search(r"\b(weather|temperature|forecast|mausam)\b", norm):
        return "weather"
    if re.search(
        r"\b(price|rate|cost|kab|kitna)\b.*\b(bitcoin|ethereum|btc|eth|crypto|gold|silver|nifty|sensex|stock|share)\b"
        r"|\b(bitcoin|ethereum|btc|eth|crypto|gold|silver|nifty|sensex|stock|share)\b.*\b(price|rate|cost)\b",
        norm,
    ):
        return "price"
    if re.search(r"\b(news|latest|update|happened|breaking|announce|launch|release)\b", norm):
        return "news"
    if re.search(r"\b(ceo|cto|founder|president|director|head|leader)\b", norm):
        return "person"
    if re.search(r"\b(version|release|update|launch)\b.*\b(python|node|java|react|angular|vue|php|rust|go)\b"
                  r"|\b(python|node|java|react|angular|vue|php|rust|go)\b.*\b(version|release|latest)\b", norm):
        return "software_version"
    return "general"
