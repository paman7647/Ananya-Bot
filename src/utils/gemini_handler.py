import logging
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, DEFAULT_PERSONALITY

logger = logging.getLogger(__name__)

class GeminiHandler:
    def __init__(self, api_key: str):
        """Initialize Gemini client with API key"""
        self.client = genai.Client(api_key=api_key)

        # Available models
        self.available_models = {
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-2.5-flash-preview-tts": "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts": "gemini-2.5-pro-preview-tts"
        }
        self.current_model = "gemini-2.5-flash"

        # Default safety settings
        self.safety_settings = {
            "HARASSMENT": "BLOCK_MEDIUM",
            "HATE_SPEECH": "BLOCK_MEDIUM",
            "SEXUALLY_EXPLICIT": "BLOCK_HIGH",
            "DANGEROUS_CONTENT": "BLOCK_MEDIUM"
        }

    async def get_response(
        self,
        prompt: str,
        history: List[Dict] = None,
        personality: str = DEFAULT_PERSONALITY,
        media_parts: list = None,
        use_search: bool = True,
        stream: bool = False,
        model_config: dict = None,
        voice_config: dict = None
    ) -> Union[str, bytes]:
        """Get response from Gemini with optional features"""
        start_time = datetime.now()
        try:
            # Update configuration if provided
            if model_config:
                if model_config.get("model") and model_config["model"] in self.available_models:
                    self.current_model = model_config["model"]
                if model_config.get("safety"):
                    self.safety_settings.update(model_config["safety"])

            model_name = self.available_models.get(self.current_model, "gemini-2.5-flash")

            # Check if this is a TTS model
            is_tts = "tts" in model_name.lower()

            # Build system instruction
            system_instruction = f"""You are Ananya, a helpful and friendly AI with a warm, human-like personality.

{personality}

Guidelines:
- Be helpful, friendly, and engaging
- Talk naturally, as a real person would
- Keep answers concise and to the point
- Answer what the user asks without unnecessary filler
- If you use Google Search results, cite your sources clearly"""

            # Prepare contents
            contents = []

            # Add conversation history
            if history:
                for msg in history[-10:]:  # Keep last 10 messages
                    if msg.get('role') == 'user':
                        user_parts = []
                        if msg.get('media_parts'):
                            for media in msg['media_parts']:
                                if isinstance(media, dict) and 'inline_data' in media:
                                    user_parts.append(types.Part(
                                        inline_data=types.Blob(
                                            mime_type=media['inline_data']['mime_type'],
                                            data=media['inline_data']['data']
                                        )
                                    ))
                        user_parts.append(types.Part(text=msg.get('content', '')))
                        contents.append(types.Content(role="user", parts=user_parts))
                    elif msg.get('role') == 'assistant':
                        contents.append(types.Content(
                            role="model",
                            parts=[types.Part(text=msg.get('content', ''))]
                        ))

            # Add current user message
            user_parts = []
            if media_parts:
                for media in media_parts:
                    if isinstance(media, dict) and 'inline_data' in media:
                        user_parts.append(types.Part(
                            inline_data=types.Blob(
                                mime_type=media['inline_data']['mime_type'],
                                data=media['inline_data']['data']
                            )
                        ))
            user_parts.append(types.Part(text=prompt))
            contents.append(types.Content(role="user", parts=user_parts))

            # Configure generation
            config_kwargs = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 4096,
                "system_instruction": system_instruction
            }

            # Add tools if needed
            tools = []
            if use_search:
                tools.append(types.Tool(google_search=types.GoogleSearch()))

            if tools:
                config_kwargs["tools"] = tools

            # For TTS models, configure speech
            if is_tts and voice_config:
                config_kwargs["speech_config"] = types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_config.get("voice_name", "Zephyr")
                        )
                    )
                )

            config = types.GenerateContentConfig(**config_kwargs)

            # Generate response
            if stream:
                import asyncio
                response = self.client.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=config
                )
                full_response = ""
                # Collect all chunks synchronously
                chunks = list(response)
                for chunk in chunks:
                    if chunk.candidates and chunk.candidates[0].content:
                        for part in chunk.candidates[0].content.parts:
                            if part.text:
                                full_response += part.text
                            elif part.inline_data:
                                # For audio responses
                                return part.inline_data.data
                return full_response
            else:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )

                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.text:
                                return part.text
                            elif part.inline_data:
                                # Return audio data for TTS
                                return part.inline_data.data

            return "I apologize, but I couldn't generate a response. Please try again."

        except Exception as e:
            logger.error(f"Error in get_response: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

    async def generate_speech(
        self,
        text: str,
        voice_name: str = "Zephyr",
        model: str = "gemini-2.5-flash-preview-tts"
    ) -> bytes:
        """Generate speech from text"""
        try:
            if model not in self.available_models:
                model = "gemini-2.5-flash-preview-tts"

            config = types.GenerateContentConfig(
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                )
            )

            response = self.client.models.generate_content(
                model=self.available_models[model],
                contents=[text],
                config=config
            )

            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        return part.inline_data.data

            raise ValueError("No audio data in response")

        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            raise

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return list(self.available_models.keys())

    def get_grounding_metadata(self, response) -> Optional[Dict]:
        """Extract grounding metadata from response"""
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata'):
                return candidate.grounding_metadata
        return None

# Create a global instance
gemini_handler = GeminiHandler(GEMINI_API_KEY)
