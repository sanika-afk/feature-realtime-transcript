"""
Speaker detection and role assignment for medical consultations.
Identifies Doctor, Patient, and Interpreter from audio/video streams.
"""
import logging
from typing import Dict, Optional, List
from collections import Counter

logger = logging.getLogger(__name__)


class SpeakerDetector:
    """
    Detects and assigns roles to speakers in medical consultations.
    
    Methods:
    1. Recall.ai speaker labels (if available)
    2. Voice characteristics (pitch, tone)
    3. Language detection (interpreter switches languages)
    4. Context analysis (medical terminology = doctor)
    5. Speaker ID mapping: speaker_0 → Doctor, speaker_1 → Interpreter
    """
    
    def __init__(self):
        self.speaker_history: Dict[str, List[str]] = {}
        self.role_assignments: Dict[str, str] = {}
        # Speaker buffers for analysis
        self.doctor_buffer: List[str] = []
        self.interpreter_buffer: List[str] = []
        
        # Scoring per speaker to dynamically learn roles
        # Format: {speaker_id: {"Doctor": 0, "Patient": 0, "Interpreter": 0}}
        self.speaker_scores: Dict[str, Dict[str, float]] = {}
        self.locking_threshold = 1.0  # Lowered from 2.0 for faster role assignment
        
        self.allowed_roles = ["Doctor", "Patient", "Interpreter"]
        
    def detect_speaker_role(
        self,
        speaker_id: str,
        text: str,
        language: Optional[str] = None,
        recall_speaker_data: Optional[Dict] = None
    ) -> str:
        """
        Detect the role of a speaker using dynamic scoring and heuristics.
        """
        if speaker_id == "Unknown" or not speaker_id:
            return "Unknown"

        # Initialize scores for new speaker
        if speaker_id not in self.speaker_scores:
            self.speaker_scores[speaker_id] = {"Doctor": 0, "Patient": 0, "Interpreter": 0}

        # If we already "locked" this speaker's role based on threshold
        if speaker_id in self.role_assignments:
            role = self.role_assignments[speaker_id]
            if role == "Interpreter":
                return self._determine_interpreter_direction(speaker_id, text, language)
            return role
        
        # Method 1: Use Recall.ai speaker data if available (High confidence)
        if recall_speaker_data:
            if "name" in recall_speaker_data:
                name = recall_speaker_data["name"].lower()
                if any(kw in name for kw in ["doctor", "dr", "physician"]):
                    self.role_assignments[speaker_id] = "Doctor"
                    return "Doctor"
                elif "patient" in name:
                    self.role_assignments[speaker_id] = "Patient"
                    return "Patient"
                elif any(kw in name for kw in ["interpreter", "translator"]):
                    self.role_assignments[speaker_id] = "Interpreter"
                    return self._determine_interpreter_direction(speaker_id, text, language)
        
        # Method 2: Analyze text content for scoring
        detected_role, score_boost = self._analyze_text_for_scoring(text, language)
        
        if detected_role:
            self.speaker_scores[speaker_id][detected_role] += score_boost
            
            # Check if we should lock the role
            current_score = self.speaker_scores[speaker_id][detected_role]
            if current_score >= self.locking_threshold:
                self.role_assignments[speaker_id] = detected_role
                logger.info(f"[SPEAKER] Locked {speaker_id} as {detected_role} (Score: {current_score})")

            # Return current best guess or locked role
            if detected_role == "Interpreter":
                return self._determine_interpreter_direction(speaker_id, text, language)
            return detected_role
        
        # Fallback: Return current leader even if score is 0
        # This ensures we always return a best guess instead of "Unknown"
        leader = max(self.speaker_scores[speaker_id], key=self.speaker_scores[speaker_id].get)
        if leader == "Interpreter":
            return self._determine_interpreter_direction(speaker_id, text, language)
        
        # If all scores are 0, make an educated guess based on first utterance
        if self.speaker_scores[speaker_id][leader] == 0:
            # Quick heuristic: if text is very short or generic, assume Doctor
            # Most meetings start with doctor greeting
            # Change from 'Doctor' to 'Unknown' for short generic starts to avoid mislabeling
            if len(text.split()) < 3:
                return "Unknown"
            return leader if self.speaker_scores[speaker_id][leader] > 0 else "Unknown"
            # Otherwise return the leader (which will be one of the three roles)
        
        return leader
    
    def _analyze_text_for_scoring(self, text: str, language: Optional[str]) -> tuple[Optional[str], float]:
        """
        Analyze text content and return potential role and importance score.
        """
        text_lower = text.lower()
        
        # Doctor indicators (Clinical questions, instructions, and professional phrases)
        doctor_keywords = [
            "prescription", "prescribe", "dosage", "medication", "medicine", "meds",
            "diagnosis", "treatment", "therapy", "symptoms", "blood pressure", "mg",
            "tablets", "pills", "take twice", "medical", "condition", "test results",
            "how can i help", "describe the pain", "take a seat", "look into your", 
            "follow up", "next appointment", "history", "surgical", "surgery",
            # Spanish Doctor keywords
            "receta", "prescribir", "medicamento", "medicina", "diagnóstico", "tratamiento",
            "síntomas", "presión arterial", "pastillas", "tabletas", "historia médica",
            "cómo puedo ayudar", "describe el dolor"
        ]
        
        # Patient indicators (Symptoms, feelings, history)
        patient_keywords = [
            "i feel", "my pain", "it hurts", "i'm experiencing", "i don't understand", 
            "my leg", "my arm", "my head", "my stomach", "i'm worried", "is it serious", 
            "i noticed", "since yesterday", "dizzy", "nauseous", "nausea", "hurts when i", 
            "the pain is", "it's spreading", "feeling sick", "cold and flu",
            "headache", "migraine", "stomachache", "toothache", "back pain", "chest pain", "i am feeling",
            "not feeling well", "feeling well", "bad today", "hurts a lot", "aching", "ache",
            # Spanish Patient keywords
            "me duele", "tengo dolor", "me siento", "no entiendo", "mi pierna", "mi brazo",
            "mi cabeza", "mi estómago", "estoy preocupado", "es serio", "desde ayer",
            "mareado", "náuseas", "duele cuando", "dolor de cabeza", "migraña"
        ]
        
        # Interpreter indicators (Translation markers and language switching)
        interpreter_keywords = [
            "the doctor says", "the patient says", "he/she is saying", "let me translate", 
            "i will interpret", "doctor wants to know", "patient is asking", "translation for",
            "doctor says", "patient says", "doctor is saying", "patient is saying",
            "doctor asked", "patient asked", "doctor wants", "patient wants",
            "doctor told", "patient told", "he says", "she says",
            "i'm translating", "translating for", "interpreting for",
            "what the doctor", "what the patient", "doctor mentioned", "patient mentioned",
            "interpreter", "translator", "i am the interpreter", "i am your interpreter",
            # Spanish interpreter phrases
            "el doctor dice", "el paciente dice", "dice el doctor", "dice el paciente",
            "el doctor quiere", "el paciente quiere", "el doctor pregunta", "el paciente pregunta"
        ]
        
        # Count keyword matches
        doctor_count = sum(1 for kw in doctor_keywords if kw in text_lower)
        patient_count = sum(1 for kw in patient_keywords if kw in text_lower)
        interpreter_count = sum(1 for kw in interpreter_keywords if kw in text_lower)
        
        # Clinical inquiry questions (High confidence for Doctor/Interpreter)
        clinical_questions = ["do you have", "are you taking", "when did", "where does it hurt", "any allergies"]
        is_clinical_q = any(q in text_lower for q in clinical_questions)
        
        if interpreter_count > 0:
            return "Interpreter", 3.0  # Increased from 2.0 for immediate lock on first detection
        
        if patient_count > 0:
            # Patients describe their own body/feelings
            return "Patient", 1.5 + (0.5 * patient_count)  # Increased base from 1.0
            
        if doctor_count > 0 or is_clinical_q:
            score = 1.5 + (0.5 * doctor_count)  # Increased base from 1.0
            if is_clinical_q: score += 1.0
            return "Doctor", score
            
        return None, 0.0
    
    def _determine_interpreter_direction(
        self,
        speaker_id: str,
        text: str,
        language: Optional[str]
    ) -> str:
        """
        Determine if interpreter is speaking to Patient or Doctor.
        
        Rules:
        - If language is English → likely speaking to Doctor
        - If language is Spanish/other → likely speaking to Patient
        - If text mentions "the doctor says" → speaking to Patient
        - If text mentions "the patient says" → speaking to Doctor
        """
        text_lower = text.lower()
        
        # Check for explicit mentions (more flexible matching)
        if any(kw in text_lower for kw in [
            "the doctor says", "doctor is saying", "doctor wants to know", "doctor is asking",
            "doctor says", "doctor asked", "doctor told", "doctor mentioned", "what the doctor",
            "doctor wants", "doctor needs"
        ]):
            return "Interpreter→Patient"
        elif any(kw in text_lower for kw in [
            "the patient says", "patient is saying", "patient wants to know", "patient is asking",
            "patient says", "patient asked", "patient told", "patient mentioned", "what the patient",
            "patient wants", "patient needs"
        ]):
            return "Interpreter→Doctor"
        
        # Use language as indicator
        if language:
            if language == "en":
                return "Interpreter→Doctor"
            else:
                return "Interpreter→Patient"
        
        # Default
        return "Interpreter→Patient"
    
    def update_from_recall_transcript(
        self,
        transcript_data: Dict
    ) -> Dict[str, str]:
        """
        Extract speaker information from Recall.ai transcript data.
        
        Expected format:
        {
            "speaker": "speaker_0",
            "text": "You need to take two tablets",
            "words": [
                {"text": "You", "start": 0.0, "end": 0.2, "speaker": "speaker_0"}
            ]
        }
        
        Returns:
            Dict with speaker_id and assigned role
        """
        speaker_id = transcript_data.get("speaker", "unknown")
        text = transcript_data.get("text", "")
        
        # Detect language (simplified - you can use a proper language detection library)
        language = self._detect_language(text)
        
        # Get speaker metadata if available
        speaker_metadata = transcript_data.get("speaker_metadata", {})
        
        role = self.detect_speaker_role(
            speaker_id=speaker_id,
            text=text,
            language=language,
            recall_speaker_data=speaker_metadata
        )
        
        return {
            "speaker_id": speaker_id,
            "role": role,
            "text": text,
            "language": language
        }
    
    def _detect_language(self, text: str) -> str:
        """
        Simple language detection based on common words.
        For production, use a library like langdetect or fasttext.
        """
        spanish_words = ["el", "la", "los", "las", "de", "que", "y", "es", "en", "por", "necesitas", "tomar"]
        english_words = ["the", "is", "are", "you", "need", "take", "and", "or", "to", "of"]
        
        text_lower = text.lower()
        words = text_lower.split()
        
        spanish_count = sum(1 for word in words if word in spanish_words)
        english_count = sum(1 for word in words if word in english_words)
        
        if spanish_count > english_count:
            return "es"
        else:
            return "en"
    
    def get_speaker_summary(self) -> Dict[str, str]:
        """Get a summary of all detected speakers and their roles."""
        return self.role_assignments.copy()
    
    def reset(self):
        """Reset all speaker assignments."""
        self.speaker_history.clear()
        self.role_assignments.clear()
    
    def add_to_speaker_buffer(self, speaker_id: str, text: str) -> None:
        """
        Add text to the appropriate speaker buffer based on speaker ID.
        
        Args:
            speaker_id: Speaker identifier (e.g., "speaker_0")
            text: Text to add to buffer
        """
        role = self.detect_speaker_role(speaker_id, text)
        
        if "Doctor" in role:
            self.doctor_buffer.append(text)
        elif "Interpreter" in role:
            self.interpreter_buffer.append(text)
    
    def get_doctor_buffer_text(self) -> str:
        """Get concatenated doctor buffer text."""
        return " ".join(self.doctor_buffer)
    
    def get_interpreter_buffer_text(self) -> str:
        """Get concatenated interpreter buffer text."""
        return " ".join(self.interpreter_buffer)
    
    def get_all_buffers(self) -> Dict[str, str]:
        """Get all speaker buffers."""
        return {
            "doctor": self.get_doctor_buffer_text(),
            "interpreter": self.get_interpreter_buffer_text(),
            "combined": f"Doctor: {self.get_doctor_buffer_text()} | Interpreter: {self.get_interpreter_buffer_text()}"
        }
    
    def clear_buffers(self) -> None:
        """Clear all speaker buffers."""
        self.doctor_buffer.clear()
        self.interpreter_buffer.clear()
    
    def get_buffer_stats(self) -> Dict[str, int]:
        """Get statistics about speaker buffers."""
        return {
            "doctor_segments": len(self.doctor_buffer),
            "interpreter_segments": len(self.interpreter_buffer),
            "doctor_words": len(self.get_doctor_buffer_text().split()),
            "interpreter_words": len(self.get_interpreter_buffer_text().split())
        }


# Global instance
_speaker_detector = SpeakerDetector()


def get_speaker_detector() -> SpeakerDetector:
    """Get the global speaker detector instance."""
    return _speaker_detector
