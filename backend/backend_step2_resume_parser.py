import os
import re
import json
from typing import Any, Dict, List, Optional
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

    PROJECT_SECTION_END_MARKERS = [
        "education",
        "experience",
        "certification",
        "skills",
        "professional",
        "summary",
        "objective",
        "references",
    ]

    EDUCATION_SECTION_END_MARKERS = [
        "experience",
        "skills",
        "projects",
        "professional",
        "summary",
        "objective",
        "references",
        "certification",
    ]

    EXPERIENCE_PATTERNS = [
        r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)",
        r"over\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        r"around\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        r"(\d+(?:\.\d+)?)\s*(?:to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        r"(?:experience|exp)\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)",
        r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*experience",
        r"worked\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        r"(\d+(?:\.\d+)?)\s*year\s*tenure",
    ]

    NON_NAME_JOB_TITLES = [
        "engineer",
        "developer",
        "manager",
        "analyst",
        "architect",
        "senior",
        "junior",
        "lead",
        "director",
        "consultant",
        "specialist",
    ]

    NON_NAME_CONTACT_KEYWORDS = [
        "phone",
        "email",
        "linkedin",
        "github",
        "portfolio",
        "address",
        "mobile",
        "whatsapp",
        "skype",
        "telegram",
    ]

    MAX_SECTION_LINES = 15
    MAX_NAME_SCAN_LINES = 10
    EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    OCR_MIN_CHAR_THRESHOLD = 100
    OCR_MIN_WORD_THRESHOLD = 50

    WEAK_TEXT_MIN_CHARS = 150
    WEAK_TEXT_WITHOUT_EXPERIENCE_MIN_CHARS = 300
    WEAK_TEXT_WITH_SINGLE_SKILL_MIN_CHARS = 400

    # -------------------------------------------------
    def __init__(self, resume_folder: str):
        self.resume_folder = resume_folder
        self.last_extraction_method = "unknown"
        self._compiled_experience_patterns = [
            re.compile(pattern) for pattern in self.EXPERIENCE_PATTERNS
        ]
        self._compiled_skill_patterns = {
            canonical: [
                re.compile(rf"\b{re.escape(variant.lower())}\b")
                for variant in variants
            ]
            for canonical, variants in self.SKILL_MAP.items()
        }

    def _new_telemetry(self) -> Dict[str, int]:
        return {
            "pdf_seen": 0,
            "parsed": 0,
            "no_text": 0,
            "ocr_used": 0,
            "weak_resume": 0,
            "llm_used": 0,
            "skill_total": 0,
        }

    def _is_pdf_file(self, filename: str) -> bool:
        return filename.lower().endswith(".pdf")

    def _build_resume_path(self, filename: str) -> str:
        return os.path.join(self.resume_folder, filename)

    def _normalize_filename_as_name(self, filename: str) -> str:
        return filename.replace(".pdf", "").replace("_", " ")

    def _is_blank(self, text: str) -> bool:
        return not text.strip()

    def _record_parsed_resume(self, results: List[Dict[str, Any]], telemetry: Dict[str, int], profile: Dict[str, Any]) -> None:
        results.append(profile)
        telemetry["skill_total"] += len(profile["skills"])
        telemetry["parsed"] += 1

    # =================================================
    # 🔥 HYBRID TEXT EXTRACTION
    # =================================================
    def _extract_text(self, pdf_path: str) -> str:
        text = self._extract_text_pymupdf(pdf_path)
        self.last_extraction_method = "pymupdf"

        if not self._should_use_ocr(text):
            return text

        print(f"[OCR] Triggered for {os.path.basename(pdf_path)} (quality check)")
        ocr_text = self._extract_text_ocr(pdf_path)
        if ocr_text is None:
            return text

        if len(ocr_text.strip()) > len(text.strip()):
            self.last_extraction_method = "ocr"
            return ocr_text

        return text

    def _extract_text_pymupdf(self, pdf_path: str) -> str:
        page_text_fragments = []

        # ---------- FAST PATH ----------
        try:
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    page_text_fragments.append(page.get_text())
        except Exception as e:
            print(f"[PDF ERROR] {pdf_path}: {e}")

        return "".join(page_text_fragments)

    def _should_use_ocr(self, text: str) -> bool:
        stripped_text = text.strip()
        word_count = len(stripped_text.split()) if stripped_text else 0
        return len(stripped_text) < self.OCR_MIN_CHAR_THRESHOLD or (
            len(stripped_text) > 0 and word_count < self.OCR_MIN_WORD_THRESHOLD
        )

    def _extract_text_ocr(self, pdf_path: str) -> Optional[str]:
        try:
            images = convert_from_path(pdf_path, dpi=300)
            ocr_fragments = []

            for img in images:
                raw = pytesseract.image_to_string(img)
                ocr_fragments.append(self._clean_ocr_text(raw))

            return "".join(ocr_fragments)
        except Exception as e:
            print(f"[OCR ERROR] {pdf_path}: {e}")
            self.last_extraction_method = "ocr_failed"
            return None

    def _clean_ocr_text(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    # -------------------------------------------------
    def _extract_email(self, text: str) -> str:
        match = self.EMAIL_PATTERN.search(text)
        return match.group(0) if match else "N/A"

    # =================================================
    # 🔥 IMPROVED NAME EXTRACTION
    # =================================================
    def _extract_name(self, filename: str, text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        for line in lines[: self.MAX_NAME_SCAN_LINES]:
            if self._is_probable_name_line(line):
                return line.strip()

        return self._normalize_filename_as_name(filename)

    def _is_probable_name_line(self, line: str) -> bool:
        words = line.split()
        if not (1 <= len(words) <= 5):
            return False

        line_lower = line.lower()
        if any(title in line_lower for title in self.NON_NAME_JOB_TITLES):
            return False
        if any(keyword in line_lower for keyword in self.NON_NAME_CONTACT_KEYWORDS):
            return False

        if sum(1 for char in line if char.isdigit()) > 1:
            return False
        if sum(1 for char in line if not char.isalnum() and char not in " -'") > 2:
            return False

        return all(word[0].isupper() for word in words if word)

    # -------------------------------------------------
    def _extract_experience(self, text: str) -> float:
        text_lower = text.lower()
        values = []

        for pattern in self._compiled_experience_patterns:
            matches = pattern.findall(text_lower)
            self._append_experience_values(matches, values)

        return max(values) if values else 0

    def _append_experience_values(self, matches, values):
        for match in matches:
            try:
                if isinstance(match, tuple):
                    numbers = [float(value) for value in match if value]
                    values.append(max(numbers))
                else:
                    values.append(float(match))
            except Exception:
                continue

    # -------------------------------------------------
    def _extract_skills(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = set()

        for canonical, compiled_variants in self._compiled_skill_patterns.items():
            for variant_pattern in compiled_variants:
                if variant_pattern.search(text_lower):
                    found.add(canonical)
                    break

        return sorted(found)

    # -------------------------------------------------
    def _extract_projects(self, text: str) -> str:
        return self._extract_section_text(
            text=text,
            start_headings=self.PROJECT_HEADINGS,
            end_markers=self.PROJECT_SECTION_END_MARKERS,
        )

    # -------------------------------------------------
    def _extract_education(self, text: str) -> str:
        return self._extract_section_text(
            text=text,
            start_headings=self.EDUCATION_HEADINGS,
            end_markers=self.EDUCATION_SECTION_END_MARKERS,
        )

    def _extract_section_text(self, text: str, start_headings, end_markers) -> str:
        lines = text.split("\n")
        section_lines = []
        in_section = False

        for line in lines:
            line_lower = line.lower().strip()
            if any(heading in line_lower for heading in start_headings):
                in_section = True
                section_lines = []
                continue

            if in_section and any(marker in line_lower for marker in end_markers):
                break

            if in_section and line.strip():
                section_lines.append(line.strip())

        if not section_lines:
            return ""

        return "\n".join(section_lines[: self.MAX_SECTION_LINES])
    # =================================================
    def _is_weak_resume(self, text: str, skills: List[str], experience: float) -> bool:
        # Trigger LLM if ANY weakness detected (was: required ALL - too strict)
        # Changed from AND to OR logic for better robustness
        
        stripped_len = len(text.strip())

        # Very sparse text → likely OCR garbage or placeholder
        if stripped_len < self.WEAK_TEXT_MIN_CHARS:
            return True
        
        # No skills detected → major red flag
        if len(skills) < 1:
            return True
        
        # No experience + incomplete text → weak profile
        if experience == 0 and stripped_len < self.WEAK_TEXT_WITHOUT_EXPERIENCE_MIN_CHARS:
            return True
        
        # If only 1 skill detected and very short → likely parsing failure
        if len(skills) == 1 and stripped_len < self.WEAK_TEXT_WITH_SINGLE_SKILL_MIN_CHARS:
            return True
        
        return False

    # =================================================
    # 🔥 LLM STRUCTURED FALLBACK
    # =================================================
    def _llm_structured_parse(self, raw_text: str, filename: str) -> Optional[Dict[str, Any]]:
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

            content = self._strip_markdown_fences(content)

            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                print(f"[LLM FALLBACK ERROR] {filename}: response is not a JSON object")
                return None

            print(f"[LLM FALLBACK] Success for {filename}")
            return parsed

        except Exception as e:
            print(f"[LLM FALLBACK ERROR] {filename}: {e}")
            return None

    def _strip_markdown_fences(self, content: str) -> str:
        if not content.startswith("```"):
            return content

        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1].strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()
        return content

    def _normalize_llm_skills(self, llm_data: Dict[str, Any], fallback_skills: List[str]) -> List[str]:
        skills = llm_data.get("skills", fallback_skills)
        if isinstance(skills, list):
            return skills
        return fallback_skills

    # =================================================
    # MAIN PARSER
    # =================================================
    def parse_resumes(self) -> List[Dict[str, Any]]:
        results = []
        telemetry = self._new_telemetry()

        for filename in os.listdir(self.resume_folder):
            if not self._is_pdf_file(filename):
                continue
            telemetry["pdf_seen"] += 1

            path = self._build_resume_path(filename)
            text = self._extract_text(path)
            if self.last_extraction_method == "ocr":
                telemetry["ocr_used"] += 1

            if self._is_blank(text):
                print(f"[WARNING] No text extracted: {filename}")
                telemetry["no_text"] += 1
                continue

            profile = self._build_deterministic_profile(filename, text)
            profile, used_llm = self._apply_llm_fallback_if_needed(filename, text, profile, telemetry)

            if used_llm:
                self._record_parsed_resume(results, telemetry, profile)
                continue

            profile["projects_text"] = self._extract_projects(text)
            profile["education_text"] = self._extract_education(text)

            self._record_parsed_resume(results, telemetry, profile)

        print(f"[PARSER] Parsed resumes: {len(results)}")
        avg_skills = round(telemetry["skill_total"] / max(1, telemetry["parsed"]), 2)
        print(
            "[PARSER METRICS] "
            f"seen={telemetry['pdf_seen']} "
            f"parsed={telemetry['parsed']} "
            f"no_text={telemetry['no_text']} "
            f"ocr_used={telemetry['ocr_used']} "
            f"weak={telemetry['weak_resume']} "
            f"llm={telemetry['llm_used']} "
            f"avg_skills={avg_skills}"
        )
        return results

    def _build_deterministic_profile(self, filename: str, text: str) -> Dict[str, Any]:
        return {
            "name": self._extract_name(filename, text),
            "email": self._extract_email(text),
            "experience_years": self._extract_experience(text),
            "skills": self._extract_skills(text),
            "text": text,
            "projects_text": "",
            "education_text": "",
            "degree_level": "unknown",
            "source_file": filename,
        }

    def _apply_llm_fallback_if_needed(self, filename: str, text: str, profile: Dict[str, Any], telemetry: Dict[str, int]):
        if not self._is_weak_resume(text, profile["skills"], profile["experience_years"]):
            return profile, False

        print(f"[WEAK RESUME DETECTED] {filename} → using LLM fallback")
        telemetry["weak_resume"] += 1
        llm_data = self._llm_structured_parse(text, filename)
        if not llm_data:
            return profile, False

        telemetry["llm_used"] += 1
        normalized_skills = self._normalize_llm_skills(llm_data, profile["skills"])

        llm_profile = {
            "name": llm_data.get("name", profile["name"]),
            "email": llm_data.get("email", profile["email"]),
            "experience_years": llm_data.get("experience_years", profile["experience_years"]),
            "skills": normalized_skills,
            "text": text,
            "projects_text": llm_data.get("projects_text", ""),
            "education_text": llm_data.get("education_text", ""),
            "degree_level": llm_data.get("degree_level", "unknown"),
            "source_file": filename,
        }
        return llm_profile, True