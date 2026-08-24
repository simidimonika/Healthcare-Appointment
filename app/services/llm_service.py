import json
import logging
import re
from typing import Dict, Any, List
import httpx
from app.config import settings

logger = logging.getLogger("llm_service")


class LLMService:
    @staticmethod
    def _heuristic_pre_visit_summary(symptoms: str) -> Dict[str, Any]:
        """Resilient fallback extractor for Pre-visit symptom analysis when LLM API is unavailable."""
        symptoms_lower = symptoms.lower()
        
        # Determine Urgency Level based on clinical danger keywords
        high_urgency_keywords = [
            "chest pain", "shortness of breath", "difficulty breathing", "severe bleeding", 
            "unconscious", "stroke", "paralysis", "sudden loss of vision", "severe burn",
            "heart attack", "crushing pain", "anaphylaxis", "coughing blood", "high fever 104"
        ]
        medium_urgency_keywords = [
            "fever", "moderate pain", "persistent cough", "vomiting", "diarrhea", 
            "dizziness", "migraine", "infection", "rash", "fracture", "swelling", 
            "burn", "asthma", "flu", "sprain", "urinary tract", "stomach pain"
        ]
        
        urgency = "Low"
        if any(keyword in symptoms_lower for keyword in high_urgency_keywords):
            urgency = "High"
        elif any(keyword in symptoms_lower for keyword in medium_urgency_keywords) or len(symptoms.split()) > 20:
            urgency = "Medium"

        # Extract Chief Complaint
        first_sentence = symptoms.strip().split(".")[0].split("\n")[0]
        chief_complaint = first_sentence if len(first_sentence) < 120 else first_sentence[:117] + "..."

        # Generate 3 relevant clinical questions for the doctor
        suggested_questions = [
            f"How long have you been experiencing '{chief_complaint}' and has the intensity changed over time?",
            "Are you currently taking any prescription medications or over-the-counter remedies for these symptoms?",
            "Have you noticed any associated triggers, dietary factors, or physical limitations since onset?"
        ]

        if urgency == "High":
            suggested_questions[0] = "Are you experiencing any radiating discomfort, dizziness, or sudden numbness?"

        return {
            "urgency_level": urgency,
            "chief_complaint": chief_complaint,
            "suggested_questions": suggested_questions,
            "is_fallback": True
        }

    @staticmethod
    def _heuristic_post_visit_summary(clinical_notes: str, prescriptions: str = "") -> Dict[str, Any]:
        """Resilient fallback parser for Post-visit patient summary when LLM API is unavailable."""
        summary = (
            f"Thank you for attending your consultation today. Your doctor has evaluated your condition and "
            f"documented the following diagnosis and assessment:\n\n{clinical_notes.strip()}"
        )
        
        if prescriptions and prescriptions.strip():
            med_schedule = (
                f"Prescribed Medications & Regimen:\n{prescriptions.strip()}\n\n"
                f"Please ensure all medications are taken strictly according to the designated dosage and frequency. "
                f"Do not discontinue early without consulting your physician."
            )
        else:
            med_schedule = "No active prescription medications added for this visit. Continue taking existing home regimens as discussed."

        follow_up = (
            "1. Monitor your symptoms daily and record any adverse changes or discomfort.\n"
            "2. Stay adequately hydrated, maintain balanced nutrition, and get plenty of rest.\n"
            "3. Schedule a follow-up appointment in 1-2 weeks or immediately seek emergency care if symptoms worsen."
        )

        return {
            "patient_friendly_summary": summary,
            "medication_schedule": med_schedule,
            "follow_up_steps": follow_up,
            "is_fallback": True
        }

    @classmethod
    async def generate_pre_visit_summary(cls, symptoms: str) -> Dict[str, Any]:
        """
        Generate AI pre-visit summary using standard prompt:
        'Analyse these symptoms and return: urgency level (Low / Medium / High), chief complaint, and three suggested questions for the doctor. Symptoms: <symptoms>'
        """
        prompt = (
            f"Analyse these symptoms and return: urgency level (Low / Medium / High), chief complaint, and three suggested questions for the doctor. "
            f"Symptoms: {symptoms}\n\n"
            f"Respond STRICTLY in valid JSON format with the following keys:\n"
            f'{{"urgency_level": "Low|Medium|High", "chief_complaint": "string", "suggested_questions": ["q1", "q2", "q3"]}}'
        )

        # Try Google Gemini API if configured
        if settings.GEMINI_API_KEY and settings.LLM_PROVIDER in ["gemini", "auto"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        # Clean JSON code blocks if present
                        cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
                        parsed = json.loads(cleaned)
                        return {
                            "urgency_level": parsed.get("urgency_level", "Medium"),
                            "chief_complaint": parsed.get("chief_complaint", symptoms[:100]),
                            "suggested_questions": parsed.get("suggested_questions", []),
                            "is_fallback": False
                        }
            except Exception as exc:
                logger.warning(f"Gemini API pre-visit call failed: {exc}. Using fallback parser.")

        # Try OpenAI API if configured
        if settings.OPENAI_API_KEY and settings.LLM_PROVIDER in ["openai", "auto"]:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_text = data["choices"][0]["message"]["content"]
                        parsed = json.loads(raw_text)
                        return {
                            "urgency_level": parsed.get("urgency_level", "Medium"),
                            "chief_complaint": parsed.get("chief_complaint", symptoms[:100]),
                            "suggested_questions": parsed.get("suggested_questions", []),
                            "is_fallback": False
                        }
            except Exception as exc:
                logger.warning(f"OpenAI API pre-visit call failed: {exc}. Using fallback parser.")

        # Graceful fallback heuristic engine
        return cls._heuristic_pre_visit_summary(symptoms)

    @classmethod
    async def generate_post_visit_summary(cls, clinical_notes: str, prescriptions: str = "") -> Dict[str, Any]:
        """
        Generate AI post-visit summary using standard prompt:
        'Convert these clinical notes into a patient-friendly summary with medication schedule and follow-up steps: <notes>'
        """
        combined_notes = f"{clinical_notes}\nPrescriptions: {prescriptions}" if prescriptions else clinical_notes
        prompt = (
            f"Convert these clinical notes into a patient-friendly summary with medication schedule and follow-up steps: {combined_notes}\n\n"
            f"Respond STRICTLY in valid JSON format with the following keys:\n"
            f'{{"patient_friendly_summary": "easy to understand plain English explanation for the patient", '
            f'"medication_schedule": "clear schedule of when and how to take prescribed medications", '
            f'"follow_up_steps": "bullet points of precautions, lifestyle, and follow-up visit dates"}}'
        )

        # Try Google Gemini API
        if settings.GEMINI_API_KEY and settings.LLM_PROVIDER in ["gemini", "auto"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"}
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
                        parsed = json.loads(cleaned)
                        return {
                            "patient_friendly_summary": parsed.get("patient_friendly_summary", clinical_notes),
                            "medication_schedule": parsed.get("medication_schedule", prescriptions),
                            "follow_up_steps": parsed.get("follow_up_steps", "Follow up in 2 weeks."),
                            "is_fallback": False
                        }
            except Exception as exc:
                logger.warning(f"Gemini API post-visit call failed: {exc}. Using fallback parser.")

        # Try OpenAI API
        if settings.OPENAI_API_KEY and settings.LLM_PROVIDER in ["openai", "auto"]:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_text = data["choices"][0]["message"]["content"]
                        parsed = json.loads(raw_text)
                        return {
                            "patient_friendly_summary": parsed.get("patient_friendly_summary", clinical_notes),
                            "medication_schedule": parsed.get("medication_schedule", prescriptions),
                            "follow_up_steps": parsed.get("follow_up_steps", "Follow up in 2 weeks."),
                            "is_fallback": False
                        }
            except Exception as exc:
                logger.warning(f"OpenAI API post-visit call failed: {exc}. Using fallback parser.")

        # Fallback parser
        return cls._heuristic_post_visit_summary(clinical_notes, prescriptions)
