# core/llm/groq_client.py
"""
Complete Groq LLM Client with Multilingual Support
Provides OpenAI-compatible interface with Groq's lightning-fast models
Supports automatic language detection and response in user's language
"""

import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
import httpx
from openai import AsyncOpenAI
from config.settings import settings
import logging
import json

logger = logging.getLogger(__name__)

class GroqClient:
    """
    Async Groq client with multilingual support
    Automatically detects user language and responds accordingly
    """
    
    def __init__(self):
        self.client = None
        self.available_models = {
            # Best quality model with massive context
            "llama-3.3-70b-versatile": {
                "name": "llama-3.3-70b-versatile",
                "context_window": 131072,  # 131k tokens!
                "max_completion": 32768,
                "speed": "fast",
                "use_case": "primary_model"
            },
            # Alternative quality models
            "openai/gpt-oss-120b": {
                "name": "openai/gpt-oss-120b",
                "context_window": 131072,
                "max_completion": 65536,
                "speed": "good",
                "use_case": "complex_reasoning"
            },
            "openai/gpt-oss-20b": {
                "name": "openai/gpt-oss-20b",
                "context_window": 131072,
                "max_completion": 65536,
                "speed": "fast",
                "use_case": "balanced_option"
            },
            # Avoiding llama-3.1-8b-instant due to quality issues
            
            # Voice transcription models
            "whisper-large-v3-turbo": {
                "name": "whisper-large-v3-turbo",
                "max_file_size": "100MB",
                "use_case": "voice_transcription"
            },
            
            # Production systems (compound models)
            "groq/compound": {
                "name": "groq/compound",
                "context_window": 131072,
                "max_completion": 8192,
                "use_case": "production_system"
            }
        }
        
        # Supported languages for retail AI
        self.supported_languages = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "nl": "Dutch",
            "ru": "Russian",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic",
            "hi": "Hindi",
            "ur": "Urdu",
            "bn": "Bengali",
            "pa": "Punjabi",
            "tr": "Turkish",
            "vi": "Vietnamese",
            "th": "Thai",
            "id": "Indonesian"
        }
        
    async def initialize(self):
        """Initialize the Groq client with OpenAI SDK"""
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
            
        self.client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=30.0,
            max_retries=3
        )
        
        logger.info(f"✅ Groq client initialized with model: {settings.llm_model_name}")
        
    async def test_connection(self):
        """Test the Groq connection"""
        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_model_name,
                messages=[
                    {"role": "user", "content": "Say 'Connection successful!' in 5 words or less"}
                ],
                temperature=0.1,
                max_tokens=20
            )
            return f"✅ Groq connected! Response: {response.choices[0].message.content}"
        except Exception as e:
            return f"❌ Groq connection failed: {e}"
    
    async def detect_language(self, text: str) -> Tuple[str, str]:
        """
        Detect the language of the input text
        Returns: (language_code, language_name)
        """
        try:
            detection_prompt = f"""Detect the language of this text and respond with ONLY a JSON object:
            Text: "{text}"
            
            Response format:
            {{"language_code": "en", "language_name": "English", "confidence": 0.95}}
            
            Use ISO 639-1 codes (en, es, fr, de, etc.)"""
            
            response = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a language detection system. Respond only with JSON."},
                    {"role": "user", "content": detection_prompt}
                ],
                temperature=0.1,
                max_tokens=50,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("language_code", "en"), result.get("language_name", "English")
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}, defaulting to English")
            return "en", "English"
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None,
        target_language: Optional[str] = None,
        auto_detect_language: bool = True,
        **kwargs
    ) -> str:
        """
        Get chat completion from Groq with multilingual support
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Override default model
            temperature: Control randomness (0-1)
            max_tokens: Maximum response length
            response_format: JSON mode if needed
            target_language: Force response in specific language (e.g., 'es', 'fr')
            auto_detect_language: Automatically detect and respond in user's language
            **kwargs: Additional parameters
            
        Returns:
            Generated response text in the appropriate language
        """
        try:
            # Detect language if needed
            if auto_detect_language and not target_language and messages:
                # Get the last user message for language detection
                user_messages = [m for m in messages if m.get("role") == "user"]
                if user_messages:
                    detected_lang, lang_name = await self.detect_language(user_messages[-1]["content"])
                    target_language = detected_lang
                    logger.info(f"Detected language: {lang_name} ({detected_lang})")
            
            # Add language instruction to system message if needed
            if target_language and target_language != "en":
                language_name = self.supported_languages.get(target_language, target_language)
                language_instruction = f"\n\nIMPORTANT: Respond in {language_name} language."
                
                # Modify or add system message
                modified_messages = []
                has_system = False
                
                for msg in messages:
                    if msg["role"] == "system":
                        has_system = True
                        modified_messages.append({
                            "role": "system",
                            "content": msg["content"] + language_instruction
                        })
                    else:
                        modified_messages.append(msg)
                
                if not has_system:
                    modified_messages.insert(0, {
                        "role": "system",
                        "content": f"You are a helpful retail assistant.{language_instruction}"
                    })
                
                messages = modified_messages
            
            response = await self.client.chat.completions.create(
                model=model or settings.llm_model_name,
                messages=messages,
                temperature=temperature or settings.temperature,
                max_tokens=max_tokens or settings.max_tokens,
                response_format=response_format,
                **kwargs
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Groq completion error: {e}")
            
            # Fallback to alternative model if primary fails
            if model == "llama-3.3-70b-versatile" and "openai/gpt-oss-20b" in self.available_models:
                logger.info("Falling back to openai/gpt-oss-20b")
                return await self.chat_completion(
                    messages=messages,
                    model="openai/gpt-oss-20b",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    target_language=target_language,
                    auto_detect_language=False,  # Don't detect again
                    **kwargs
                )
            raise
    
    async def streaming_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        target_language: Optional[str] = None,
        auto_detect_language: bool = True,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion for real-time responses with language support
        """
        try:
            # Detect language if needed
            if auto_detect_language and not target_language and messages:
                user_messages = [m for m in messages if m.get("role") == "user"]
                if user_messages:
                    detected_lang, _ = await self.detect_language(user_messages[-1]["content"])
                    target_language = detected_lang
            
            # Add language instruction
            if target_language and target_language != "en":
                language_name = self.supported_languages.get(target_language, target_language)
                for i, msg in enumerate(messages):
                    if msg["role"] == "system":
                        messages[i]["content"] += f"\n\nRespond in {language_name}."
                        break
                else:
                    messages.insert(0, {
                        "role": "system",
                        "content": f"You are a helpful assistant. Respond in {language_name}."
                    })
            
            stream = await self.client.chat.completions.create(
                model=model or settings.llm_model_name,
                messages=messages,
                temperature=temperature or settings.temperature,
                max_tokens=max_tokens or settings.max_tokens,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"❌ Groq streaming error: {e}")
            yield "I'm sorry, I'm having trouble generating a response right now."
    
    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None
    ) -> str:
        """
        Translate text to target language
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'es', 'fr')
            source_language: Source language code (auto-detect if None)
            
        Returns:
            Translated text
        """
        try:
            if not source_language:
                source_language, _ = await self.detect_language(text)
            
            source_name = self.supported_languages.get(source_language, source_language)
            target_name = self.supported_languages.get(target_language, target_language)
            
            translation_prompt = f"""Translate the following text from {source_name} to {target_name}.
            Provide ONLY the translation, no explanations or notes.
            
            Text: {text}
            
            Translation:"""
            
            response = await self.client.chat.completions.create(
                model=settings.llm_model_name,
                messages=[
                    {"role": "user", "content": translation_prompt}
                ],
                temperature=0.3,
                max_tokens=max(len(text) * 2, 100)  # Ensure enough tokens for translation
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text  # Return original text if translation fails
    
    async def transcribe_audio(
        self,
        audio_file_path: str,
        model: str = "whisper-large-v3-turbo",
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio file (for WhatsApp voice messages)
        
        Args:
            audio_file_path: Path to audio file
            model: Whisper model to use
            language: Hint for language (optional)
            
        Returns:
            Dict with transcribed text and detected language
        """
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = await self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language=language,  # Optional language hint
                    response_format="verbose_json"  # Get more details
                )
            
            # Detect language of transcribed text
            detected_lang, lang_name = await self.detect_language(transcription.text)
            
            return {
                "text": transcription.text,
                "language": detected_lang,
                "language_name": lang_name,
                "duration": getattr(transcription, 'duration', None)
            }
            
        except Exception as e:
            logger.error(f"❌ Audio transcription error: {e}")
            raise
    
    def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about a specific model"""
        model = model_name or settings.llm_model_name
        return self.available_models.get(model, {
            "name": model,
            "info": "Model information not available"
        })
    
    def is_language_supported(self, language_code: str) -> bool:
        """Check if a language is supported"""
        return language_code.lower() in self.supported_languages

# Singleton instance
groq_client = GroqClient()

# Helper functions for quick access
async def get_groq_response(
    messages: List[Dict[str, str]],
    target_language: Optional[str] = None,
    **kwargs
) -> str:
    """Quick helper to get a Groq response with language support"""
    if not groq_client.client:
        await groq_client.initialize()
    return await groq_client.chat_completion(
        messages, 
        target_language=target_language,
        **kwargs
    )

async def detect_user_language(text: str) -> Tuple[str, str]:
    """Quick helper to detect language"""
    if not groq_client.client:
        await groq_client.initialize()
    return await groq_client.detect_language(text)

async def translate(text: str, to_language: str, from_language: Optional[str] = None) -> str:
    """Quick helper for translation"""
    if not groq_client.client:
        await groq_client.initialize()
    return await groq_client.translate_text(text, to_language, from_language)