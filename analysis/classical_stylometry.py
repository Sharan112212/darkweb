import re
import math
import hashlib
from typing import List, Dict, Any, Tuple

# Common function words for classical stylometry
FUNCTION_WORDS = [
  "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
  "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
  "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
  "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
  "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
  "when", "make", "can", "like", "time", "no", "just", "him", "know", "take",
  "people", "into", "year", "your", "good", "some", "could", "them", "see", "other",
  "than", "then", "now", "look", "only", "come", "its", "over", "think", "also",
  "back", "after", "use", "two", "how", "our", "work", "first", "well", "way",
  "even", "new", "want", "because", "any", "these", "give", "day", "most", "us"
]

class ClassicalStylometryEngine:
    """
    Classical Stylometry Analysis Engine.
    Enforces corpus quality gates (EC-19), corpus cleaning (EC-18, EC-21),
    and computes classical features (function-word frequencies, sentence lengths,
    punctuation habits, character 3-5 n-grams) using cosine similarity.
    """

    def clean_corpus(self, posts: List[str]) -> str:
        """
        Cleans corpus by removing quotes, PGP blocks, wallet strings, URLs, HTML tags,
        and market templates per EC-18 & EC-21.
        """
        cleaned_posts = []
        for post in posts:
            p = post
            # Remove HTML tags
            p = re.sub(r'<[^>]+>', ' ', p)
            # Remove PGP blocks
            p = re.sub(r'-----BEGIN PGP.*?-----END PGP.*?-----', ' ', p, flags=re.DOTALL)
            p = re.sub(r'-----BEGIN PGP.*', ' ', p, flags=re.DOTALL)
            # Remove Quoted lines (> or On ... wrote:)
            p = re.sub(r'^\s*>.*$', ' ', p, flags=re.MULTILINE)
            p = re.sub(r'On\s+.*?\s+wrote:', ' ', p)
            p = re.sub(r'---\s*Original Message\s*---.*', ' ', p, flags=re.DOTALL)
            # Remove Wallet addresses (BTC/ETH/XMR)
            p = re.sub(r'\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b', ' ', p)
            p = re.sub(r'\b0x[a-fA-F0-9]{40}\b', ' ', p)
            p = re.sub(r'\b[48][0-9a-zA-B]{94}\b', ' ', p)
            # Remove URLs
            p = re.sub(r'https?://\S+|http://\S+|\S+\.onion\S*', ' ', p)
            # Remove marketplace boilerplate / headers
            p = re.sub(r'===.*?===', ' ', p)
            p = re.sub(r'=====.*?=====', ' ', p)
            p = re.sub(r'Terms of Service:.*?\n', ' ', p)

            cleaned_posts.append(p.strip())

        return " ".join(cleaned_posts)

    def check_eligibility(self, posts: List[str]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Enforces eligibility gates (EC-19):
        - Minimum 5 posts
        - Minimum 1,500 cleaned characters
        - English language confidence gate (> 0.08 function word ratio threshold)
        """
        if len(posts) < 5:
            return False, "Failed gate: Post count below 5 posts requirement.", {"post_count": len(posts), "char_count": 0}

        cleaned = self.clean_corpus(posts)
        char_count = len(cleaned)

        if char_count < 1500:
            return False, f"Failed gate: Cleaned character count ({char_count}) below 1500 requirement.", {"post_count": len(posts), "char_count": char_count}

        # Simple language confidence check via function word density
        words = re.findall(r'\b[a-z]+\b', cleaned.lower())
        if not words:
            return False, "Failed gate: No valid words found in corpus.", {"post_count": len(posts), "char_count": char_count}

        fw_count = sum(1 for w in words if w in FUNCTION_WORDS)
        fw_ratio = fw_count / len(words)

        if fw_ratio < 0.08:
            return False, f"Failed gate: Non-English language detected (function word ratio {fw_ratio:.2f} < 0.08).", {"post_count": len(posts), "char_count": char_count, "fw_ratio": fw_ratio}

        return True, "Eligible", {"post_count": len(posts), "char_count": char_count, "fw_ratio": fw_ratio}

    def extract_feature_vector(self, cleaned_text: str) -> Dict[str, float]:
        """
        Extracts classical stylometric feature vector:
        1. Function-word relative frequencies
        2. Sentence length distribution (mean, stdev)
        3. Punctuation habits per 100 chars
        4. Top character 3-5 n-grams
        """
        text_lower = cleaned_text.lower()
        words = re.findall(r'\b[a-z]+\b', text_lower)
        total_words = max(len(words), 1)

        vector: Dict[str, float] = {}

        # 1. Function words frequency
        for fw in FUNCTION_WORDS:
            count = words.count(fw)
            vector[f"fw_{fw}"] = count / total_words

        # 2. Sentence lengths
        sentences = [s.strip() for s in re.split(r'[.!?]+', cleaned_text) if s.strip()]
        if sentences:
            s_lengths = [len(re.findall(r'\b\w+\b', s)) for s in sentences]
            mean_s_len = sum(s_lengths) / len(s_lengths)
            var_s_len = sum((x - mean_s_len) ** 2 for x in s_lengths) / len(s_lengths)
            stdev_s_len = math.sqrt(var_s_len)
        else:
            mean_s_len = 0.0
            stdev_s_len = 0.0

        vector["sent_len_mean"] = mean_s_len / 100.0  # normalize scale
        vector["sent_len_stdev"] = stdev_s_len / 100.0

        # 3. Punctuation habits
        total_chars = max(len(cleaned_text), 1)
        for punct in [',', '.', '!', '?', ';', ':', '-', '(', ')', '"', '\'']:
            vector[f"punct_{punct}"] = (cleaned_text.count(punct) / total_chars) * 100.0

        # 4. Top character n-grams (3-gram to 5-gram)
        for n in [3, 4]:
            ngrams = [text_lower[i:i+n] for i in range(len(text_lower) - n + 1) if ' ' not in text_lower[i:i+n]]
            total_ngrams = max(len(ngrams), 1)
            # Count top 20 ngrams across text
            ngram_counts: Dict[str, int] = {}
            for ng in ngrams:
                ngram_counts[ng] = ngram_counts.get(ng, 0) + 1
            for ng, count in ngram_counts.items():
                if count >= 3:  # Only significant n-grams
                    vector[f"ngram_{n}_{ng}"] = count / total_ngrams

        return vector

    def cosine_similarity(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """Computes cosine similarity between two feature vectors."""
        all_keys = set(vec_a.keys()).union(set(vec_b.keys()))
        dot_product = sum(vec_a.get(k, 0.0) * vec_b.get(k, 0.0) for k in all_keys)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def analyze_pair(self, posts_a: List[str], posts_b: List[str]) -> Dict[str, Any]:
        """
        Analyzes pair of post collections for classical stylometry similarity.
        Enforces gates on both corpora.
        """
        eligible_a, msg_a, meta_a = self.check_eligibility(posts_a)
        if not eligible_a:
            return {"is_eligible": False, "reason": f"Corpus A: {msg_a}", "similarity": 0.0}

        eligible_b, msg_b, meta_b = self.check_eligibility(posts_b)
        if not eligible_b:
            return {"is_eligible": False, "reason": f"Corpus B: {msg_b}", "similarity": 0.0}

        cleaned_a = self.clean_corpus(posts_a)
        cleaned_b = self.clean_corpus(posts_b)

        vec_a = self.extract_feature_vector(cleaned_a)
        vec_b = self.extract_feature_vector(cleaned_b)

        sim = self.cosine_similarity(vec_a, vec_b)

        hash_a = hashlib.sha256(cleaned_a.encode()).hexdigest()[:12]
        hash_b = hashlib.sha256(cleaned_b.encode()).hexdigest()[:12]
        corpus_hash = f"{hash_a}_{hash_b}"

        return {
            "is_eligible": True,
            "similarity": round(sim, 4),
            "corpus_hash": corpus_hash,
            "meta_a": meta_a,
            "meta_b": meta_b,
            "cleaned_char_count_a": len(cleaned_a),
            "cleaned_char_count_b": len(cleaned_b)
        }
