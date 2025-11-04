import logging
import asyncio
from typing import Optional
import io
import os

logger = logging.getLogger(__name__)

class AudioHandler:
    def __init__(self):
        """Initialize Text-to-Speech clients with fallbacks"""
        self.tts_clients = {}
        self._init_tts_clients()

        # Define supported languages with their best voices
        self.language_voices = {
            'en': {  # English variants
                'en-IN': ['en-IN-Neural2-A', 'en-IN-Neural2-B', 'en-IN-Neural2-C'],  # Indian English
                'en-US': ['en-US-Neural2-H', 'en-US-Neural2-C'],  # American English
                'en-GB': ['en-GB-Neural2-A', 'en-GB-Neural2-B'],  # British English
            },
            'hi': {  # Hindi
                'hi-IN': ['hi-IN-Neural2-A', 'hi-IN-Neural2-B', 'hi-IN-Neural2-C'],
            },
            'bn': {  # Bengali
                'bn-IN': ['bn-IN-Neural2-A', 'bn-IN-Neural2-B'],
            },
            'ta': {  # Tamil
                'ta-IN': ['ta-IN-Neural2-A', 'ta-IN-Neural2-B'],
            },
            'te': {  # Telugu
                'te-IN': ['te-IN-Neural2-A', 'te-IN-Neural2-B'],
            },
            'kn': {  # Kannada
                'kn-IN': ['kn-IN-Neural2-A', 'kn-IN-Neural2-B'],
            },
            'ml': {  # Malayalam
                'ml-IN': ['ml-IN-Neural2-A', 'ml-IN-Neural2-B'],
            },
            'gu': {  # Gujarati
                'gu-IN': ['gu-IN-Neural2-A', 'gu-IN-Neural2-B'],
            },
            'mr': {  # Marathi
                'mr-IN': ['mr-IN-Neural2-A', 'mr-IN-Neural2-B'],
            },
            'pa': {  # Punjabi
                'pa-IN': ['pa-IN-Neural2-A', 'pa-IN-Neural2-B'],
            },
            # Add more languages as needed
        }

    def _init_tts_clients(self):
        """Initialize TTS clients with fallbacks"""
        # Try Google Cloud TTS first
        try:
            from google.cloud import texttospeech
            self.tts_clients['google_cloud'] = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud TTS client initialized")
        except Exception as e:
            logger.warning(f"Google Cloud TTS not available: {e}")
            self.tts_clients['google_cloud'] = None

        # Try gTTS (Google Translate TTS - no API key needed)
        try:
            from gtts import gTTS
            self.tts_clients['gtts'] = gTTS
            logger.info("gTTS client initialized")
        except Exception as e:
            logger.warning(f"gTTS not available: {e}")
            self.tts_clients['gtts'] = None

        # Try pyttsx3 (offline TTS)
        try:
            import pyttsx3
            self.tts_clients['pyttsx3'] = pyttsx3.init()
            logger.info("pyttsx3 client initialized")
        except Exception as e:
            logger.warning(f"pyttsx3 not available: {e}")
            self.tts_clients['pyttsx3'] = None

        # Check if any TTS client is available
        if not any(client for client in self.tts_clients.values()):
            logger.error("No TTS clients available! Audio functionality will not work.")
        else:
            logger.info("TTS clients initialized successfully")
        
    async def detect_language(self, text: str) -> tuple[str, str]:
        """Detect language of the text with offline fallback"""
        try:
            # Try Google Cloud Translate first
            from google.cloud import translate_v2 as translate
            translate_client = translate.Client()
            result = translate_client.detect_language(text)

            # Get the language code
            detected_lang = result['language']
            confidence = result['confidence']

            # Find the best matching voice configuration
            for lang_group, variants in self.language_voices.items():
                if detected_lang.startswith(lang_group):
                    # If we have a specific regional variant, use it
                    for variant in variants.keys():
                        if variant.startswith(detected_lang):
                            return variant, variants[variant][0]

                    # If no exact match, use the first available variant
                    first_variant = list(variants.keys())[0]
                    return first_variant, variants[first_variant][0]

            # Default to Indian English if language not supported
            return 'en-IN', 'en-IN-Neural2-A'

        except Exception as e:
            logger.warning(f"Google Translate language detection failed: {e}")
            # Offline fallback: simple heuristic based on script/characters
            text_lower = text.lower()

            # Check for Devanagari script (Hindi and other Indian languages)
            if any('\u0900' <= char <= '\u097f' for char in text):
                return 'hi-IN', 'hi-IN-Neural2-A'

            # Check for Bengali script
            if any('\u0980' <= char <= '\u09ff' for char in text):
                return 'bn-IN', 'bn-IN-Neural2-A'

            # Check for Tamil script
            if any('\u0b80' <= char <= '\u0bff' for char in text):
                return 'ta-IN', 'ta-IN-Neural2-A'

            # Check for Telugu script
            if any('\u0c00' <= char <= '\u0c7f' for char in text):
                return 'te-IN', 'te-IN-Neural2-A'

            # Check for Kannada script
            if any('\u0c80' <= char <= '\u0cff' for char in text):
                return 'kn-IN', 'kn-IN-Neural2-A'

            # Check for Malayalam script
            if any('\u0d00' <= char <= '\u0d7f' for char in text):
                return 'ml-IN', 'ml-IN-Neural2-A'

            # Check for Gujarati script
            if any('\u0a80' <= char <= '\u0aff' for char in text):
                return 'gu-IN', 'gu-IN-Neural2-A'

            # Check for Punjabi script (Gurmukhi)
            if any('\u0a00' <= char <= '\u0a7f' for char in text):
                return 'pa-IN', 'pa-IN-Neural2-A'

            # Check for Marathi (uses Devanagari, but common words)
            marathi_words = ['मराठी', 'महाराष्ट्र', 'पुणे', 'मुंबई']
            if any(word in text for word in marathi_words):
                return 'mr-IN', 'mr-IN-Neural2-A'

            # Default to English for Latin script
            return 'en-IN', 'en-IN-Neural2-A'
        
    async def text_to_speech(self, text: str, target_lang: str = None) -> Optional[bytes]:
        """Convert text to speech with offline-first approach"""
        if not text.strip():
            logger.warning("Empty text provided for TTS")
            return None

        logger.info(f"Starting TTS for text: {text[:50]}... (target_lang: {target_lang})")

        # Try gTTS first (Google Translate TTS - no API key needed)
        if self.tts_clients['gtts']:
            try:
                logger.info("Attempting gTTS...")
                result = await self._gtts_tts(text, target_lang)
                if result:
                    logger.info("gTTS succeeded")
                    return result
                logger.warning("gTTS returned None")
            except Exception as e:
                logger.warning(f"gTTS failed: {e}", exc_info=True)

        # Fallback to pyttsx3 (offline TTS)
        if self.tts_clients['pyttsx3']:
            try:
                logger.info("Attempting pyttsx3...")
                result = await self._pyttsx3_tts(text, target_lang)
                if result:
                    logger.info("pyttsx3 succeeded")
                    return result
                logger.warning("pyttsx3 returned None")
            except Exception as e:
                logger.warning(f"pyttsx3 failed: {e}", exc_info=True)

        # Final fallback to Google Cloud TTS (requires API key)
        if self.tts_clients['google_cloud']:
            try:
                logger.info("Attempting Google Cloud TTS...")
                result = await self._google_cloud_tts(text, target_lang)
                if result:
                    logger.info("Google Cloud TTS succeeded")
                    return result
                logger.warning("Google Cloud TTS returned None")
            except Exception as e:
                logger.warning(f"Google Cloud TTS failed: {e}", exc_info=True)

        logger.error("All TTS clients failed or returned None")
        return None

    async def _google_cloud_tts(self, text: str, target_lang: str = None) -> Optional[bytes]:
        """Google Cloud Text-to-Speech implementation"""
        from google.cloud import texttospeech

        # Detect language if not specified
        if not target_lang:
            lang_code, voice_name = await self.detect_language(text)
        else:
            lang_code, voice_name = self._get_voice_config(target_lang)

        # Configure the synthesis input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Build the voice request with natural settings
        voice = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        # Enhanced audio configuration for natural sound
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,  # Natural speaking rate
            pitch=0.0,  # Neutral pitch
            volume_gain_db=1.0,  # Slightly increased volume
            effects_profile_id=['telephony-class-application'],  # Optimize for voice
            sample_rate_hertz=24000  # High quality audio
        )

        # Perform the text-to-speech request
        response = await asyncio.to_thread(
            self.tts_clients['google_cloud'].synthesize_speech,
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        return response.audio_content

    async def _gtts_tts(self, text: str, target_lang: str = None) -> Optional[bytes]:
        """gTTS (Google Translate TTS) implementation - no API key needed"""
        try:
            # Detect language if not specified
            if not target_lang:
                lang_code, _ = await self.detect_language(text)
            else:
                lang_code, _ = self._get_voice_config(target_lang)

            # gTTS uses 2-letter language codes
            lang_code_2 = lang_code[:2] if len(lang_code) >= 2 else 'en'
            
            logger.info(f"gTTS using language code: {lang_code_2}")

            # Create gTTS instance
            tts = self.tts_clients['gtts'](text=text, lang=lang_code_2, slow=False)

            # Generate audio in memory
            audio_buffer = io.BytesIO()
            await asyncio.to_thread(tts.write_to_fp, audio_buffer)
            audio_buffer.seek(0)
            
            audio_data = audio_buffer.getvalue()
            
            if not audio_data:
                logger.error("gTTS generated empty audio data")
                return None
                
            logger.info(f"gTTS generated {len(audio_data)} bytes of audio")
            return audio_data
            
        except Exception as e:
            logger.error(f"gTTS error: {e}", exc_info=True)
            raise

    async def _pyttsx3_tts(self, text: str, target_lang: str = None) -> Optional[bytes]:
        """pyttsx3 (offline TTS) implementation"""
        import tempfile
        import subprocess

        # Detect language if not specified
        if not target_lang:
            lang_code, _ = await self.detect_language(text)
        else:
            lang_code, _ = self._get_voice_config(target_lang)

        # Create temporary file for audio output
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            # Configure pyttsx3
            engine = self.tts_clients['pyttsx3']

            # Set voice based on language (limited support in pyttsx3)
            voices = engine.getProperty('voices')
            if voices:
                # Try to find a voice that matches the language
                for voice in voices:
                    if lang_code[:2].lower() in voice.languages[0].lower() if voice.languages else False:
                        engine.setProperty('voice', voice.id)
                        break

            # Set speech rate and volume
            engine.setProperty('rate', 180)  # Slightly slower for clarity
            engine.setProperty('volume', 0.8)

            # Save to file
            engine.save_to_file(text, temp_filename)
            engine.runAndWait()

            # Read the generated audio file
            with open(temp_filename, 'rb') as f:
                audio_data = f.read()

            # Convert WAV to MP3 using ffmpeg if available
            try:
                mp3_filename = temp_filename.replace('.wav', '.mp3')
                result = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-i', temp_filename, '-acodec', 'libmp3lame', '-q:a', '2', mp3_filename,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await result.wait()

                if result.returncode == 0:
                    with open(mp3_filename, 'rb') as f:
                        audio_data = f.read()
                    os.unlink(mp3_filename)
            except (FileNotFoundError, subprocess.SubprocessError, OSError) as e:
                # If ffmpeg conversion fails, keep WAV data
                logger.warning(f"FFmpeg conversion failed, using WAV format: {e}")
                pass

            return audio_data

        finally:
            # Clean up temporary file
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    def _get_voice_config(self, target_lang: str) -> tuple[str, str]:
        """Get voice configuration for a target language"""
        lang_group = target_lang[:2]
        if lang_group in self.language_voices:
            variants = self.language_voices[lang_group]
            # Find exact match or use first variant
            for variant, voices in variants.items():
                if variant.startswith(target_lang):
                    return variant, voices[0]
            # Use first available variant
            first_variant = list(variants.keys())[0]
            return first_variant, variants[first_variant][0]
        else:
            # Default to Indian English
            return 'en-IN', 'en-IN-Neural2-A'

    async def split_long_text(self, text: str, max_chars: int = 4500) -> list[str]:
        """Split long text into chunks for TTS processing"""
        chunks = []
        current_chunk = ""
        sentences = text.split(". ")

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 <= max_chars:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

# Create a global instance
audio_handler = AudioHandler()