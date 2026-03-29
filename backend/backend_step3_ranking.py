import re
import math
from collections import OrderedDict
from typing import Any, Dict, Optional, Set, Tuple
from sentence_transformers import util


class ResumeRanker:
    """
    Production ATS ranker — FINAL POLISH VERSION.
    """

    # ================================
    # 🔥 Slight hybrid-role rebalance
    # ================================
    W_ROLE = 0.20
    W_SKILL = 0.30
    W_EXP = 0.14
    W_SEMANTIC_MAIN = 0.24
    W_PROJECT = 0.08
    W_RESP = 0.04
    W_KEYWORD = 0.0
    SCORE_TRACE_LIMIT = 1000
    ROLE_CACHE_LIMIT = 2048

    ROLE_TOOL_SIGNALS = {
        "devops": [
            "docker", "kubernetes", "terraform", "jenkins",
            "ansible", "helm", "prometheus", "grafana",
            "ci/cd", "github actions", "infrastructure", "sre"
        ],
        "ml": [
            "pytorch", "tensorflow", "machine learning",
            "deep learning", "nlp", "computer vision"
        ],
        "fullstack": [
            "react", "node", "express", "frontend", "backend",
            "nextjs", "typescript"
        ],
        "backend": [
            "api", "microservices", "fastapi", "django", "flask"
        ],
        "frontend": [
            "react", "angular", "vue", "ui"
        ],
        "data": [
            "tableau", "power bi", "data analysis", "analytics"
        ],
        "security": [
            "cybersecurity", "penetration", "vulnerability",
            "siem", "soc", "security analyst"
        ],
    }

    DEVOPS_CLUSTER = {
        "docker", "kubernetes", "ci/cd",
        "terraform", "jenkins", "aws", "gcp", "azure"
    }

    TITLE_ROLE_HINTS = {
        "devops": ["devops", "site reliability", "sre"],
        "ml": ["ml engineer", "ai engineer", "machine learning"],
        "fullstack": ["full stack", "fullstack"],
        "backend": ["backend"],
        "frontend": ["frontend"],
        "data": ["data scientist", "data analyst"],
        "security": ["cybersecurity", "security analyst"],
    }

    SKILL_ALIASES = {
        "k8s": "kubernetes",
        "kube": "kubernetes",
        "node.js": "node",
        "nodejs": "node",
        "postgre": "postgresql",
        "postgres": "postgresql",
        "ci cd": "ci/cd",
        "continuous integration": "ci/cd",
        "continuous delivery": "ci/cd",
        "ml": "machine learning",
        "ai": "machine learning",
        "nlp": "nlp",
        "powerbi": "power bi",
        "js": "javascript",
        "ts": "typescript",
    }

    # =================================================
    # INIT
    # =================================================
    def __init__(self, embedder, jd_text, jd_schema):
        self.embedder = embedder
        self.jd_text = jd_text.lower()
        self.jd_schema = jd_schema
        self.score_trace = []
        self._role_inference_cache = OrderedDict()

        self.jd_embedding = embedder.encode(
            [jd_text],
            normalize_embeddings=True
        )

        self._initialize_jd_requirements(jd_schema)
        self._initialize_responsibility_context(jd_schema)

    def _initialize_jd_requirements(self, jd_schema: Dict[str, Any]) -> None:
        self.core_skills = set(
            s.lower() for s in jd_schema.get("core_skills", [])
        )
        self.core_skills = self._normalize_skill_set(self.core_skills)
        self._core_skill_patterns = self._build_core_skill_patterns(self.core_skills)

        self.min_exp, self.ideal_exp = self._parse_experience_range(
            jd_schema.get("min_experience"),
            self.jd_text
        )

        self.jd_role, _ = self._infer_role_with_confidence(self.jd_text)

    def _build_core_skill_patterns(self, core_skills: Set[str]) -> Dict[str, Tuple[re.Pattern, re.Pattern]]:
        patterns = {}
        for skill in core_skills:
            escaped = re.escape(skill)
            strict_pattern = re.compile(rf"\b{escaped}\b")
            relaxed = escaped.replace("/", r"[\s/\\-]*").replace(r"\ ", r"[\s_\-]*")
            relaxed_pattern = re.compile(rf"\b{relaxed}\b")
            patterns[skill] = (strict_pattern, relaxed_pattern)
        return patterns

    def _initialize_responsibility_context(self, jd_schema: Dict[str, Any]) -> None:
        self.resp_text = self._build_responsibility_text(jd_schema)
        self.resp_embedding = self._encode_optional_text(self.resp_text)

    def _build_responsibility_text(self, jd_schema: Dict[str, Any]) -> str:
        return " ".join(
            jd_schema.get("responsibilities", [])
            + jd_schema.get("project_expectations", [])
        ).strip()

    def _encode_optional_text(self, text: str):
        if not text:
            return None
        return self.embedder.encode([text], normalize_embeddings=True)

    def _record_score_trace(self, payload):
        self.score_trace.append(payload)
        if len(self.score_trace) > self.SCORE_TRACE_LIMIT:
            self.score_trace = self.score_trace[-self.SCORE_TRACE_LIMIT:]

    # =================================================
    # EXPERIENCE RANGE PARSER
    # =================================================
    def _parse_experience_range(self, schema_value, jd_text):
        text = str(schema_value or "") + " " + jd_text.lower()

        range_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)", text)
        if range_match:
            return float(range_match.group(1)), float(range_match.group(2))

        plus_match = re.search(r"(\d+)\+?\s*(?:years|yrs)", text)
        if plus_match:
            val = float(plus_match.group(1))
            return val, val

        return 0.0, 0.0

    # =================================================
    # ROLE INFERENCE
    # =================================================
    def _extract_title_signal(self, text):
        lines = text.lower().split("\n")[:12]
        primary = " ".join(lines[:5])
        secondary = " ".join(lines[5:12])

        scores = {}
        for role, hints in self.TITLE_ROLE_HINTS.items():
            primary_hits = sum(primary.count(h) for h in hints)
            secondary_hits = sum(secondary.count(h) for h in hints)
            scores[role] = primary_hits + (0.45 * secondary_hits)

        best_role = max(scores, key=scores.get)
        conf = scores[best_role]

        if conf == 0:
            return "unknown", 0.0

        return best_role, min(conf / 2.0, 1.0)

    def _normalize_skill_token(self, skill):
        token = (skill or "").strip().lower()
        token = token.replace("_", " ")
        token = re.sub(r"\s+", " ", token)
        token = self.SKILL_ALIASES.get(token, token)
        return token

    def _normalize_skill_set(self, skills):
        return set(self._normalize_skill_token(s) for s in skills if str(s).strip())

    def _skill_present_in_text(self, skill, text_lower):
        skill_patterns = self._core_skill_patterns.get(skill)
        if skill_patterns:
            strict_pattern, relaxed_pattern = skill_patterns
            if strict_pattern.search(text_lower):
                return True
            return bool(relaxed_pattern.search(text_lower))

        escaped = re.escape(skill)
        strict_pattern = re.compile(rf"\b{escaped}\b")
        if strict_pattern.search(text_lower):
            return True

        # Handle common separator variations, such as "ci/cd" vs "ci cd".
        relaxed = escaped.replace("/", r"[\s/\\-]*").replace(r"\ ", r"[\s_\-]*")
        relaxed_pattern = re.compile(rf"\b{relaxed}\b")
        return bool(relaxed_pattern.search(text_lower))

    def _extract_tool_signal(self, text):
        text_lower = text.lower()
        length_norm = len(text_lower.split()) + 1

        scores = {}

        for role, tools in self.ROLE_TOOL_SIGNALS.items():
            raw = 0
            for t in tools:
                raw += min(text_lower.count(t), 3)
            scores[role] = raw / length_norm

        best_role = max(scores, key=scores.get)
        conf = scores[best_role]

        if conf == 0:
            return "unknown", 0.0

        return best_role, min(conf * 5, 1.0)

    def _infer_role_with_confidence(self, text):
        cached = self._role_inference_cache.get(text)
        if cached is not None:
            self._role_inference_cache.move_to_end(text)
            return cached

        title_role, title_conf = self._extract_title_signal(text)
        tool_role, tool_conf = self._extract_tool_signal(text)

        role_scores = {}

        for role in self.ROLE_TOOL_SIGNALS.keys():
            score = 0.0
            if role == title_role:
                score += 0.6 * title_conf
            if role == tool_role:
                score += 0.4 * tool_conf
            role_scores[role] = score

        best_role = max(role_scores, key=role_scores.get)
        best_conf = role_scores[best_role]

        if best_conf < 0.15:
            result = ("unknown", best_conf)
        else:
            result = (best_role, best_conf)

        self._role_inference_cache[text] = result
        if len(self._role_inference_cache) > self.ROLE_CACHE_LIMIT:
            self._role_inference_cache.popitem(last=False)

        return result

    # =================================================
    # ROLE ALIGNMENT
    # =================================================
    def role_alignment_score(self, resume, resume_text_lower: Optional[str] = None):
        text = resume_text_lower if resume_text_lower is not None else resume.get("text", "").lower()
        candidate_role, conf = self._infer_role_with_confidence(text)

        if candidate_role == self.jd_role:
            return 0.92 + 0.08 * conf

        if candidate_role == "unknown":
            return 0.52

        return 0.40

    # =================================================
    # ROLE-AWARE CLUSTER BONUS
    # =================================================
    def _cluster_bonus(self, resume):
        if self.jd_role != "devops":
            return 1.0

        skills = set(s.lower() for s in resume.get("skills", []))
        devops_hits = len(self.DEVOPS_CLUSTER & skills)

        if devops_hits >= 4:
            return 1.08
        if devops_hits >= 3:
            return 1.05

        return 1.0

    # =================================================
    # EXPERIENCE
    # =================================================
    def _read_candidate_experience(self, resume: Dict[str, Any]) -> float:
        try:
            return float(resume.get("experience_years") or 0)
        except Exception:
            return 0.0

    def _score_experience_without_ideal(self, candidate_exp: float) -> float:
        if self.min_exp > 0:
            ratio = candidate_exp / self.min_exp
            if ratio < 0.6:
                return max(0.2, ratio * 0.6)
            if ratio <= 1.5:
                return 0.9
            return 0.85

        return min(0.72 + min(candidate_exp, 8.0) * 0.03, 0.96)

    def experience_score(self, resume):
        candidate_exp = self._read_candidate_experience(resume)

        if self.min_exp > 0 and candidate_exp < 0.5 * self.min_exp:
            ratio = candidate_exp / max(self.min_exp, 1e-6)
            return max(0.35, ratio * 0.85)

        if self.ideal_exp <= 0:
            return self._score_experience_without_ideal(candidate_exp)

        ratio = candidate_exp / self.ideal_exp

        if ratio < 0.8:
            return max(0.38, ratio * 0.85)
        elif ratio <= 1.3:
            return 1.0
        elif ratio <= 2.0:
            return 0.95
        else:
            return 0.90

    # =================================================
    # SKILL COVERAGE
    # =================================================
    def _count_core_skill_matches(self, normalized_resume_skills: Set[str], resume_text_lower: str) -> int:
        matches = 0
        for skill in self.core_skills:
            if skill in normalized_resume_skills or self._skill_present_in_text(skill, resume_text_lower):
                matches += 1
        return matches

    def skill_score(self, resume, resume_text_lower: Optional[str] = None):
        res_skills = self._normalize_skill_set(resume.get("skills", []))
        text_lower = resume_text_lower if resume_text_lower is not None else resume.get("text", "").lower()

        if not self.core_skills:
            return 1.0, 1.0

        matches = self._count_core_skill_matches(res_skills, text_lower)

        coverage = matches / len(self.core_skills)

        # Smooth gate around coverage=0.35 to avoid hard cliffs.
        gate = 0.55 + (0.45 / (1.0 + math.exp(-8.0 * (coverage - 0.35))))

        return coverage ** 1.08, gate

    # =================================================
    # SEMANTIC
    # =================================================
    def semantic_score(self, resume):
        emb = resume.get("text_embedding")
        if emb is None:
            return 0.0

        sem = util.cos_sim(self.jd_embedding, emb)[0][0].item()
        sem = max(0.0, min(sem, 1.0))
        return max(0.15, sem)

    # =================================================
    # PROJECT
    # =================================================
    def project_score(self, resume, semantic_main: Optional[float] = None):
        proj_emb = resume.get("project_embedding")

        if proj_emb is None:
            base_sem = semantic_main if semantic_main is not None else self.semantic_score(resume)
            return max(0.10, min(base_sem * 0.72, 0.75))

        if self.resp_embedding is not None:
            return util.cos_sim(self.resp_embedding, proj_emb)[0][0].item()

        return util.cos_sim(self.jd_embedding, proj_emb)[0][0].item()

    # =================================================
    # RESPONSIBILITY
    # =================================================
    def responsibility_score(self, resume):
        if self.resp_embedding is None:
            return 0.35

        emb = resume.get("text_embedding")
        if emb is None:
            return 0.35

        return util.cos_sim(self.resp_embedding, emb)[0][0].item()

    # =================================================
    # FINAL — BROADER SPECTRUM
    # =================================================
    def _compute_weighted_score(self, role: float, skill: float, exp: float, sem: float, proj: float, resp: float) -> float:
        return (
            self.W_ROLE * role +
            self.W_SKILL * skill +
            self.W_EXP * exp +
            self.W_SEMANTIC_MAIN * sem +
            self.W_PROJECT * proj +
            self.W_RESP * resp
        )

    def _calibrate_final_score(self, weighted: float, gate: float, cluster_bonus: float) -> float:
        final = weighted * gate
        final *= cluster_bonus

        final = final ** 0.82
        final = final * 1.55

        if final < 0.12:
            final *= 0.75

        return final

    def _build_score_trace_payload(
        self,
        resume: Dict[str, Any],
        role: float,
        skill: float,
        gate: float,
        exp: float,
        sem: float,
        proj: float,
        resp: float,
        weighted: float,
        cluster_bonus: float,
        score: float,
    ) -> Dict[str, Any]:
        return {
            "name": resume.get("name", "Unknown"),
            "role": round(role, 4),
            "skill": round(skill, 4),
            "skill_gate": round(gate, 4),
            "experience": round(exp, 4),
            "semantic": round(sem, 4),
            "project": round(proj, 4),
            "responsibility": round(resp, 4),
            "weighted": round(weighted, 4),
            "cluster_bonus": round(cluster_bonus, 4),
            "score": score,
        }

    def score_resume(self, resume):
        try:
            resume_text_lower = resume.get("text", "").lower()

            role = self.role_alignment_score(resume, resume_text_lower=resume_text_lower)
            sem = self.semantic_score(resume)
            skill, gate = self.skill_score(resume, resume_text_lower=resume_text_lower)
            exp = self.experience_score(resume)
            proj = self.project_score(resume, semantic_main=sem)
            resp = self.responsibility_score(resume)
            cluster_bonus = self._cluster_bonus(resume)

            weighted = self._compute_weighted_score(role, skill, exp, sem, proj, resp)
            final = self._calibrate_final_score(weighted, gate, cluster_bonus)

            score = round(min(final * 100, 100), 2)
            trace_payload = self._build_score_trace_payload(
                resume=resume,
                role=role,
                skill=skill,
                gate=gate,
                exp=exp,
                sem=sem,
                proj=proj,
                resp=resp,
                weighted=weighted,
                cluster_bonus=cluster_bonus,
                score=score,
            )
            self._record_score_trace(trace_payload)

            return score

        except Exception as e:
            print(f"[RANK ERROR] {resume.get('name','Unknown')}: {e}")
            return 0.0