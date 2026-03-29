import os
import re
import requests
import faiss
import numpy as np
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class ResumeRAGChatbot:
    """
    Production-style Recruiter Copilot

    Routing order:
    1️⃣ Meta
    2️⃣ Ranking-aware
    3️⃣ Structured factual
    4️⃣ Fast factual
    5️⃣ LLM with retrieved context (NO TEXT DUMP EVER)
    """

    SYSTEM_PROMPT = """
You are an expert recruiter copilot.

Hard constraints:
- Use only provided context (job description, parsed resumes, and ranking data)
- Never invent missing facts
- If data is missing, state exactly what is missing
- Keep responses concise and actionable for hiring decisions
- Prefer direct answers over long explanations
- Do not output raw context dumps
- If the user asks outside hiring/resume/JD scope, refuse briefly
"""

    MAX_OUTPUT_CHARS = 950
    MIN_QUERY_LEN = 3
    MAX_TOP_K = 12
    MIN_PARAGRAPH_LEN = 40
    MAX_CHAT_HISTORY_MESSAGES = 6
    MAX_CHAT_MESSAGE_CHARS = 1000
    SCOPE_WORDS = {
        "resume", "candidate", "job", "jd", "rank", "score", "experience",
        "skill", "email", "fit", "shortlist", "compare", "hiring", "who", "why"
    }
    WHY_FIRST_PATTERN = re.compile(r"why is (.+?) first")
    SCORE_FOR_PATTERN = re.compile(r"(?:score|rank).*?for\s+([a-zA-Z .'-]+)")
    COMPARE_PATTERN = re.compile(r"compare\s+([a-zA-Z .'-]+)\s+(?:and|vs)\s+([a-zA-Z .'-]+)")
    WHO_KNOWS_PATTERN = re.compile(r"who knows ([a-z0-9+.# ]+)")

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self, resumes, jd_schema, embedder, jd_text=None):
        self.embedder = embedder
        self.index = None
        self.chunks = []
        self._http = requests.Session()
        self.raw_resumes = resumes or []
        self.jd_schema = jd_schema  # Store full schema, not just summary
        self.jd_text = jd_text or ""  # Store raw JD text
        self.jd_summary = self._build_jd_summary(jd_schema)
        self.ranking_data = None  # Will be updated from outside
        self._candidate_rollup_cache = None
        self._ranking_context_cache = None
        self.name_lookup = {
            r.get("name", "").strip().lower(): r
            for r in self.raw_resumes
            if r.get("name")
        }

        if resumes:
            self._build_index(resumes)

    # =====================================================
    # META INTELLIGENCE
    # =====================================================
    def _meta_answer(self, query: str):
        q = query.lower()

        if "how many candidates" in q:
            return f"Total candidates uploaded: {len(self.raw_resumes)}"

        if "list candidates" in q:
            names = [r.get("name", "Unknown") for r in self.raw_resumes]
            return "Candidates:\n" + "\n".join(names)

        if "job description" in q or "jd summary" in q:
            return self.jd_summary or "Job description details are not available."

        if "how many resumes" in q or "total resumes" in q:
            return f"Total resumes processed: {len(self.raw_resumes)}"

        return None

    # =====================================================
    # RANKING INTELLIGENCE
    # =====================================================
    def _ranking_answer(self, query: str, ranking_df):
        if ranking_df is None or ranking_df.empty:
            return None

        q = query.lower()

        # why is X first
        m = self.WHY_FIRST_PATTERN.search(q)
        if m:
            name = m.group(1).strip().title()

            row = self._get_ranking_row(ranking_df, name)
            if row.empty:
                return None

            score = float(row.iloc[0]["score"])
            rank = int(row.index[0]) + 1

            return (
                f"{name} is ranked #{rank} with a match score of {score}%. "
                "The ranking is based on semantic similarity, skill coverage, "
                "experience alignment, and project relevance to the job description."
            )

        # who is first
        if "who is first" in q or "top candidate" in q:
            top = ranking_df.iloc[0]
            return (
                f"Top candidate is {top['name']} "
                f"with a match score of {top['score']}%."
            )

        if "lowest" in q or "last candidate" in q or "who is last" in q:
            last = ranking_df.iloc[-1]
            return (
                f"Lowest-ranked candidate is {last['name']} "
                f"with a match score of {last['score']}%."
            )

        score_match = self.SCORE_FOR_PATTERN.search(q)
        if score_match:
            candidate_name = score_match.group(1).strip()
            row = self._get_ranking_row(ranking_df, candidate_name)
            if not row.empty:
                idx = int(row.index[0]) + 1
                score = float(row.iloc[0]["score"])
                return f"{row.iloc[0]['name']} is ranked #{idx} with a score of {score}%."

        compare_match = self.COMPARE_PATTERN.search(q)
        if compare_match:
            left = compare_match.group(1).strip().lower()
            right = compare_match.group(2).strip().lower()
            left_row = self._get_ranking_row(ranking_df, left)
            right_row = self._get_ranking_row(ranking_df, right)

            if not left_row.empty and not right_row.empty:
                l_rank = int(left_row.index[0]) + 1
                r_rank = int(right_row.index[0]) + 1
                l_name = left_row.iloc[0]["name"]
                r_name = right_row.iloc[0]["name"]
                l_score = float(left_row.iloc[0]["score"])
                r_score = float(right_row.iloc[0]["score"])
                diff = round(abs(l_score - r_score), 2)

                if l_score >= r_score:
                    return (
                        f"{l_name} ranks above {r_name} (#{l_rank} vs #{r_rank}). "
                        f"Scores: {l_name} {l_score}%, {r_name} {r_score}% (gap {diff}%)."
                    )
                return (
                    f"{r_name} ranks above {l_name} (#{r_rank} vs #{l_rank}). "
                    f"Scores: {r_name} {r_score}%, {l_name} {l_score}% (gap {diff}%)."
                )

        # show ranking
        if "show ranking" in q or "leaderboard" in q:
            lines = [
                f"{i+1}. {row['name']} — {row['score']}%"
                for i, (_, row) in enumerate(ranking_df.iterrows())
            ]
            return "Current ranking:\n" + "\n".join(lines)

        return None

    @staticmethod
    def _get_ranking_row(ranking_df, candidate_name):
        return ranking_df[ranking_df["name"].str.lower() == candidate_name.lower()]

    # =====================================================
    # STRUCTURED FACTUAL ANSWERS
    # =====================================================
    def _structured_answer(self, query: str):
        q = query.lower()

        # ---- EXPERIENCE QUESTIONS ----
        if "experience" in q:
            matches = []

            for r in self.raw_resumes:
                name = r.get("name", "").lower()
                if name and name in q:
                    matches.append(r)

            if matches:
                lines = []
                for r in matches:
                    exp = r.get("experience_years")
                    if exp:
                        lines.append(f"{r['name']}: {exp} years")
                    else:
                        lines.append(f"{r['name']}: experience not found")

                return "Experience summary:\n" + "\n".join(lines)

            if "most experience" in q:
                ranked = sorted(
                    self.raw_resumes,
                    key=lambda r: float(r.get("experience_years") or 0),
                    reverse=True,
                )
                if ranked:
                    top = ranked[0]
                    exp = top.get("experience_years") or "unknown"
                    return f"Most experienced candidate is {top.get('name', 'Unknown')} with {exp} years."

        if "email" in q:
            for resume in self.raw_resumes:
                name = (resume.get("name") or "").lower()
                if name and name in q:
                    email = resume.get("email") or "N/A"
                    return f"{resume.get('name', 'Unknown')}'s email: {email}"

        if "skills" in q and "who" in q:
            skill_candidates = []
            for r in self.raw_resumes:
                skills = r.get("skills", [])
                if not skills:
                    continue
                for s in skills:
                    if s.lower() in q:
                        skill_candidates.append(r.get("name", "Unknown"))
                        break
            if skill_candidates:
                return "Candidates matching the mentioned skills: " + ", ".join(skill_candidates)

        return None

    # =====================================================
    # FAST FACTUAL
    # =====================================================
    def _fast_answer(self, query):
        q = query.lower()

        skill_match = self.WHO_KNOWS_PATTERN.search(q)
        if skill_match:
            skill = skill_match.group(1).strip()

            matches = [
                r.get("name", "Unknown")
                for r in self.raw_resumes
                if skill in r.get("text", "").lower()
            ]

            if matches:
                return f"Candidates with {skill}: " + ", ".join(matches)

            return f"No candidates found with {skill}."

        return None

    def _is_in_scope(self, query: str):
        q = query.lower()
        if any(word in q for word in self.SCOPE_WORDS):
            return True

        # Also allow candidate-name based questions.
        if any(name in q for name in self.name_lookup.keys()):
            return True

        return False

    def _build_candidate_rollup(self):
        if self._candidate_rollup_cache is not None:
            return self._candidate_rollup_cache

        lines = []
        for resume in self.raw_resumes:
            name = resume.get("name", "Unknown")
            exp = resume.get("experience_years")
            exp_text = f"{exp}y" if exp not in (None, "") else "exp:n/a"
            skills = ", ".join((resume.get("skills") or [])[:8]) or "n/a"
            lines.append(f"- {name} | {exp_text} | skills: {skills}")
        self._candidate_rollup_cache = "\n".join(lines) if lines else "No candidate summaries available."
        return self._candidate_rollup_cache

    def _build_ranking_context(self):
        if self._ranking_context_cache is not None:
            return self._ranking_context_cache

        if self.ranking_data is None or self.ranking_data.empty:
            self._ranking_context_cache = "Ranking data not available."
            return self._ranking_context_cache

        lines = []
        for idx, (_, row) in enumerate(self.ranking_data.iterrows(), start=1):
            lines.append(f"{idx}. {row['name']} - {row['score']}%")
        self._ranking_context_cache = "\n".join(lines)
        return self._ranking_context_cache

    def _retrieve(self, query, top_k):
        if self.index is None:
            return []

        q_emb = self.embedder.encode(
            [query],
            normalize_embeddings=True
        ).astype("float32")

        scores, indices = self.index.search(q_emb, top_k)

        retrieved = []
        for i, score in zip(indices[0], scores[0]):
            if 0 <= i < len(self.chunks):
                retrieved.append({"text": self.chunks[i], "score": float(score)})

        return retrieved

    def _sanitize_top_k(self, top_k):
        return max(1, min(int(top_k or 5), self.MAX_TOP_K))

    def _validate_query(self, user_query):
        if not user_query or len(user_query.strip()) < self.MIN_QUERY_LEN:
            return "Please ask a clearer question related to resumes, ranking, or the job description."

        if not self._is_in_scope(user_query):
            return "I can only help with resume, ranking, and job-description questions for this hiring session."

        return None

    def _route_precomputed_answers(self, user_query, ranking_df):
        meta = self._meta_answer(user_query)
        if meta:
            return meta

        rank_ans = self._ranking_answer(user_query, ranking_df)
        if rank_ans:
            return rank_ans

        structured = self._structured_answer(user_query)
        if structured:
            return structured

        fast = self._fast_answer(user_query)
        if fast:
            return fast

        return None

    def _retrieve_with_guardrails(self, user_query, top_k, query_type):
        safe_top_k = self._sanitize_top_k(top_k)
        retrieved_chunks = self._retrieve(user_query, safe_top_k)

        if not retrieved_chunks:
            return None, "I couldn't find relevant information in the resumes."

        best_score = max((item["score"] for item in retrieved_chunks), default=0.0)
        if best_score < 0.15 and query_type != "meta":
            return None, "I couldn't find enough relevant evidence in the uploaded resumes for that question."

        return retrieved_chunks, None

    def _build_generation_prompt(self, user_query, query_type, retrieved_chunks):
        compact_context = "\n\n---\n\n".join(item["text"] for item in retrieved_chunks)
        ranking_context = self._build_ranking_context()
        candidate_rollup = self._build_candidate_rollup()

        return f"""
Recruiter request type: {query_type or 'content'}

JOB REQUIREMENTS SUMMARY:
{self.jd_summary}

JOB DESCRIPTION (raw):
{self.jd_text[:3000] if self.jd_text else 'Not available'}

RANKING WITH MATCH PERCENTAGES:
{ranking_context}

ALL CANDIDATE ROLLUP:
{candidate_rollup}

RETRIEVED RESUME EVIDENCE:
{compact_context}

USER QUESTION:
{user_query}

RESPONSE RULES:
- Return 2 to 6 short sentences
- Include names and exact percentages when ranking is relevant
- Mention uncertainty when evidence is weak
- Avoid repeating the same point
- No markdown tables
"""

    def _compress_output(self, text: str):
        if not text:
            return "I could not generate a response from available data."

        cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()

        if len(cleaned) <= self.MAX_OUTPUT_CHARS:
            return cleaned

        clipped = cleaned[: self.MAX_OUTPUT_CHARS].rsplit(".", 1)[0].strip()
        if not clipped:
            clipped = cleaned[: self.MAX_OUTPUT_CHARS].strip()
        return clipped + "."

    # =====================================================
    # JD SUMMARY (ENHANCED WITH FULL CONTEXT)
    # =====================================================
    def _build_jd_summary(self, jd_schema):
        parts = []

        role = jd_schema.get("role_title")
        if role:
            parts.append(f"**Role**: {role}")

        core = jd_schema.get("core_skills", [])
        if core:
            parts.append(f"**Required Skills**: {', '.join(core)}")
        
        secondary = jd_schema.get("secondary_skills", [])
        if secondary:
            parts.append(f"**Nice-to-Have Skills**: {', '.join(secondary)}")

        min_exp = jd_schema.get("min_experience")
        if min_exp:
            parts.append(f"**Experience Required**: {min_exp}")

        responsibilities = jd_schema.get("responsibilities", [])
        if responsibilities:
            parts.append(f"**Key Responsibilities**: {'; '.join(responsibilities[:3])}")

        project_expectations = jd_schema.get("project_expectations", [])
        if project_expectations:
            parts.append(f"**Project Expectations**: {'; '.join(project_expectations[:2])}")

        return "\n".join(parts)
    
    # =====================================================
    # UPDATE RANKING DATA (called from outside)
    # =====================================================
    def set_ranking_data(self, ranking_df):
        """
        Update ranking data for context-aware responses.
        Called from API after ranking is computed.
        """
        self.ranking_data = ranking_df
        self._ranking_context_cache = None

    # =====================================================
    # BUILD VECTOR INDEX
    # =====================================================
    def _build_index(self, resumes):
        self.chunks = []
        for r in resumes:
            name = r.get("name", "Unknown")

            paragraphs = [
                p.strip()
                for p in r.get("text", "").split("\n\n")
                if len(p.strip()) > self.MIN_PARAGRAPH_LEN
            ]

            for p in paragraphs:
                self.chunks.append(f"Candidate: {name}\n{p}")

        if not self.chunks:
            return

        embeddings = self.embedder.encode(
            self.chunks,
            normalize_embeddings=True
        )

        embeddings = np.array(embeddings).astype("float32")

        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    # =====================================================
    # ADD RESUME INCREMENTALLY (NEW - for upload optimization)
    # =====================================================
    def _add_resume_to_index(self, resume):
        """
        Add a single new resume to existing FAISS index.
        Called after each resume upload to avoid full re-indexing.
        """
        try:
            name = resume.get("name", "Unknown")
            paragraphs = [
                p.strip()
                for p in resume.get("text", "").split("\n\n")
                if len(p.strip()) > self.MIN_PARAGRAPH_LEN
            ]

            if not paragraphs:
                return False

            # Keep chunk text format identical to embeddings input.
            new_chunk_texts = [f"Candidate: {name}\n{p}" for p in paragraphs]
            self.chunks.extend(new_chunk_texts)

            # Embed new chunks
            new_embeddings = self.embedder.encode(
                new_chunk_texts,
                normalize_embeddings=True
            )
            new_embeddings = np.array(new_embeddings).astype("float32")

            # Keep fast lookup updated.
            resume_name = resume.get("name", "").strip().lower()
            if resume_name:
                self.name_lookup[resume_name] = resume

            # Add to existing index (or create if doesn't exist)
            if self.index is None:
                self.index = faiss.IndexFlatIP(new_embeddings.shape[1])
            
            self.index.add(new_embeddings)
            
            print(f"[RAG] Added {len(paragraphs)} chunks for {name}")
            return True

        except Exception as e:
            print(f"[RAG INCREMENTAL ERROR] {str(e)}")
            return False

    # =====================================================
    # LLM CALL
    # =====================================================
    def _call_llm(self, prompt, chat_history):
        if not GROQ_API_KEY:
            return "LLM key missing."

        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ]

            for h in (chat_history or [])[-self.MAX_CHAT_HISTORY_MESSAGES:]:
                role = h.get("role")
                content = h.get("content")
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": str(content)[: self.MAX_CHAT_MESSAGE_CHARS]})

            messages.append({"role": "user", "content": prompt})

            res = self._http.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.2,
                    "messages": messages,
                },
                timeout=30,
            )

            res.raise_for_status()

            return res.json()["choices"][0]["message"]["content"]

        except Exception as e:
            return f"LLM error: {str(e)}"

    # =====================================================
    # MAIN ENTRY — FINAL
    # =====================================================
    def generate_response(
        self,
        user_query,
        top_k=5,
        chat_history=None,
        ranking_df=None,
        query_type=None,
    ):
        if self.index is None:
            return "No resumes available yet."

        validation_error = self._validate_query(user_query)
        if validation_error:
            return validation_error

        routed_answer = self._route_precomputed_answers(user_query, ranking_df)
        if routed_answer:
            return self._compress_output(routed_answer)

        retrieved_chunks, retrieval_error = self._retrieve_with_guardrails(user_query, top_k, query_type)
        if retrieval_error:
            return retrieval_error

        prompt = self._build_generation_prompt(user_query, query_type, retrieved_chunks)
        llm_response = self._call_llm(prompt, chat_history)
        return self._compress_output(llm_response)
