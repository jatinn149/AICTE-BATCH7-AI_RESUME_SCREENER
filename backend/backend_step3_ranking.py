import re
from sentence_transformers import util


class ResumeRanker:
    """
    Production ATS ranker — FINAL POLISH VERSION.
    """

    # ================================
    # 🔥 Slight hybrid-role rebalance
    # ================================
    W_ROLE = 0.30
    W_SKILL = 0.26
    W_EXP = 0.22
    W_SEMANTIC_MAIN = 0.10
    W_PROJECT = 0.05
    W_RESP = 0.03
    W_KEYWORD = 0.0

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

    # =================================================
    # INIT
    # =================================================
    def __init__(self, embedder, jd_text, jd_schema):
        self.embedder = embedder
        self.jd_text = jd_text.lower()
        self.jd_schema = jd_schema

        self.jd_embedding = embedder.encode(
            [jd_text],
            normalize_embeddings=True
        )

        self.core_skills = set(
            s.lower() for s in jd_schema.get("core_skills", [])
        )

        self.min_exp, self.ideal_exp = self._parse_experience_range(
            jd_schema.get("min_experience"),
            jd_text
        )

        self.jd_role, _ = self._infer_role_with_confidence(self.jd_text)

        self.resp_text = " ".join(
            jd_schema.get("responsibilities", [])
            + jd_schema.get("project_expectations", [])
        ).strip()

        self.resp_embedding = (
            embedder.encode([self.resp_text], normalize_embeddings=True)
            if self.resp_text else None
        )

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
        lines = text.lower().split("\n")[:5]
        joined = " ".join(lines)

        scores = {}
        for role, hints in self.TITLE_ROLE_HINTS.items():
            scores[role] = sum(joined.count(h) for h in hints)

        best_role = max(scores, key=scores.get)
        conf = scores[best_role]

        if conf == 0:
            return "unknown", 0.0

        return best_role, min(conf / 2.0, 1.0)

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
            return "unknown", best_conf

        return best_role, best_conf

    # =================================================
    # ROLE ALIGNMENT
    # =================================================
    def role_alignment_score(self, resume):
        text = resume.get("text", "").lower()
        candidate_role, conf = self._infer_role_with_confidence(text)

        if candidate_role == self.jd_role:
            return 0.92 + 0.08 * conf

        if candidate_role == "unknown":
            return 0.28

        return 0.15

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
    def experience_score(self, resume):
        try:
            candidate_exp = float(resume.get("experience_years") or 0)
        except Exception:
            candidate_exp = 0

        if self.min_exp > 0 and candidate_exp < 0.5 * self.min_exp:
            return 0.15

        if self.ideal_exp <= 0:
            return 1.0

        ratio = candidate_exp / self.ideal_exp

        if ratio < 0.8:
            return ratio * 0.7
        elif ratio <= 1.3:
            return 1.0
        elif ratio <= 2.0:
            return 0.95
        else:
            return 0.90

    # =================================================
    # SKILL COVERAGE
    # =================================================
    def skill_score(self, resume):
        res_skills = set(s.lower() for s in resume.get("skills", []))
        text_lower = resume.get("text", "").lower()

        if not self.core_skills:
            return 1.0, 1.0

        matches = 0
        for skill in self.core_skills:
            if skill in res_skills or re.search(rf"\b{re.escape(skill)}\b", text_lower):
                matches += 1

        coverage = matches / len(self.core_skills)

        if coverage < 0.2:
            gate = 0.4
        elif coverage < 0.4:
            gate = 0.65
        elif coverage < 0.6:
            gate = 0.85
        else:
            gate = 1.0

        return coverage ** 1.1, gate

    # =================================================
    # SEMANTIC
    # =================================================
    def semantic_score(self, resume):
        emb = resume.get("text_embedding")
        if emb is None:
            return 0.0

        sem = util.cos_sim(self.jd_embedding, emb)[0][0].item()
        return max(0.15, min(sem, 0.92))

    # =================================================
    # PROJECT
    # =================================================
    def project_score(self, resume):
        proj_emb = resume.get("project_embedding")

        if proj_emb is None:
            return 0.03

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
    def score_resume(self, resume):
        try:
            role = self.role_alignment_score(resume)
            sem = self.semantic_score(resume)
            skill, gate = self.skill_score(resume)
            exp = self.experience_score(resume)
            proj = self.project_score(resume)
            resp = self.responsibility_score(resume)

            weighted = (
                self.W_ROLE * role +
                self.W_SKILL * skill +
                self.W_EXP * exp +
                self.W_SEMANTIC_MAIN * sem +
                self.W_PROJECT * proj +
                self.W_RESP * resp
            )

            final = weighted * gate
            final *= self._cluster_bonus(resume)

            # 🔥 ATS-calibrated spread widening
            final = final ** 0.82
            final = final * 1.55

            if final < 0.12:
                final *= 0.75

            return round(min(final * 100, 100), 2)

        except Exception as e:
            print(f"[RANK ERROR] {resume.get('name','Unknown')}: {e}")
            return 0.0