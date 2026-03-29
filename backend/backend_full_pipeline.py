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
        self.sender_email = sender_email
        self.sender_password = sender_password

        self.embedder = self._create_embedder()

        self.jd_text = jd_text
        self.jd_schema = JDStructurer.structure(jd_text)

        self.parser = ResumeParser(resume_folder)
        self.ranker = self._create_ranker()

        self.parsed_resumes = []
        self.chatbot = None
        self.latest_ranking = None
        self._ranking_dirty = True

        self.refresh_resumes()

    def _create_embedder(self):
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def _create_ranker(self):
        return ResumeRanker(
            self.embedder,
            self.jd_text,
            self.jd_schema,
        )

    def _build_chatbot(self):
        return ResumeRAGChatbot(
            self.parsed_resumes,
            self.jd_schema,
            self.embedder,
            jd_text=self.jd_text,
        )

    def _encode_text_embedding(self, text):
        return self.embedder.encode([text], normalize_embeddings=True)[0]

    def _attach_resume_embeddings(self, resume):
        text = resume.get("text", "")
        projects_text = resume.get("projects_text", "")

        try:
            resume["text_embedding"] = self._encode_text_embedding(text)
        except Exception:
            resume["text_embedding"] = None

        try:
            if projects_text:
                resume["project_embedding"] = self._encode_text_embedding(projects_text)
            else:
                resume["project_embedding"] = None
        except Exception:
            resume["project_embedding"] = None

    def _attach_resume_embeddings_batch(self, resumes):
        if not resumes:
            return

        texts = [resume.get("text", "") for resume in resumes]
        projects_texts = [resume.get("projects_text", "") for resume in resumes]

        text_embeddings = [None] * len(resumes)
        try:
            encoded_texts = self.embedder.encode(texts, normalize_embeddings=True)
            text_embeddings = [embedding for embedding in encoded_texts]
        except Exception:
            for idx, text in enumerate(texts):
                try:
                    text_embeddings[idx] = self._encode_text_embedding(text)
                except Exception:
                    text_embeddings[idx] = None

        project_embeddings = [None] * len(resumes)
        project_indices = [idx for idx, value in enumerate(projects_texts) if value]
        if project_indices:
            try:
                encoded_projects = self.embedder.encode(
                    [projects_texts[idx] for idx in project_indices],
                    normalize_embeddings=True,
                )
                for position, idx in enumerate(project_indices):
                    project_embeddings[idx] = encoded_projects[position]
            except Exception:
                for idx in project_indices:
                    try:
                        project_embeddings[idx] = self._encode_text_embedding(projects_texts[idx])
                    except Exception:
                        project_embeddings[idx] = None

        for idx, resume in enumerate(resumes):
            resume["text_embedding"] = text_embeddings[idx]
            resume["project_embedding"] = project_embeddings[idx]

    def _mark_ranking_dirty(self):
        self._ranking_dirty = True

    def _is_ranking_cache_valid(self):
        return (not self._ranking_dirty) and self.latest_ranking is not None

    # -----------------------------------------------------
    # REFRESH RESUMES
    # -----------------------------------------------------
    def refresh_resumes(self):
        self.parsed_resumes = self.parser.parse_resumes()
        self._attach_resume_embeddings_batch(self.parsed_resumes)
        self._mark_ranking_dirty()

        self.chatbot = self._build_chatbot()

    # -----------------------------------------------------
    # INCREMENTAL RESUME UPDATE (UPLOAD OPTIMIZATION)
    # -----------------------------------------------------
    def add_resume_incrementally(self, new_resume):
        """
        Add a single newly-parsed resume without re-parsing all.
        Much faster for batch uploads.
        Returns True if added successfully.
        """
        try:
            self._attach_resume_embeddings(new_resume)

            # Add to parsed resumes
            self.parsed_resumes.append(new_resume)
            self._mark_ranking_dirty()

            # Add to chatbot index incrementally
            if self.chatbot:
                self.chatbot._add_resume_to_index(new_resume)

            print(f"[INCREMENTAL] Added resume: {new_resume.get('name', 'Unknown')}")
            return True

        except Exception as e:
            print(f"[INCREMENTAL ERROR] {str(e)}")
            return False

    def _build_rank_row(self, resume, score):
        return {
            "name": resume.get("name", "Unknown Candidate"),
            "email": resume.get("email", "N/A"),
            "score": score,
            "role": "Candidate",
        }

    def _score_resume_safely(self, resume):
        try:
            return self.ranker.score_resume(resume)
        except Exception as e:
            print(f"[RANK ERROR] {resume.get('name')}: {e}")
            return 0

    @staticmethod
    def _normalize_score_frame(df):
        df["score"] = df["score"].clip(0, 100).round(2)
        return df.sort_values("score", ascending=False).reset_index(drop=True)

    def _sync_chatbot_ranking_context(self, ranking_df):
        self.latest_ranking = ranking_df.copy()
        self._ranking_dirty = False
        if self.chatbot:
            self.chatbot.set_ranking_data(ranking_df)

    def _ensure_ranking_context(self):
        if self.latest_ranking is None and self.parsed_resumes:
            try:
                self.rank_resumes()
            except Exception as e:
                print(f"[CHAT RANK PREP ERROR] {e}")

    # -----------------------------------------------------
    def rank_resumes(self):
        if not self.parsed_resumes:
            return pd.DataFrame()

        if self._is_ranking_cache_valid():
            return self.latest_ranking.copy()

        rows = []
        for resume in self.parsed_resumes:
            score = self._score_resume_safely(resume)
            rows.append(self._build_rank_row(resume, score))

        df = pd.DataFrame(rows)

        if df.empty:
            return df

        # =================================================
        # ✅ CRITICAL FIX — REMOVE MIN-MAX NORMALIZATION
        # =================================================
        # The ranker already outputs calibrated percentages.
        # We only clip to safe bounds to avoid UI anomalies.
        df = self._normalize_score_frame(df)
        self._sync_chatbot_ranking_context(df)

        return df

    # -----------------------------------------------------
    # CHATBOT
    # -----------------------------------------------------
    def ask_chatbot(self, query, top_k=5, chat_history=None, query_type=None):
        if not self.chatbot:
            return "No resumes available yet."

        self._ensure_ranking_context()

        return self.chatbot.generate_response(
            user_query=query,
            top_k=top_k,
            chat_history=chat_history or [],
            ranking_df=self.latest_ranking,
            query_type=query_type,
        )