import os
import json
from typing import Any, Dict, List
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class JDStructurer:
    SYSTEM_PROMPT = """
You are an expert ATS job description parser.

Extract structured fields from the job description.

Return STRICT JSON with keys:

role_title: string
core_skills: array of strings
secondary_skills: array of strings
min_experience: string or null
responsibilities: array of strings
project_expectations: array of strings

Return ONLY JSON.
"""

    ROLE_HINTS = {
        "devops": ["devops", "site reliability", "sre", "infrastructure"],
        "ml": ["machine learning", "ml engineer", "ai engineer", "deep learning"],
        "fullstack": ["full stack", "fullstack"],
        "backend": ["backend", "api", "microservice"],
        "frontend": ["frontend", "react", "angular", "vue"],
        "data": ["data scientist", "data analyst", "analytics"],
        "security": ["security", "cybersecurity", "soc", "siem"],
    }

    SKILL_HINTS = {
        "python": ["python"],
        "java": ["java"],
        "sql": ["sql", "mysql", "postgresql", "postgres"],
        "aws": ["aws", "amazon web services"],
        "gcp": ["gcp", "google cloud"],
        "azure": ["azure"],
        "docker": ["docker"],
        "kubernetes": ["kubernetes", "k8s"],
        "terraform": ["terraform"],
        "jenkins": ["jenkins"],
        "ci/cd": ["ci/cd", "ci cd", "continuous integration"],
        "fastapi": ["fastapi"],
        "django": ["django"],
        "flask": ["flask"],
        "react": ["react"],
        "node": ["node", "nodejs", "node.js"],
        "pytorch": ["pytorch", "torch"],
        "tensorflow": ["tensorflow"],
        "nlp": ["nlp", "natural language processing"],
        "tableau": ["tableau"],
        "power bi": ["power bi", "powerbi"],
    }

    GROQ_MODEL = "llama-3.3-70b-versatile"
    GROQ_TEMPERATURE = 0.2
    GROQ_TIMEOUT_SECONDS = 20
    JD_PREVIEW_CHARS = 500
    RESPONSE_PREVIEW_CHARS = 1000
    HTTP_SESSION = requests.Session()

    DEFAULT_SCHEMA = {
        "role_title": "Unknown",
        "core_skills": [],
        "secondary_skills": [],
        "min_experience": None,
        "responsibilities": [],
        "project_expectations": [],
    }

    # =====================================================
    # MAIN STRUCTURER
    # =====================================================
    @classmethod
    def structure(cls, jd_text: str) -> Dict[str, Any]:
        normalized_text = cls._normalize_text(jd_text)

        if not cls._has_groq_key():
            print("[JD STRUCTURER] ❌ GROQ KEY MISSING — using fallback")
            return cls._build_fallback_with_metrics(jd_text, normalized_text, source="fallback")

        try:
            cls._log_request_start(jd_text)
            content = cls._request_structured_content(jd_text)
            cls._log_raw_response(content)

            parsed_schema = cls._parse_and_normalize(content, normalized_text)
            cls._log_success(parsed_schema)
            return parsed_schema
        except Exception as e:
            cls._log_failure(e)
            return cls._build_fallback_with_metrics(jd_text, normalized_text, source="fallback_after_error")

    @staticmethod
    def _normalize_text(text: str) -> str:
        return (text or "").lower()

    @staticmethod
    def _has_groq_key() -> bool:
        return bool(GROQ_API_KEY)

    @classmethod
    def _build_fallback_with_metrics(cls, jd_text: str, normalized_text: str, source: str) -> Dict[str, Any]:
        fallback = cls._fallback(jd_text, normalized_text)
        cls._log_schema_quality(fallback, source=source)
        return fallback

    @staticmethod
    def _log_request_start(jd_text: str):
        print("\n" + "=" * 70)
        print("[JD STRUCTURER] 🚀 Sending JD to GROQ")
        print("[JD STRUCTURER] JD Preview:")
        print(jd_text[: JDStructurer.JD_PREVIEW_CHARS])
        print("=" * 70)

    @classmethod
    def _request_structured_content(cls, jd_text: str) -> str:
        response = cls.HTTP_SESSION.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=cls._build_groq_payload(jd_text),
            timeout=cls.GROQ_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        response_payload = response.json()
        return cls._extract_message_content(response_payload)

    @staticmethod
    def _extract_message_content(response_payload: Dict[str, Any]) -> str:
        try:
            return response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("Unexpected GROQ response structure") from error

    @classmethod
    def _build_groq_payload(cls, jd_text: str) -> Dict[str, Any]:
        return {
            "model": cls.GROQ_MODEL,
            "temperature": cls.GROQ_TEMPERATURE,
            "messages": [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": jd_text},
            ],
        }

    @staticmethod
    def _log_raw_response(content: str):
        print("\n[JD STRUCTURER] ✅ GROQ RAW RESPONSE:")
        print(content[: JDStructurer.RESPONSE_PREVIEW_CHARS])

    @classmethod
    def _parse_and_normalize(cls, content: str, normalized_text: str) -> Dict[str, Any]:
        cleaned_content = cls._strip_markdown_fences(content)
        parsed = json.loads(cleaned_content)
        return cls._normalize_schema(parsed, normalized_text)

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        cleaned = content.strip()
        if not cleaned.startswith("```"):
            return cleaned

        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]

        cleaned = cleaned.strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

        return cleaned

    @classmethod
    def _log_success(cls, parsed_schema: Dict[str, Any]):
        print("\n[JD STRUCTURER] ✅ PARSED SCHEMA:")
        print(json.dumps(parsed_schema, indent=2))
        cls._log_schema_quality(parsed_schema, source="groq")
        print("=" * 70 + "\n")

    @staticmethod
    def _log_failure(error: Exception):
        print("\n[JD STRUCTURER] ❌ GROQ FAILED:", str(error))
        print("[JD STRUCTURER] 🔁 USING FALLBACK\n")

    @classmethod
    def _normalize_schema(cls, parsed: Dict[str, Any], normalized_text: str) -> Dict[str, Any]:
        schema = dict(cls.DEFAULT_SCHEMA)
        if isinstance(parsed, dict):
            schema.update(parsed)

        if not schema["core_skills"]:
            schema["core_skills"] = cls._extract_skills_from_normalized_text(normalized_text)

        if not schema.get("role_title") or str(schema.get("role_title")).strip().lower() in {"unknown", "n/a", "na"}:
            schema["role_title"] = cls._infer_role_title_from_normalized_text(normalized_text)

        return schema

    # =====================================================
    # FALLBACK
    # =====================================================
    @classmethod
    def _fallback(cls, jd_text: str, normalized_text: str = "") -> Dict[str, Any]:
        if not normalized_text:
            normalized_text = cls._normalize_text(jd_text)

        core_skills = cls._extract_skills_from_normalized_text(normalized_text)
        role_title = cls._infer_role_title_from_normalized_text(normalized_text)
        return {
            "role_title": role_title,
            "core_skills": core_skills,
            "secondary_skills": [],
            "min_experience": None,
            "responsibilities": [],
            "project_expectations": [],
        }

    @classmethod
    def _extract_skills_from_normalized_text(cls, normalized_text: str) -> List[str]:
        found = []
        for canonical, hints in cls.SKILL_HINTS.items():
            if any(hint in normalized_text for hint in hints):
                found.append(canonical)
        return found

    @classmethod
    def _infer_role_title_from_normalized_text(cls, normalized_text: str) -> str:
        best_role = "Unknown"
        best_score = 0

        for role, hints in cls.ROLE_HINTS.items():
            score = sum(normalized_text.count(hint) for hint in hints)
            if score > best_score:
                best_score = score
                best_role = role

        if best_role == "Unknown":
            return "Unknown"
        return best_role.title()

    @staticmethod
    def _log_schema_quality(schema: Dict[str, Any], source: str):
        print(
            "[JD STRUCTURE METRICS] "
            f"source={source} "
            f"role={schema.get('role_title', 'Unknown')} "
            f"core_skills={len(schema.get('core_skills', []))} "
            f"secondary_skills={len(schema.get('secondary_skills', []))} "
            f"responsibilities={len(schema.get('responsibilities', []))} "
            f"projects={len(schema.get('project_expectations', []))} "
            f"min_experience={'yes' if schema.get('min_experience') else 'no'}"
        )
