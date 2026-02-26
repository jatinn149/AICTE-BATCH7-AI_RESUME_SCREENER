import pandas as pd
from sentence_transformers import SentenceTransformer

from backend_step0_jd_structurer import JDStructurer
from backend_step2_resume_parser import ResumeParser
from backend_step3_ranking import ResumeRanker
from backend_step5_rag_chatbot import ResumeRAGChatbot


class ResumeScreeningAI:
    """
    Clean orchestration pipeline.
    """

    # -----------------------------------------------------
    # INIT
    # -----------------------------------------------------
    def __init__(self, jd_text, resume_folder, sender_email, sender_password):
        self.embedder = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        self.jd_text = jd_text
        self.jd_schema = JDStructurer.structure(jd_text)

        self.parser = ResumeParser(resume_folder)

        self.ranker = ResumeRanker(
            self.embedder,
            jd_text,
            self.jd_schema
        )

        self.parsed_resumes = []
        self.chatbot = None
        self.latest_ranking = None

        self.refresh_resumes()

    # -----------------------------------------------------
    # REFRESH RESUMES
    # -----------------------------------------------------
    def refresh_resumes(self):
        self.parsed_resumes = self.parser.parse_resumes()

        # 🔥 embedding cache
        for r in self.parsed_resumes:
            text = r.get("text", "")
            projects = r.get("projects_text", "")

            try:
                r["text_embedding"] = self.embedder.encode(
                    [text],
                    normalize_embeddings=True
                )[0]
            except Exception:
                r["text_embedding"] = None

            try:
                if projects:
                    r["project_embedding"] = self.embedder.encode(
                        [projects],
                        normalize_embeddings=True
                    )[0]
                else:
                    r["project_embedding"] = None
            except Exception:
                r["project_embedding"] = None

        # rebuild chatbot
        self.chatbot = ResumeRAGChatbot(
            self.parsed_resumes,
            self.jd_schema,
            self.embedder
        )

    # -----------------------------------------------------
    # 🔥 RANKING — PRODUCTION SAFE
    # -----------------------------------------------------
    def rank_resumes(self):
        if not self.parsed_resumes:
            return pd.DataFrame()

        rows = []

        for r in self.parsed_resumes:
            try:
                score = self.ranker.score_resume(r)
            except Exception as e:
                print(f"[RANK ERROR] {r.get('name')}: {e}")
                score = 0

            rows.append({
                "name": r.get("name", "Unknown Candidate"),
                "email": r.get("email", "N/A"),
                "score": score,
                "role": "Candidate"
            })

        df = pd.DataFrame(rows)

        if df.empty:
            return df

        # =================================================
        # ✅ CRITICAL FIX — REMOVE MIN-MAX NORMALIZATION
        # =================================================
        # The ranker already outputs calibrated percentages.
        # We only clip to safe bounds to avoid UI anomalies.
        df["score"] = df["score"].clip(0, 100).round(2)

        df = df.sort_values("score", ascending=False).reset_index(drop=True)

        # cache ranking for chatbot
        self.latest_ranking = df.copy()

        return df

    # -----------------------------------------------------
    # CHATBOT
    # -----------------------------------------------------
    def ask_chatbot(self, query, top_k=5, chat_history=None):
        if not self.chatbot:
            return "No resumes available yet."

        return self.chatbot.generate_response(
            user_query=query,
            top_k=top_k,
            chat_history=chat_history or [],
            ranking_df=self.latest_ranking,
        )