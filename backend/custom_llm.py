from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import torch

from inference.generate import generate_text
from model.config import GPTConfig
from model.gpt import GPTModel
from tokenizer.tokenizer import CharTokenizer


@dataclass(frozen=True)
class CuratedAnswer:
    """A vetted local answer already present in this project's knowledge corpus."""

    question: str
    answer: str
    source: str
    continuation: Optional[str] = None


class CuratedAnswerStore:
    """Retrieves factual general/technical answers from the existing local corpus.

    The small character model is useful for experimentation, but it has no reliable
    end-of-sequence token and can produce unrelated partial continuations.  For
    questions already covered by the project's vetted corpus, returning the corpus
    answer is both more accurate and avoids inventing a new fact.
    """

    SOURCE_FILES: Sequence[str] = (
        "data/raw/trading_knowledge.txt",
        "data/raw/ai_llm_knowledge.txt",
        "data/raw/technical_knowledge.txt",
        "data/raw/general_conversation.txt",
        "data/raw/general_knowledge.txt",
        "data/raw/hindi_hinglish_conversation.txt",
        "data/raw/followup_conversations.txt",
        "data/raw/database_knowledge.txt",
    )
    _PAIR_RE = re.compile(
        r"^User:\s*(?P<question>.+?)\r?\nAssistant:\s*(?P<answer>.+?)(?=\r?\n\r?\nUser:|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    _STOP_WORDS: Set[str] = {
        "a",
        "an",
        "and",
        "are",
        "can",
        "do",
        "for",
        "how",
        "is",
        "it",
        "me",
        "of",
        "please",
        "tell",
        "the",
        "to",
        "what",
        "who",
        "you",
    }

    def __init__(self, root: Path) -> None:
        self.root = root
        self.answers = self._load_answers()

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").casefold()).strip(" .?!")

    @classmethod
    def _terms(cls, text: str) -> Set[str]:
        terms: Set[str] = set()
        for token in re.findall(r"[a-z0-9]+", cls._normalize(text)):
            if token in cls._STOP_WORDS:
                continue
            # The corpus uses both "embedding" and "embeddings".  This small
            # normalization makes singular wording find the same vetted answer.
            if len(token) > 3 and token.endswith("s"):
                token = token[:-1]
            terms.add(token)
        return terms

    def _load_answers(self) -> List[CuratedAnswer]:
        answers: List[CuratedAnswer] = []
        for relative_path in self.SOURCE_FILES:
            path = self.root / relative_path
            if not path.exists():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            pairs = [
                (match.group("question").strip(), match.group("answer").strip())
                for match in self._PAIR_RE.finditer(content)
            ]
            for index, (question, answer) in enumerate(pairs):
                if not question or not answer:
                    continue
                continuation = pairs[index + 1][1] if index + 1 < len(pairs) else None
                answers.append(
                    CuratedAnswer(
                        question=question,
                        answer=answer,
                        source=relative_path.replace("\\", "/"),
                        continuation=continuation,
                    )
                )
        return answers

    def find(self, question: str) -> Optional[CuratedAnswer]:
        normalized = self._normalize(question)
        if not normalized:
            return None

        exact = [item for item in self.answers if self._normalize(item.question) == normalized]
        if exact:
            # Later files contain the more detailed technical/database definitions
            # where duplicate questions exist.
            return max(exact, key=lambda item: len(item.answer))

        requested_terms = self._terms(question)
        if not requested_terms:
            return None

        best: Optional[CuratedAnswer] = None
        best_score = 0.0
        for item in self.answers:
            candidate_terms = self._terms(item.question)
            if not candidate_terms:
                continue
            overlap = len(requested_terms & candidate_terms)
            if not overlap:
                continue
            # A single distinctive term such as "qdrant" or "embedding" is
            # sufficient.  Multi-term questions need a strong overlap so an
            # unrelated generic corpus response is never selected.
            coverage = overlap / len(requested_terms)
            precision = overlap / len(candidate_terms)
            score = (coverage * 0.7) + (precision * 0.3)
            if coverage >= 0.75 and score > best_score:
                best = item
                best_score = score
        return best

    @staticmethod
    def _is_comparison_question(text: str) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "").casefold()).strip()
        patterns = (
            r"\bdifference\b",
            r"\bvs\b",
            r"\bversus\b",
            r"\bfarak\b",
            r"\bcompare\b",
            r"\bdiff\b",
        )
        return any(re.search(pattern, normalized) for pattern in patterns)

    def continuation_for(self, previous_question: str) -> Optional[CuratedAnswer]:
        item = self.find(previous_question)
        if item is None:
            return None

        previous_terms = self._terms(previous_question)
        best_related: Optional[CuratedAnswer] = None
        best_score = 0.0
        for candidate in self.answers:
            if candidate.question == item.question:
                continue
            if self._is_comparison_question(candidate.question):
                continue
            candidate_terms = self._terms(candidate.question)
            overlap = len(previous_terms & candidate_terms)
            if not overlap:
                continue
            coverage = overlap / max(len(previous_terms), 1)
            precision = overlap / max(len(candidate_terms), 1)
            score = (coverage * 0.7) + (precision * 0.3)
            if score >= 0.3 and score > best_score:
                best_related = candidate
                best_score = score

        if best_related is not None:
            return CuratedAnswer(
                question=item.question,
                answer=f"{item.answer} {best_related.answer}",
                source=item.source,
            )
        return item


