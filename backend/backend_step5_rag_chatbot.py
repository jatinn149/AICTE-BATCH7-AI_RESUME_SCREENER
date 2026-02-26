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
You are an expert AI hiring assistant.

Answer ONLY using the provided resume context.
If information is missing, say so clearly.

Be concise and recruiter-friendly.
Mention candidate names when relevant.
Do not hallucinate.
"""

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self, resumes, jd_schema, embedder):
        self.embedder = embedder
        self.index = None
        self.chunks = []
        self.raw_resumes = resumes or []
        self.jd_summary = self._build_jd_summary(jd_schema)

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

        return None

    # =====================================================
    # RANKING INTELLIGENCE
    # =====================================================
    def _ranking_answer(self, query: str, ranking_df):
        if ranking_df is None or ranking_df.empty:
            return None

        q = query.lower()

        # why is X first
        m = re.search(r"why is (.+?) first", q)
        if m:
            name = m.group(1).strip().title()

            row = ranking_df[
                ranking_df["name"].str.lower() == name.lower()
            ]
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

        # show ranking
        if "show ranking" in q or "leaderboard" in q:
            lines = [
                f"{i+1}. {row['name']} — {row['score']}%"
                for i, (_, row) in enumerate(ranking_df.iterrows())
            ]
            return "Current ranking:\n" + "\n".join(lines)

        return None

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

        return None

    # =====================================================
    # FAST FACTUAL
    # =====================================================
    def _fast_answer(self, query):
        q = query.lower()

        skill_match = re.search(r"who knows ([a-z0-9+.# ]+)", q)
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

    # =====================================================
    # JD SUMMARY
    # =====================================================
    def _build_jd_summary(self, jd_schema):
        parts = []

        role = jd_schema.get("role_title")
        if role:
            parts.append(f"Role: {role}")

        core = jd_schema.get("core_skills", [])
        if core:
            parts.append("Core Skills: " + ", ".join(core))

        return "\n".join(parts)

    # =====================================================
    # BUILD VECTOR INDEX
    # =====================================================
    def _build_index(self, resumes):
        for r in resumes:
            name = r.get("name", "Unknown")

            paragraphs = [
                p.strip()
                for p in r.get("text", "").split("\n\n")
                if len(p.strip()) > 40
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
    # RETRIEVE
    # =====================================================
    def _retrieve(self, query, top_k):
        if self.index is None:
            return []

        q_emb = self.embedder.encode(
            [query],
            normalize_embeddings=True
        ).astype("float32")

        scores, indices = self.index.search(q_emb, top_k)

        return [
            self.chunks[i]
            for i in indices[0]
            if 0 <= i < len(self.chunks)
        ]

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

            for h in (chat_history or [])[-6:]:
                messages.append(h)

            messages.append({"role": "user", "content": prompt})

            res = requests.post(
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
    ):
        if self.index is None:
            return "No resumes available yet."

        # 1️⃣ META
        meta = self._meta_answer(user_query)
        if meta:
            return meta

        # 2️⃣ RANKING
        rank_ans = self._ranking_answer(user_query, ranking_df)
        if rank_ans:
            return rank_ans

        # 3️⃣ STRUCTURED
        structured = self._structured_answer(user_query)
        if structured:
            return structured

        # 4️⃣ FAST
        fast = self._fast_answer(user_query)
        if fast:
            return fast

        # 5️⃣ RETRIEVE + ALWAYS LLM (NO TEXT DUMP)
        retrieved_chunks = self._retrieve(user_query, top_k)

        if not retrieved_chunks:
            return "I couldn't find relevant information in the resumes."

        context_block = "\n\n---\n\n".join(retrieved_chunks)

        prompt = f"""
You are an expert recruiter assistant.

JOB DESCRIPTION:
{self.jd_summary}

RESUME CONTEXT:
{context_block}

USER QUESTION:
{user_query}

Instructions:
- Answer ONLY from the provided context.
- Be concise and recruiter-friendly.
- If unsure, say information is not available.
- DO NOT dump raw resume text.
"""

        return self._call_llm(prompt, chat_history)
