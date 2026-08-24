import pytest
from app.services.llm_service import LLMService


@pytest.mark.asyncio
async def test_llm_pre_visit_high_urgency():
    symptoms = "Severe crushing chest pain radiating to left jaw, accompanied by shortness of breath for 1 hour."
    result = await LLMService.generate_pre_visit_summary(symptoms)
    
    assert result["urgency_level"] == "High"
    assert "chief_complaint" in result
    assert len(result["suggested_questions"]) == 3
    assert isinstance(result["suggested_questions"], list)


@pytest.mark.asyncio
async def test_llm_pre_visit_low_medium_urgency():
    symptoms = "Mild dry cough and seasonal runny nose for 2 days."
    result = await LLMService.generate_pre_visit_summary(symptoms)
    
    assert result["urgency_level"] in ["Low", "Medium"]
    assert "chief_complaint" in result
    assert len(result["suggested_questions"]) == 3


@pytest.mark.asyncio
async def test_llm_post_visit_summary():
    clinical_notes = "Acute pharyngitis. Posterior oropharynx is erythematous. Rapid strep negative. Hydration advised."
    prescriptions = "Acetaminophen 500mg - Twice daily as needed for throat soreness."
    
    result = await LLMService.generate_post_visit_summary(clinical_notes, prescriptions)
    
    assert "patient_friendly_summary" in result
    assert "medication_schedule" in result
    assert "follow_up_steps" in result
    assert len(result["patient_friendly_summary"]) > 20


@pytest.mark.asyncio
async def test_llm_graceful_fallback_resilience():
    # Calling internal fallback directly to ensure robust parsing
    fallback = LLMService._heuristic_pre_visit_summary("Persistent migraine headache with light sensitivity")
    assert fallback["urgency_level"] in ["Low", "Medium", "High"]
    assert fallback["is_fallback"] is True
    assert len(fallback["suggested_questions"]) == 3
