import os
import re
import json
import fitz  # PyMuPDF
import pytesseract
import requests
from pdf2image import convert_from_path
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class ResumeParser:
    """
    ELITE-TIER Production Resume Parser

    Pipeline:
    1. Fast text extraction (PyMuPDF)
    2. OCR fallback (if needed)
    3. Deterministic parsing
    4. 🔥 LLM structured fallback (only if weak)

    Output schema unchanged.
    """

    # -------------------------------------------------
    # 🔥 MASSIVELY EXPANDED SKILL MAP
    # -------------------------------------------------
    SKILL_MAP = {
        "python": ["python"],
        "java": ["java"],
        "c++": ["c++", "cpp"],
        "javascript": ["javascript", "js"],
        "typescript": ["typescript", "ts"],
        "pytorch": ["pytorch", "torch"],
        "tensorflow": ["tensorflow", "tf"],
        "sklearn": ["scikit-learn", "sklearn"],
        "xgboost": ["xgboost"],
        "lightgbm": ["lightgbm"],
        "nlp": ["nlp", "natural language processing"],
        "computer vision": ["computer vision"],
        "machine learning": ["machine learning"],
        "deep learning": ["deep learning"],
        "pandas": ["pandas"],
        "numpy": ["numpy"],
        "matplotlib": ["matplotlib"],
        "huggingface": ["huggingface", "transformers"],
        "langchain": ["langchain"],
        "aws": ["aws", "amazon web services"],
        "gcp": ["gcp", "google cloud", "google cloud platform"],
        "azure": ["azure", "microsoft azure"],
        "docker": ["docker"],
        "kubernetes": ["kubernetes", "k8s"],
        "terraform": ["terraform"],
        "ansible": ["ansible"],
        "jenkins": ["jenkins"],
        "github actions": ["github actions", "github-actions"],
        "ci/cd": ["ci/cd", "ci cd", "continuous integration"],
        "helm": ["helm"],
        "airflow": ["airflow"],
        "argo": ["argo"],
        "prometheus": ["prometheus"],
        "grafana": ["grafana"],
        "nginx": ["nginx"],
        "linux": ["linux"],
        "fastapi": ["fastapi"],
        "django": ["django"],
        "flask": ["flask"],
        "node": ["node", "nodejs", "node.js"],
        "express": ["express", "expressjs"],
        "react": ["react"],
        "nextjs": ["nextjs", "next.js"],
        "sql": ["sql", "mysql"],
        "postgresql": ["postgresql", "postgres"],
        "mongodb": ["mongodb"],
        "redis": ["redis"],
        "tableau": ["tableau"],
        "power bi": ["power bi", "powerbi"],
        "excel": ["excel"],
        "agile": ["agile", "scrum"],
    }

    PROJECT_HEADINGS = [
        "projects",
        "project experience",
        "academic projects",
        "personal projects",
    ]

    EDUCATION_HEADINGS = [
        "education",
        "academic background",
        "qualifications",
        "education & certifications",
    ]

    # -------------------------------------------------
    def __init__(self, resume_folder):
        self.resume_folder = resume_folder

    # =================================================
    # 🔥 HYBRID TEXT EXTRACTION
    # =================================================
    def _extract_text(self, pdf_path):
        text = ""

        # ---------- FAST PATH ----------
        try:
            doc = fitz.open(pdf_path)
            for page in doc:
                text += page.get_text()
        except Exception as e:
            print(f"[PDF ERROR] {pdf_path}: {e}")

        # ---------- OCR FALLBACK ----------
        if len(text.strip()) < 50:
            print(f"[OCR] Triggered for {os.path.basename(pdf_path)}")

            try:
                images = convert_from_path(pdf_path, dpi=300)
                ocr_text = ""

                for img in images:
                    raw = pytesseract.image_to_string(img)

                    # basic OCR cleanup
                    raw = re.sub(r"[ \t]+", " ", raw)
                    raw = re.sub(r"\n{3,}", "\n\n", raw)

                    ocr_text += raw

                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text

            except Exception as e:
                print(f"[OCR ERROR] {pdf_path}: {e}")

        return text

    # -------------------------------------------------
    def _extract_email(self, text):
        match = re.search(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            text,
        )
        return match.group(0) if match else "N/A"

    # =================================================
    # 🔥 IMPROVED NAME EXTRACTION
    # =================================================
    def _extract_name(self, filename, text):
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        for line in lines[:6]:
            words = line.split()

            if (
                1 < len(words) <= 4
                and not any(char.isdigit() for char in line)
                and "@" not in line
                and not any(w.lower() in ["engineer", "developer", "resume"] for w in words)
            ):
                if all(w[0].isalpha() for w in words if w):
                    return line.strip()

        return filename.replace(".pdf", "").replace("_", " ")

    # -------------------------------------------------
    def _extract_experience(self, text):
        text_lower = text.lower()

        patterns = [
            r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)",
            r"over\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
            r"around\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
            r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        ]

        values = []

        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for m in matches:
                try:
                    if isinstance(m, tuple):
                        nums = [float(x) for x in m if x]
                        values.append(max(nums))
                    else:
                        values.append(float(m))
                except Exception:
                    continue

        return max(values) if values else 0

    # -------------------------------------------------
    def _extract_skills(self, text):
        text_lower = text.lower()
        found = set()

        for canonical, variants in self.SKILL_MAP.items():
            for v in variants:
                if re.search(rf"\b{re.escape(v.lower())}\b", text_lower):
                    found.add(canonical)
                    break

        return sorted(found)

    # =================================================
    # 🔥 WEAK RESUME DETECTOR
    # =================================================
    def _is_weak_resume(self, text, skills, experience):
        if len(text.strip()) < 200 and len(skills) < 2 and experience == 0:
            return True
        return False

    # =================================================
    # 🔥 LLM STRUCTURED FALLBACK
    # =================================================
    def _llm_structured_parse(self, raw_text, filename):
        if not GROQ_API_KEY:
            print("[LLM FALLBACK] GROQ key missing — skipping")
            return None

        system_prompt = """
You are an expert resume parser.

Extract structured information from the resume text.

Return STRICT JSON with keys:

name: string
email: string
experience_years: number
skills: array of strings
projects_text: string
education_text: string
degree_level: string

Return ONLY JSON.
"""

        try:
            res = requests.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": raw_text[:12000]},
                    ],
                },
                timeout=25,
            )

            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"].strip()

            # remove markdown fences
            if content.startswith("```"):
                parts = content.split("```")
                if len(parts) >= 2:
                    content = parts[1].strip()
                if content.lower().startswith("json"):
                    content = content[4:].strip()

            parsed = json.loads(content)

            print(f"[LLM FALLBACK] Success for {filename}")
            return parsed

        except Exception as e:
            print(f"[LLM FALLBACK ERROR] {filename}: {e}")
            return None

    # =================================================
    # MAIN PARSER
    # =================================================
    def parse_resumes(self):
        results = []

        for file in os.listdir(self.resume_folder):
            if not file.lower().endswith(".pdf"):
                continue

            path = os.path.join(self.resume_folder, file)
            text = self._extract_text(path)

            if not text.strip():
                print(f"[WARNING] No text extracted: {file}")
                continue

            email = self._extract_email(text)
            name = self._extract_name(file, text)
            experience = self._extract_experience(text)
            skills = self._extract_skills(text)

            # =================================================
            # 🔥 ELITE LLM FALLBACK
            # =================================================
            if self._is_weak_resume(text, skills, experience):
                print(f"[WEAK RESUME DETECTED] {file} → using LLM fallback")

                llm_data = self._llm_structured_parse(text, file)

                if llm_data:
                    results.append({
                        "name": llm_data.get("name", name),
                        "email": llm_data.get("email", email),
                        "experience_years": llm_data.get("experience_years", experience),
                        "skills": llm_data.get("skills", skills),
                        "text": text,
                        "projects_text": llm_data.get("projects_text", ""),
                        "education_text": llm_data.get("education_text", ""),
                        "degree_level": llm_data.get("degree_level", "unknown"),
                    })
                    continue

            # ---------- normal deterministic path ----------
            projects_text = ""
            education_text = ""

            results.append({
                "name": name,
                "email": email,
                "experience_years": experience,
                "skills": skills,
                "text": text,
                "projects_text": projects_text,
                "education_text": education_text,
                "degree_level": "unknown",
            })

        print(f"[PARSER] Parsed resumes: {len(results)}")
        return results