from sentence_transformers import SentenceTransformer, util
import re
from typing import List


class JobDescription:
    """
    Handles Job Description understanding:
    - Semantic embedding
    - Structured extraction of skills & experience
    """

    DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    MIN_CANDIDATE_CHUNK_LENGTH = 50
    MAX_SIMILARITY_CACHE_SIZE = 512
    EXPERIENCE_PATTERN = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)")
    SKILL_KEYWORDS = [
        "python",
        "java",
        "c++",
        "sql",
        "machine learning",
        "deep learning",
        "nlp",
        "pytorch",
        "tensorflow",
        "scikit",
        "data analysis",
        "faiss",
        "embeddings",
    ]

    def __init__(
        self,
        jd_text: str,
        model_name: str = DEFAULT_MODEL_NAME,
    ):
        self.jd_text = self._validate_and_normalize_jd_text(jd_text)
        self.model = SentenceTransformer(model_name)
        self.jd_text_lower = self.jd_text.lower()

        self.jd_embedding = self._encode_text(self.jd_text)
        self._similarity_cache = {}

        self.skills = self._extract_skills()
        self.min_experience = self._extract_experience()

    # ---------------- SEMANTIC SIMILARITY ---------------- #

    def compute_similarity(self, candidate_text: str) -> float:
        if self._is_blank(candidate_text):
            return 0.0

        cached_score = self._get_cached_similarity(candidate_text)
        if cached_score is not None:
            return cached_score

        candidate_chunks = self._prepare_candidate_chunks(candidate_text)

        if not candidate_chunks:
            self._cache_similarity(candidate_text, 0.0)
            return 0.0

        candidate_embeddings = self._encode_chunks(candidate_chunks)
        similarities = util.cos_sim(self.jd_embedding, candidate_embeddings)
        similarity_score = round(float(similarities.max().item()), 6)
        self._cache_similarity(candidate_text, similarity_score)
        return similarity_score

    def _get_cached_similarity(self, candidate_text: str):
        return self._similarity_cache.get(candidate_text)

    def _cache_similarity(self, candidate_text: str, similarity_score: float) -> None:
        if len(self._similarity_cache) >= self.MAX_SIMILARITY_CACHE_SIZE:
            oldest_key = next(iter(self._similarity_cache))
            self._similarity_cache.pop(oldest_key, None)
        self._similarity_cache[candidate_text] = similarity_score

    def _encode_text(self, text: str):
        return self.model.encode(
            text,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )

    def _encode_chunks(self, chunks: List[str]):
        return self.model.encode(
            chunks,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )

    def _prepare_candidate_chunks(self, candidate_text: str) -> List[str]:
        lines = (line.strip() for line in candidate_text.split("\n"))
        return [line for line in lines if len(line) > self.MIN_CANDIDATE_CHUNK_LENGTH]

    @staticmethod
    def _validate_and_normalize_jd_text(jd_text: str) -> str:
        if not jd_text or not jd_text.strip():
            raise ValueError("Job Description text cannot be empty")
        return jd_text.strip()

    @staticmethod
    def _is_blank(text: str) -> bool:
        return not text or not text.strip()

    # ---------------- STRUCTURED EXTRACTION ---------------- #

    def _extract_skills(self) -> list:
        matched_skills = [
            skill for skill in self.SKILL_KEYWORDS
            if skill in self.jd_text_lower
        ]
        return list(set(matched_skills))

    def _extract_experience(self) -> int:
        matches = self.EXPERIENCE_PATTERN.findall(self.jd_text_lower)

        if matches:
            return max(int(x) for x in matches)

        return 0