class CustomLLMService:
    """Wrapper around the existing Custom GPT model (no external APIs)."""

    def __init__(self, checkpoint_path: Optional[Path] = None, device: str = "cpu") -> None:
        root = Path(__file__).resolve().parents[1]
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else root / "checkpoints" / "checkpoint_latest.pt"
        self.device = torch.device(device)
        self.tokenizer = CharTokenizer()
        self.config = GPTConfig(
            vocab_size=self.tokenizer.vocab_size,
            block_size=128,
            embedding_dim=256,
            n_heads=4,
            n_layers=4,
            dropout=0.1,
        )
        self.model = GPTModel(self.config).to(self.device)
        self.ready = False
        self.curated_answers = CuratedAnswerStore(root)
        self._load()

    def _load(self) -> None:
        if not self.checkpoint_path.exists():
            return
        try:
            checkpoint = torch.load(str(self.checkpoint_path), map_location=self.device, weights_only=False)
            state = checkpoint.get("model_state") or checkpoint
            self.model.load_state_dict(state)
            self.model.eval()
            self.ready = True
        except Exception as exc:  # pragma: no cover
            print(f"CustomLLMService load failed: {exc}")
            self.ready = False

    def generate(self, prompt: str, max_new_tokens: int = 48) -> Dict[str, Any]:
        if not self.ready:
            return {"text": "", "used": False, "error": "checkpoint_unavailable"}
        try:
            raw = generate_text(
                self.model,
                self.tokenizer,
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=0.2,
                top_k=20,
            )
            text = (raw or "").strip()
            if text.startswith(prompt):
                text = text[len(prompt) :].strip()
            return {"text": text, "used": True, "error": None}
        except Exception as exc:  # pragma: no cover
            return {"text": "", "used": False, "error": str(exc)}

    @staticmethod
    def _looks_coherent(text: str) -> bool:
        cleaned = (text or "").strip()
        if not (12 <= len(cleaned) <= 220):
            return False
        lowered = cleaned.lower()
        banned = ("user:", "assistant:", "question:", "context:", "answer:", "draft:")
        if any(token in lowered for token in banned):
            return False
        words = re.findall(r"[A-Za-z]{2,}", cleaned)
        if len(words) < 3:
            return False
        # Reject heavy character-spam generations from the tiny model.
        if re.search(r"(.)\1{4,}", cleaned):
            return False
        unique_ratio = len(set(w.lower() for w in words)) / max(len(words), 1)
        if unique_ratio < 0.45:
            return False
        return True

    @staticmethod
    def _is_follow_up(message: str) -> bool:
        normalized = re.sub(r"\s+", " ", (message or "").casefold()).strip()
        patterns = (
            r"iske baare mein aur batao",
            r"iske baare mein aur information do",
            r"aur explain karo",
            r"aur batao",
            r"explain more",
            r"tell me more",
            r"more info(?:rmation)?",
            r"aur bataye",
            r"phir se batao",
            r"detail mein batao",
            r"iska simple example do",
            r"samajh nahi aaya",
            r"samajh nhi aaya",
            r"thoda aur batao",
            r"thoda detail mein batao",
        )
        return any(re.search(pattern, normalized) for pattern in patterns)

    def answer_general(
        self,
        message: str,
        context: str = "",
        previous_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Answer general questions without letting capped sampled text replace facts."""
        prompt = f"User: {message}\nAssistant:"
        if context:
            prompt = f"{context.strip()}\n{prompt}"

        if previous_message and self._is_follow_up(message):
            continued = self.curated_answers.continuation_for(previous_message)
            if continued:
                return {
                    "answer": continued.answer,
                    "llm_used": False,
                    "fallback": False,
                    "prompt": prompt,
                    "source": continued.source,
                }

        curated = self.curated_answers.find(message)
        if curated:
            return {
                "answer": curated.answer,
                "llm_used": False,
                "fallback": False,
                "prompt": prompt,
                "source": curated.source,
            }

        lowered = message.lower().strip()
        greeting = any(token in lowered for token in ("hello", "hi", "hey", "how are you"))
        if greeting:
            deterministic = (
                "Hello! I'm your trading and database assistant. "
                "Ask about stocks, forex, crypto, options, risk management, or company data."
            )
        elif "thank" in lowered:
            deterministic = "You're welcome. Ask me about trading concepts or your database anytime."
        elif any(token in lowered for token in ("bye", "goodbye")):
            deterministic = "Goodbye! I'm here whenever you need trading insights or database answers."
        else:
            deterministic = (
                "I can help with trading questions (7700+ topics), general conversation, "
                "company knowledge retrieval, and live PostgreSQL analytics."
            )

        # The generator emits exactly max_new_tokens character tokens and has no
        # end-of-sequence signal.  A short sampled continuation can therefore end
        # in the middle of a sentence.  It must not replace a complete answer.
        if greeting:
            return {
                "answer": deterministic,
                "llm_used": False,
                "fallback": True,
                "prompt": prompt,
                "source": "deterministic:greeting",
            }

        generated = self.generate(prompt, max_new_tokens=200)
        if generated.get("used") and self._looks_coherent(generated.get("text", "")):
            return {
                "answer": generated["text"],
                "llm_used": True,
                "fallback": False,
                "prompt": prompt,
                "source": "generated",
            }

        return {
            "answer": deterministic,
            "llm_used": False,
            "fallback": True,
            "prompt": prompt,
            "source": "deterministic:general",
        }

    def compose_with_context(self, question: str, context: str, draft: str) -> Dict[str, Any]:
        """Keep a complete factual draft rather than replacing it with a fragment.

        The local generator has fixed-length character sampling and no completion
        token, so it cannot safely be used as an automatic rewrite stage.  The
        factual SQL/Qdrant draft remains the final answer intact.
        """
        prompt = f"Answer: {draft}\n"
        return {
            "answer": draft,
            "llm_used": False,
            "prompt": prompt,
            "source": "deterministic:draft_preserved",
        }
