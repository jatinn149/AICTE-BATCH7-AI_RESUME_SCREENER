import os
import json
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

    # =====================================================
    # MAIN STRUCTURER
    # =====================================================
    @classmethod
    def structure(cls, jd_text: str) -> dict:
        if not GROQ_API_KEY:
            print("[JD STRUCTURER] ❌ GROQ KEY MISSING — using fallback")
            return cls._fallback(jd_text)

        try:
            print("\n" + "=" * 70)
            print("[JD STRUCTURER] 🚀 Sending JD to GROQ")
            print("[JD STRUCTURER] JD Preview:")
            print(jd_text[:500])
            print("=" * 70)

            res = requests.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": cls.SYSTEM_PROMPT},
                        {"role": "user", "content": jd_text},
                    ],
                },
                timeout=20,
            )

            res.raise_for_status()

            raw = res.json()
            content = raw["choices"][0]["message"]["content"]

            print("\n[JD STRUCTURER] ✅ GROQ RAW RESPONSE:")
            print(content[:1000])

            # =================================================
            # 🔥 CRITICAL FIX — STRIP MARKDOWN FENCES
            # =================================================
            cleaned = content.strip()

            # Handle ```json ... ``` or ``` ... ```
            if cleaned.startswith("```"):
                parts = cleaned.split("```")

                # usually format: ["", "json\n{...}", ""]
                if len(parts) >= 2:
                    cleaned = parts[1]

                # remove leading "json"
                cleaned = cleaned.strip()
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()

            # =================================================
            # PARSE JSON SAFELY
            # =================================================
            parsed = json.loads(cleaned)

            print("\n[JD STRUCTURER] ✅ PARSED SCHEMA:")
            print(json.dumps(parsed, indent=2))
            print("=" * 70 + "\n")

            return parsed

        except Exception as e:
            print("\n[JD STRUCTURER] ❌ GROQ FAILED:", str(e))
            print("[JD STRUCTURER] 🔁 USING FALLBACK\n")
            return cls._fallback(jd_text)

    # =====================================================
    # FALLBACK
    # =====================================================
    @staticmethod
    def _fallback(jd_text: str) -> dict:
        return {
            "role_title": "Unknown",
            "core_skills": [],
            "secondary_skills": [],
            "min_experience": None,
            "responsibilities": [],
            "project_expectations": [],
        }
