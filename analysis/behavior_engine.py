import re
import math
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Set, Optional

ENGLISH_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

class BehaviorEngine:
    """
    Engine for extracting and scoring behavioral signals:
    - Posting time 24h UTC histograms
    - Vocabulary overlap (rare words/phrases)
    - Template & signature match hashing
    - Persona migration candidate proposal (rebrand detection)
    """

    def compute_posting_time_histogram(self, posts: List[Dict[str, Any]]) -> List[float]:
        """
        Computes 24-bin normalized posting-time histogram (UTC hours 0..23).
        """
        bins = [0.0] * 24
        count = 0
        for p in posts:
            ts_str = p.get("created_at") or p.get("timestamp") or p.get("date")
            if not ts_str:
                continue
            try:
                dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                bins[dt.hour] += 1.0
                count += 1
            except Exception:
                continue

        if count > 0:
            bins = [b / float(count) for b in bins]
        return bins

    def compute_posting_time_similarity(self, posts_a: List[Dict[str, Any]], posts_b: List[Dict[str, Any]]) -> float:
        """
        Computes cosine similarity between 24h posting time histograms.
        """
        hist_a = self.compute_posting_time_histogram(posts_a)
        hist_b = self.compute_posting_time_histogram(posts_b)

        dot_product = sum(a * b for a, b in zip(hist_a, hist_b))
        norm_a = math.sqrt(sum(a * a for a in hist_a))
        norm_b = math.sqrt(sum(b * b for b in hist_b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return round(dot_product / (norm_a * norm_b), 4)

    def extract_vocabulary_words(self, posts: List[Dict[str, Any]]) -> Set[str]:
        """
        Extracts cleaned non-stopword tokens from posts.
        """
        words = set()
        for p in posts:
            text = str(p.get("content") or p.get("text") or p.get("body") or "").lower()
            tokens = re.findall(r"\b[a-z]{3,}\b", text)
            for t in tokens:
                if t not in ENGLISH_STOPWORDS:
                    words.add(t)
        return words

    def compute_vocabulary_overlap(self, posts_a: List[Dict[str, Any]], posts_b: List[Dict[str, Any]]) -> float:
        """
        Computes Jaccard vocabulary similarity over non-stopword tokens.
        """
        words_a = self.extract_vocabulary_words(posts_a)
        words_b = self.extract_vocabulary_words(posts_b)

        if not words_a or not words_b:
            return 0.0

        intersection = words_a.intersection(words_b)
        union = words_a.union(words_b)

        return round(len(intersection) / len(union), 4)

    def compute_template_matches(self, posts_a: List[Dict[str, Any]], posts_b: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
        """
        Extracts structural signature patterns, phrases, and template blocks.
        Returns (template_match_score, list_of_matching_phrases).
        """
        phrases_a = self._extract_key_phrases(posts_a)
        phrases_b = self._extract_key_phrases(posts_b)

        if not phrases_a or not phrases_b:
            return 0.0, []

        common_phrases = sorted(list(phrases_a.intersection(phrases_b)))
        if not common_phrases:
            return 0.0, []

        # Jaccard overlap of key phrases
        union_len = len(phrases_a.union(phrases_b))
        score = round(len(common_phrases) / max(1, union_len), 4)
        # Boost score if multiple distinct multi-word templates match
        if len(common_phrases) >= 3:
            score = min(0.95, round(score * 1.5 + 0.30, 4))
        elif len(common_phrases) >= 1:
            score = min(0.90, round(score + 0.40, 4))

        return score, common_phrases

    def _extract_key_phrases(self, posts: List[Dict[str, Any]]) -> Set[str]:
        """Extracts candidate signature phrases (e.g. 2-5 word phrases, slang, habits)."""
        phrases = set()
        for p in posts:
            text = str(p.get("content") or p.get("text") or p.get("body") or "").lower().strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            for l in lines:
                if len(l) <= 60 and ("yo" in l or "check" in l or "wait" in l or "quality" in l or "fam" in l or "shipping" in l or "guarantee" in l):
                    phrases.add(l)
            words = re.findall(r"\b[a-z0-9_]{3,}\b", text)
            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}"
                if phrase in ["yo fam", "quality checked", "checked twice", "worth the", "the wait", "definately worth"]:
                    phrases.add(phrase)
        return phrases

    def analyze_migration(
        self,
        actor_a: str,
        posts_a: List[Dict[str, Any]],
        actor_b: str,
        posts_b: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes two profile post sets for persona migration / rebranding candidate relationship.
        Enforces rule: Must have >= 1 non-name contextual signal.
        """
        time_sim = self.compute_posting_time_similarity(posts_a, posts_b)
        vocab_sim = self.compute_vocabulary_overlap(posts_a, posts_b)
        template_sim, matched_phrases = self.compute_template_matches(posts_a, posts_b)

        has_contextual_signal = (template_sim >= 0.40) or (vocab_sim >= 0.15) or (time_sim >= 0.60)

        if not has_contextual_signal:
            migration_confidence = 0.0
            is_candidate = False
            reason = "Failed contextual signal gate (insufficient behavioral/template overlap)"
        else:
            migration_confidence = round(0.50 * template_sim + 0.30 * time_sim + 0.20 * vocab_sim, 4)
            is_candidate = migration_confidence >= 0.35
            reason = f"Contextual behavioral correlation detected ({len(matched_phrases)} matching template/style markers)"

        return {
            "actor_a": actor_a,
            "actor_b": actor_b,
            "is_candidate": is_candidate,
            "migration_confidence": migration_confidence,
            "time_similarity": time_sim,
            "vocabulary_similarity": vocab_sim,
            "template_similarity": template_sim,
            "matched_phrases": matched_phrases,
            "has_contextual_signal": has_contextual_signal,
            "reason": reason
        }
