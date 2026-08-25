from __future__ import annotations

import re
from typing import List, Optional


class ConversationRouter:
    """Routes user messages to general, database, knowledge, web, or memory paths."""

    GREETING_PATTERNS = [
        r"\bhello\b",
        r"\bhi\b",
        r"\bhey\b",
        r"\bgood (morning|afternoon|evening)\b",
        r"\bhow are you\b",
        r"\bwhat's up\b",
        r"\bthanks\b",
        r"\bthank you\b",
        r"\bbye\b",
        r"\bgoodbye\b",
    ]

    MEMORY_PATTERNS = [
        r"what did i ask",
        r"previous(ly)?",
        r"earlier",
        r"last question",
        r"conversation history",
        r"what did we talk",
        r"remind me",
    ]

    DATABASE_PATTERNS = [
        # Only patterns that clearly indicate a database SQL query intent.
        # General questions like "How many planets are there?" should NOT match.
        r"how many (?:employees|customers|orders|records|rows|entries|departments)",
        r"total (?:revenue|sales|salary|amount|expense|budget|profit)",
        r"average (?:salary|revenue|amount|price|cost)",
        r"group by",
        r"show (?:me )?(?:the )?(?:data|records|rows|table)",
        r"list (?:all )?(?:the )?(?:employees|customers|orders|departments)",
        r"compare (?:the )?(?:employees|departments|sales)",
        r"\bmin\b.*\b(salary|amount|revenue)\b",
        r"\bmax\b.*\b(salary|amount|revenue)\b",
        r"percentage (?:of|for) (?:the|total)",
    ]

    KNOWLEDGE_PATTERNS = [
        r"tell me about",
        r"explain",
        r"summary",
        r"summarize",
        r"why ",
        r"describe",
        r"overview",
        r"who is",
        r"about the company",
        r"company overview",
        # Hindi/Hinglish knowledge questions (only standalone, not follow-ups)
        r"kya (?:hot[ai]|hai|tha)",
        r"kaise (?:kaam|bana|ho)",
        r"samjhao",
        r"kya cheez hai",
    ]

    TRADING_PATTERNS = [
        r"\btrading\b",
        r"\btrade\b",
        r"\bstock\b",
        r"\bstocks\b",
        r"\bforex\b",
        r"\bcrypto\b",
        r"\bbitcoin\b",
        r"\bbroker\b",
        r"\bleverage\b",
        r"\bmargin\b",
        r"\bstop[- ]?loss\b",
        r"\btake[- ]?profit\b",
        r"\blimit order\b",
        r"\bmarket order\b",
        r"\bcandlestick\b",
        r"\btechnical analysis\b",
        r"\brsi\b",
        r"\bmacd\b",
        r"\bportfolio\b",
        r"\brisk management\b",
        r"\bday trading\b",
        r"\bswing trading\b",
        r"\bscalping\b",
        r"\bvolatility\b",
    ]

    TECHNICAL_PATTERNS = [
        r"\bai\b",
        r"artificial intelligence",
        r"\bllm\b",
        r"large language model",
        r"language model",
        r"machine learning",
        r"transformer",
        r"tokenizer",
        r"embedding",
        r"\bpostgresql\b",
        r"\bmysql\b",
        r"\bmongodb\b",
        r"database concepts?",
        r"programming",
        r"code",
        r"syntax",
        r"api\b",
    ]

    FOLLOW_UP_PATTERNS = [
        r"iske baare mein aur batao",
        r"iske baare mein aur information do",
        r"aur explain karo",
        r"aur batao",
        r"aur .*batao",
        r"explain more",
        r"tell me more",
        r"more info",
        r"more information",
        r"aur bataye",
        r"phir se batao",
        r"detail mein batao",
    ]

    # Database follow-up patterns (short follow-ups to prior DB questions)
    DATABASE_FOLLOWUP_PATTERNS = [
        r"what about",
        r"how about",
        r"and for",
        r"and the",
        r"same for",
        r"same as",
        r"now show",
        r"now list",
        r"now give",
        r"break it down",
        r"break that down",
        r"compare it",
        r"compare that",
        r"compare them",
        r"how does it compare",
        r"how much (?:higher|lower|more|less)",
        r"what's (?:the|its) (?:difference|trend|pattern)",
        r"next",
        r"also show",
        r"also list",
    ]

    # ---------- Web search patterns ----------
    # Temporal signals indicating the user wants current/live information.
    WEB_TEMPORAL_PATTERNS = [
        r"\blatest\b",
        r"\bcurrent(?:ly)?\b",
        r"\btoday\b",
        r"\bright now\b",
        r"\bas of now\b",
        r"\blive\b",
        r"\brecent(?:ly)?\b",
        r"\bnew(?:est)?\b",
        r"\bupdate(?:d|s)?\b",
        r"\bnews\b",
        r"\bbreaking\b",
        r"\bthis (week|month|year)\b",
        r"\bjust (in|happened|released|launched|announced)\b",
        r"\bwhat's new\b",
        r"\bwhat happened\b",
        r"\bprice today\b",
        r"\bmarket today\b",
        r"\bweather (today|now|right now)\b",
        r"\btonight\b",
        r"\bthis morning\b",
        r"\btonight\b",
    ]

    # Hindi/Hinglish temporal signals.
    WEB_TEMPORAL_HINDI = [
        r"\baaj\b",
        r"\babhi\b",
        r"\bnaya update\b",
        r"\bcurrent\b",
        r"\babhi kya\b",
        r"\baaj ka\b",
        r"\baaj ki\b",
        r"\blatest\b",
        r"\brecent\b",
        r"\blive\b",
        r"\bhua hai\b",
        r"\bchalu hai\b",
        r"\bchal raha\b",
        r"\bkya chal\b",
    ]

    # Topic patterns that commonly need live/current data.
    WEB_TOPIC_PATTERNS = [
        r"\b(weather|temperature|forecast)\b",
        r"\b(stock|share|nifty|sensex|djia|nasdaq|s&p)\b.*\b(price|today|live|now|update)\b",
        r"\b(gold|silver|crude oil|petrol|diesel)\b.*\b(price|today|rate)\b",
        r"\b(bitcoin|ethereum|crypto|btc|eth)\b.*\b(price|today|live|now)\b",
        r"\b(exchange rate|usd|eur|inr)\b.*\b(today|now|current)\b",
        r"\b(match|game|score|result)\b.*\b(live|today|latest|won)\b",
        r"\b(release|released|launch|launched|version)\b.*\b(date|when|latest)\b",
        r"\b(python|node|java|react|angular|vue)\b.*\b(version|latest|release)\b",
    ]

    # Words that should PREVENT web routing (evergreen / definitional).
    # Only exclude "what is" when it does NOT contain temporal keywords.
    WEB_EXCLUSION_PATTERNS = [
        r"\bdefine\b",
        r"\bmeaning of\b",
        r"\bhow does .+ work\b",
        r"\bexplain (the )?concept\b",
        r"\bdifference between\b",
        r"\bwhy (does|do|is|are|did)\b",
    ]

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").lower()).strip()

    @classmethod
    def _matches(cls, text: str, patterns: List[str]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)

    @classmethod
    def _is_web_query(cls, text: str) -> bool:
        """Determine if a question requires live web information.

        Strategy:
        1. If an exclusion pattern matches → NOT web (evergreen question).
        2. If a topic pattern matches AND a temporal pattern matches → web.
        3. If only temporal patterns match (no strong local signal) → web.
        4. Otherwise → not web.
        """
        # Never send definitional/evergreen questions to web.
        if cls._matches(text, cls.WEB_EXCLUSION_PATTERNS):
            return False

        has_temporal = cls._matches(text, cls.WEB_TEMPORAL_PATTERNS) or cls._matches(
            text, cls.WEB_TEMPORAL_HINDI
        )
        has_topic = cls._matches(text, cls.WEB_TOPIC_PATTERNS)

        # Topic + temporal → strong web signal.
        if has_topic and has_temporal:
            return True

        # Temporal alone -> web signal (e.g., "Bitcoin price today", "AI news").
        if has_temporal:
            return True

        return False

    @classmethod
    def route(cls, message: str, history_texts: Optional[List[str]] = None) -> str:
        text = cls._normalize(message)
        history_texts = history_texts or []

        if not text:
            return "general"

        # Greetings always go to general (never database).
        if cls._matches(text, cls.GREETING_PATTERNS):
            return "general"

        # Memory queries.
        if cls._matches(text, cls.MEMORY_PATTERNS):
            return "memory"

        # Hindi greetings / casual phrases always go to general.
        hindi_casual = re.search(
            r"\b(namaste|aap kaise|kya haal|accha|theek hai|bilkul|zaroor|shukriya|dhanyavaad)\b",
            text,
        )
        if hindi_casual and not cls._matches(text, cls.DATABASE_PATTERNS):
            return "general"

        # Web search: check BEFORE other patterns for temporal questions.
        if cls._is_web_query(text):
            if not cls._matches(text, cls.DATABASE_PATTERNS):
                return "web"

        # Follow-up: check if prior context was database/knowledge/web.
        if cls._matches(text, cls.FOLLOW_UP_PATTERNS + cls.DATABASE_FOLLOWUP_PATTERNS) and history_texts:
            prior = " ".join(history_texts[-4:]).lower()
            if cls._matches(prior, cls.DATABASE_PATTERNS):
                return "database"
            if cls._matches(prior, cls.KNOWLEDGE_PATTERNS):
                return "knowledge"
            # If prior was a web question, follow-up stays web.
            if cls._matches(prior, cls.WEB_TEMPORAL_PATTERNS) or cls._matches(
                prior, cls.WEB_TEMPORAL_HINDI
            ):
                return "web"
            # General follow-ups go to general (not database).
            return "general"

        # Knowledge: check BEFORE technical/trading so explanatory questions
        # about technical topics still route to knowledge retrieval.
        if cls._matches(text, cls.KNOWLEDGE_PATTERNS):
            return "knowledge"

        if cls._matches(text, cls.TECHNICAL_PATTERNS):
            return "general"

        if cls._matches(text, cls.TRADING_PATTERNS):
            return "general"

        if cls._matches(text, cls.DATABASE_PATTERNS):
            return "database"

        return "general"
