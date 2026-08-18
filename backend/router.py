from __future__ import annotations

import re
from typing import List, Optional


class ConversationRouter:
    """Routes user messages to general, database, knowledge, or memory paths."""

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
        r"how many",
        r"\bcount\b",
        r"number of",
        r"total revenue",
        r"total .*",
        r"average",
        r"\bavg\b",
        r"\bsum\b",
        r"highest",
        r"lowest",
        r"group by",
        r"each department",
        r"by department",
        r"show employees",
        r"show .*",
        r"list .*",
        r"minus",
        r"compare .*revenue",
        r"compare .*expense",
        r"company name",
        r"name of the company",
        r"how much",
        r"\bmin\b",
        r"\bmax\b",
        r"percentage",
        r"orders?",
        r"customers?",
        r"employees?",
        r"salary",
        r"expenses?",
        r"revenues?",
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
        r"what is .*department",
        r"engineering department",
        r"about the company",
        r"company overview",
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
        r"explain more",
        r"tell me more",
        r"more info",
        r"more information",
        r"aur bataye",
        r"phir se batao",
        r"detail mein batao",
    ]

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").lower()).strip()

    @classmethod
    def _matches(cls, text: str, patterns: List[str]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)

    @classmethod
    def route(cls, message: str, history_texts: Optional[List[str]] = None) -> str:
        text = cls._normalize(message)
        history_texts = history_texts or []

        if not text:
            return "general"

        if cls._matches(text, cls.MEMORY_PATTERNS):
            return "memory"

        if cls._matches(text, cls.GREETING_PATTERNS) and not cls._matches(text, cls.DATABASE_PATTERNS):
            return "general"

        if cls._matches(text, cls.FOLLOW_UP_PATTERNS) and history_texts:
            prior = " ".join(history_texts[-4:]).lower()
            if cls._matches(prior, cls.DATABASE_PATTERNS):
                return "database"
            if cls._matches(prior, cls.KNOWLEDGE_PATTERNS):
                return "knowledge"
            return "general"

        if cls._matches(text, cls.TECHNICAL_PATTERNS):
            return "general"

        if cls._matches(text, cls.TRADING_PATTERNS):
            return "general"

        if cls._matches(text, cls.KNOWLEDGE_PATTERNS):
            # Prefer knowledge for explanatory/summary questions.
            if cls._matches(text, [r"how many", r"total revenue", r"average", r"show employees"]):
                return "database"
            return "knowledge"

        if cls._matches(text, cls.DATABASE_PATTERNS):
            return "database"

        return "general"
