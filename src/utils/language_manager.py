import logging
from typing import Optional, Tuple, Dict
from google.cloud import translate_v2 as translate
from datetime import datetime

logger = logging.getLogger(__name__)

class LanguageManager:
    def __init__(self):
        """Initialize language manager with offline fallbacks"""
        # Try to initialize Google Cloud clients, but don't fail if not available
        self.translate_client = None
        self.tts_client = None
        self.speech_client = None
        
        try:
            from google.cloud import translate_v2 as translate
            self.translate_client = translate.Client()
            logger.info("Google Translate client initialized")
        except Exception as e:
            logger.warning(f"Google Translate not available: {e}")
            
        try:
            from google.cloud import texttospeech, speech
            self.tts_client = texttospeech.TextToSpeechClient()
            self.speech_client = speech.SpeechClient()
            logger.info("Google Cloud TTS/STT clients initialized")
        except Exception as e:
            logger.warning(f"Google Cloud TTS/STT not available: {e}")
        
        # Define supported languages with their display info
        self.SUPPORTED_LANGUAGES = {
            'auto': {
                'name': 'Auto-detect',
                'native_name': 'Auto-detect',
                'flag': '🔄'
            },
            'en': {
                'name': 'English',
                'native_name': 'English',
                'flag': '🇬🇧',
                'variants': {
                    'en-IN': 'India',
                    'en-US': 'United States',
                    'en-GB': 'United Kingdom'
                }
            },
            'hi': {
                'name': 'Hindi',
                'native_name': 'हिन्दी',
                'flag': '🇮🇳',
                'variants': {
                    'hi-IN': 'India'
                }
            },
            'bn': {
                'name': 'Bengali',
                'native_name': 'বাংলা',
                'flag': '🇮🇳',
                'variants': {
                    'bn-IN': 'India'
                }
            },
            'ta': {
                'name': 'Tamil',
                'native_name': 'தமிழ்',
                'flag': '🇮🇳',
                'variants': {
                    'ta-IN': 'India'
                }
            },
            'te': {
                'name': 'Telugu',
                'native_name': 'తెలుగు',
                'flag': '🇮🇳',
                'variants': {
                    'te-IN': 'India'
                }
            },
            'kn': {
                'name': 'Kannada',
                'native_name': 'ಕನ್ನಡ',
                'flag': '🇮🇳',
                'variants': {
                    'kn-IN': 'India'
                }
            },
            'ml': {
                'name': 'Malayalam',
                'native_name': 'മലയാളം',
                'flag': '🇮🇳',
                'variants': {
                    'ml-IN': 'India'
                }
            },
            'gu': {
                'name': 'Gujarati',
                'native_name': 'ગુજરાતી',
                'flag': '🇮🇳',
                'variants': {
                    'gu-IN': 'India'
                }
            },
            'mr': {
                'name': 'Marathi',
                'native_name': 'मराठी',
                'flag': '🇮🇳',
                'variants': {
                    'mr-IN': 'India'
                }
            },
            'pa': {
                'name': 'Punjabi',
                'native_name': 'ਪੰਜਾਬੀ',
                'flag': '🇮🇳',
                'variants': {
                    'pa-IN': 'India'
                }
            }
        }
        
    async def detect_language(self, text: str) -> Tuple[str, float]:
        """Detect the language of the text with offline fallback"""
        # Try Google Cloud Translate first
        if self.translate_client:
            try:
                result = self.translate_client.detect_language(text)
                return result['language'], result['confidence']
            except Exception as e:
                logger.warning(f"Google Translate detection failed: {e}")
        
        # Offline fallback: simple heuristic based on script/characters
        text_lower = text.lower()
        
        # Check for Devanagari script (Hindi and other Indian languages)
        if any('\u0900' <= char <= '\u097f' for char in text):
            return 'hi', 0.9
        
        # Check for Bengali script
        if any('\u0980' <= char <= '\u09ff' for char in text):
            return 'bn', 0.9
        
        # Check for Tamil script
        if any('\u0b80' <= char <= '\u0bff' for char in text):
            return 'ta', 0.9
        
        # Check for Telugu script
        if any('\u0c00' <= char <= '\u0c7f' for char in text):
            return 'te', 0.9
        
        # Check for Kannada script
        if any('\u0c80' <= char <= '\u0cff' for char in text):
            return 'kn', 0.9
        
        # Check for Malayalam script
        if any('\u0d00' <= char <= '\u0d7f' for char in text):
            return 'ml', 0.9
        
        # Check for Gujarati script
        if any('\u0a80' <= char <= '\u0aff' for char in text):
            return 'gu', 0.9
        
        # Check for Punjabi script (Gurmukhi)
        if any('\u0a00' <= char <= '\u0a7f' for char in text):
            return 'pa', 0.9
        
        # Check for Marathi (uses Devanagari, but common words)
        marathi_words = ['मराठी', 'महाराष्ट्र', 'पुणे', 'मुंबई']
        if any(word in text for word in marathi_words):
            return 'mr', 0.8
        
        # Default to English for Latin script
        return 'en', 0.7
            
    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str = None
    ) -> Optional[str]:
        """Translate text to target language"""
        try:
            if target_language == 'auto' or not target_language:
                return text
                
            if not source_language:
                source_language, _ = await self.detect_language(text)
                
            if source_language == target_language:
                return text
                
            result = self.translate_client.translate(
                text,
                target_language=target_language,
                source_language=source_language
            )
            
            return result['translatedText']
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text
            
    def get_language_info(self, lang_code: str) -> Dict:
        """Get language information including flag and names"""
        base_lang = lang_code.split('-')[0]
        if base_lang in self.SUPPORTED_LANGUAGES:
            info = self.SUPPORTED_LANGUAGES[base_lang].copy()
            if '-' in lang_code and 'variants' in info:
                if lang_code in info['variants']:
                    info['variant'] = info['variants'][lang_code]
            return info
        return self.SUPPORTED_LANGUAGES['auto']
        
    def get_voice_language(self, lang_code: str) -> str:
        """Get appropriate voice language code"""
        base_lang = lang_code.split('-')[0]
        if base_lang in self.SUPPORTED_LANGUAGES:
            lang_info = self.SUPPORTED_LANGUAGES[base_lang]
            if 'variants' in lang_info:
                # Return first variant as default voice language
                return next(iter(lang_info['variants'].keys()))
        return 'en-IN'  # Default to Indian English

    async def format_language_button(self, lang_code: str) -> str:
        """Format language button text with flag and names"""
        info = self.get_language_info(lang_code)
        return f"{info['flag']} {info['native_name']} ({info['name']})"
        
    async def text_to_speech(
        self,
        text: str,
        target_lang: str = 'en-IN',
        voice_gender: str = 'FEMALE'
    ) -> Optional[bytes]:
        """Convert text to speech using appropriate voice model
        
        Args:
            text: Text to convert to speech
            target_lang: Target language code (e.g. 'hi-IN', 'bn-IN')
            voice_gender: Desired voice gender ('FEMALE' or 'MALE')
            
        Returns:
            bytes: Audio file content or None if error
        """
        try:
            from google.cloud import texttospeech
            
            # Configure voice
            gender_enum = texttospeech.SsmlVoiceGender.FEMALE
            if voice_gender.upper() == 'MALE':
                gender_enum = texttospeech.SsmlVoiceGender.MALE
            
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=target_lang,
                ssml_gender=gender_enum
            )
            
            # Configure audio
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.9  # Slightly slower for better clarity
            )
            
            # Generate speech
            response = self.tts_client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=voice_params,
                audio_config=audio_config
            )
            
            return response.audio_content
            
        except Exception as e:
            logger.error(f"Text-to-speech error: {e}")
            return None
            
    async def speech_to_text(
        self,
        audio_content: bytes,
        language_code: str = 'en-IN'
    ) -> str:
        """Convert speech to text
        
        Args:
            audio_content: Audio file content
            language_code: Language code for speech recognition
            
        Returns:
            str: Transcribed text or empty string if error
        """
        try:
            from google.cloud import speech
            
            audio = speech.RecognitionAudio(content=audio_content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                sample_rate_hertz=16000,
                language_code=language_code,
                enable_automatic_punctuation=True
            )
            
            response = self.speech_client.recognize(config=config, audio=audio)
            
            if response.results:
                return response.results[0].alternatives[0].transcript
            return ""
            
        except Exception as e:
            logger.error(f"Speech-to-text error: {e}")
            return ""

# Create global instance
language_manager = LanguageManager()