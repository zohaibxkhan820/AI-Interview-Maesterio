import os
import time
import json
import re
import tempfile
import threading
import logging
import queue
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import io
import wave
import docx2txt
import PyPDF2
import requests
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import speech_recognition as sr
import pyttsx3
from gtts import gTTS
import whisper
import sounddevice as sd

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ai_interviewer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ai_interviewer')

# Check if Together AI is available, otherwise use a mock
try:
    from together import Together
    TOGETHER_AVAILABLE = True
except ImportError:
    TOGETHER_AVAILABLE = False
    logger.warning("Together AI not available, using mock implementation")

# Check if speech recognition is available, otherwise use a mock
try:
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    logger.warning("Speech recognition not available, using mock implementation")

# Check if text-to-speech is available, otherwise use a mock
try:
    from playsound import playsound
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("Text-to-speech not available, using mock implementation")

# Check if whisper is available for advanced speech recognition
try:
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Whisper not available, using standard speech recognition")

class VoiceInteractionManager:
    """Manages voice interactions with improved TTS and STT capabilities."""
    
    def __init__(self, use_gtts=True, use_whisper=True):
        """Initialize the voice interaction manager.
        
        Args:
            use_gtts: Whether to use Google TTS (True) or pyttsx3 (False)
            use_whisper: Whether to use OpenAI Whisper for STT
        """
        self.use_gtts = use_gtts and TTS_AVAILABLE
        self.use_whisper = use_whisper and WHISPER_AVAILABLE
        
        # TTS components
        self.temp_audio_file = os.path.join(tempfile.gettempdir(), "temp_speech.mp3")
        self.tts_complete_event = threading.Event()
        self.tts_in_progress = False
        
        # Initialize TTS engine
        if TTS_AVAILABLE and not self.use_gtts:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 160)  # Speaking rate
                voices = self.engine.getProperty('voices')
                # Try to find a female voice for the interviewer
                female_voice = next((voice for voice in voices if 'female' in voice.name.lower()), None)
                if female_voice:
                    self.engine.setProperty('voice', female_voice.id)
                
                # Set up callback for TTS completion
                self.engine.connect('finished-utterance', self._on_tts_complete)
                logger.info("pyttsx3 TTS engine initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing pyttsx3: {e}")
                self.use_gtts = True  # Fallback to Google TTS
                self.engine = None
        else:
            self.engine = None
        
        # STT components
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            # Adjust recognition parameters for better performance
            self.recognizer.energy_threshold = 300  # Lower energy threshold for detecting speech
            self.recognizer.dynamic_energy_threshold = True  # Dynamically adjust for ambient noise
            self.recognizer.pause_threshold = 2.0  # Longer pause threshold to detect end of speech
        else:
            self.recognizer = MockRecognizer()
        
        # Initialize Whisper model if available
        self.whisper_model = None
        if self.use_whisper:
            try:
                logger.info("Loading Whisper model...")
                self.whisper_model = whisper.load_model("base")
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Error loading Whisper model: {e}")
                self.use_whisper = False
        
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.audio_thread = None
    
    def _on_tts_complete(self, name, completed):
        """Callback for TTS completion."""
        if completed:
            self.tts_in_progress = False
            self.tts_complete_event.set()
    
    def speak(self, text: str, wait_for_completion: bool = True) -> bool:
        """Convert text to speech with enhanced voice quality.
        
        Args:
            text: The text to speak
            wait_for_completion: Whether to wait for speech to complete before returning
            
        Returns:
            True if successful, False otherwise
        """
        if not text:
            logger.warning("Empty text provided to speak method")
            return False
        
        logger.info(f"Speaking: {text}")
        
        if not TTS_AVAILABLE:
            logger.warning("TTS not available, skipping speech")
            return False
        
        self.tts_in_progress = True
        self.tts_complete_event.clear()
        success = False
        
        try:
            if self.use_gtts:
                # Use Google TTS for better quality
                chunks = self._split_text_into_chunks(text)
                
                for chunk in chunks:
                    tts = gTTS(text=chunk, lang='en', slow=False)
                    tts.save(self.temp_audio_file)
                    
                    # Play the audio
                    playsound(self.temp_audio_file)
                    
                    # Clean up the temp file
                    if os.path.exists(self.temp_audio_file):
                        os.remove(self.temp_audio_file)
                
                # Signal completion
                self.tts_in_progress = False
                self.tts_complete_event.set()
                success = True
            elif self.engine:
                # Use pyttsx3 as fallback (works offline)
                self.engine.say(text)
                self.engine.runAndWait()
                
                # Signal completion if callback didn't work
                if self.tts_in_progress:
                    self.tts_in_progress = False
                    self.tts_complete_event.set()
                
                success = True
            else:
                logger.error("No TTS engine available")
                self.tts_in_progress = False
                self.tts_complete_event.set()
                return False
            
            # Wait for TTS to complete if requested
            if wait_for_completion:
                logger.debug("Waiting for TTS to complete...")
                self.tts_complete_event.wait(timeout=30)  # 30 second timeout
                logger.debug("TTS completed")
                
            return success
        except Exception as e:
            logger.error(f"Error in TTS: {e}")
            # Ensure we don't block in case of error
            self.tts_in_progress = False
            self.tts_complete_event.set()
            return False
    
    def listen(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> Optional[str]:
        """Listen for speech and convert to text with enhanced accuracy.
        
        Args:
            timeout: Maximum time to wait for speech to start
            phrase_time_limit: Maximum time to record speech
            
        Returns:
            The transcribed text or None if no speech was detected
        """
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.warning("Speech recognition not available, returning mock response")
            return "Mock response: This is a simulated answer from the candidate."
        
        timeout = timeout or 10.0  # Default 10 seconds timeout
        phrase_time_limit = phrase_time_limit or 60.0  # Default 60 seconds phrase time limit
        
        logger.info("Listening for response...")
        
        try:
            with sr.Microphone() as source:
                # Adjust for ambient noise
                logger.debug("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Listening...")
                
                # Listen for audio
                try:
                    audio = self.recognizer.listen(
                        source, 
                        timeout=timeout, 
                        phrase_time_limit=phrase_time_limit
                    )
                    
                    logger.debug("Audio captured, transcribing...")
                    
                    # Try to use Whisper for better accuracy if available
                    if self.use_whisper and self.whisper_model:
                        # Convert audio to format Whisper can use
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                            temp_audio_path = temp_audio.name
                            with wave.open(temp_audio_path, 'wb') as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(16000)
                                wf.writeframes(audio.get_raw_data())
                        
                        try:
                            # Use Whisper to transcribe
                            result = self.whisper_model.transcribe(temp_audio_path)
                            text = result["text"].strip()
                            
                            logger.info(f"Whisper transcription: {text}")
                            
                            # Clean up temp file
                            if os.path.exists(temp_audio_path):
                                os.remove(temp_audio_path)
                                
                            return text
                        except Exception as e:
                            logger.error(f"Error using Whisper: {e}")
                            # Clean up temp file
                            if os.path.exists(temp_audio_path):
                                os.remove(temp_audio_path)
                            
                            # Fall back to Google Speech Recognition
                            logger.info("Falling back to Google Speech Recognition")
                    
                    # Use Google Speech Recognition
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    logger.info(f"Google Speech Recognition: {text}")
                    return text
                    
                except sr.WaitTimeoutError:
                    logger.warning("Timeout waiting for speech")
                    return None
                except sr.UnknownValueError:
                    logger.warning("Could not understand audio")
                    return None
                except Exception as e:
                    logger.error(f"Error in speech recognition: {e}")
                    return None
                
        except Exception as e:
            logger.error(f"Error setting up microphone: {e}")
            return None
    
    def listen_with_retry(self, max_retries: int = 3, timeout: Optional[float] = None, 
                          phrase_time_limit: Optional[float] = None) -> str:
        """Listen for speech with retry logic for better reliability.
        
        Args:
            max_retries: Maximum number of retry attempts
            timeout: Maximum time to wait for speech to start
            phrase_time_limit: Maximum time to record speech
            
        Returns:
            The transcribed text or a message indicating no response was detected
        """
        for attempt in range(max_retries):
            logger.info(f"Listen attempt {attempt + 1}/{max_retries}")
            
            text = self.listen(timeout, phrase_time_limit)
            
            if text:
                return text
            elif attempt < max_retries - 1:
                # Notify the user we didn't hear them
                self.speak("I didn't catch that. Could you please repeat your answer?", wait_for_completion=True)
                time.sleep(1)  # Short pause before listening again
        
        # If we get here, all retries failed
        message = "No response detected after multiple attempts."
        self.speak("I'm having trouble hearing you. Let's move on to the next question.", wait_for_completion=True)
        return message
    
    def _split_text_into_chunks(self, text: str, max_length: int = 500) -> List[str]:
        """Split text into smaller chunks for TTS processing.
        
        Args:
            text: The text to split
            max_length: Maximum length of each chunk
            
        Returns:
            List of text chunks
        """
        # First try to split by sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < max_length:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def process_voice_data(self, voice_data):
        """Process raw voice data and convert to text."""
        try:
            if self.use_whisper:
                # Convert voice data to numpy array
                audio_data = np.frombuffer(voice_data, dtype=np.int16)
                # Convert to float32 and normalize
                audio_data = audio_data.astype(np.float32) / 32768.0
                # Transcribe using Whisper
                result = self.whisper_model.transcribe(audio_data)
                return result["text"]
            else:
                # Use Google Speech Recognition
                audio = sr.AudioData(voice_data, 16000, 2)
                text = self.recognizer.recognize_google(audio)
                return text
        except Exception as e:
            print(f"Error processing voice data: {e}")
            return None

    def start_listening(self):
        """Start listening for voice input."""
        self.is_listening = True
        self.audio_thread = threading.Thread(target=self._audio_callback)
        self.audio_thread.start()

    def stop_listening(self):
        """Stop listening for voice input."""
        self.is_listening = False
        if self.audio_thread:
            self.audio_thread.join()

    def _audio_callback(self):
        """Callback function for audio input."""
        def callback(indata, frames, time, status):
            if status:
                print(status)
            if self.is_listening:
                self.audio_queue.put(indata.copy())

        with sd.InputStream(callback=callback, channels=1, samplerate=16000):
            while self.is_listening:
                time.sleep(0.1)

class AIInterviewer:
    def __init__(self):
        """Initialize the AI Interviewer with enhanced voice capabilities and API integration."""
        # API keys - in production, get these from Django settings
        self.together_api_key = getattr(settings, "TOGETHER_API_KEY", "tgp_v1_4Sr1k1JaX_m5U1agvWjOLjulLYtOeH17eUJ5Xls6i6I")
        self.question_api_url = getattr(settings, "QUESTION_API_URL", "https://api.example.com/generate-questions")
        self.question_api_key = getattr(settings, "QUESTION_API_KEY", "your-api-key")
        
        # Initialize Together AI client
        if TOGETHER_AVAILABLE:
            self.client = Together(api_key=self.together_api_key)
        else:
            self.client = MockTogetherClient()
            
        self.model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        self.job_description = ""
        self.cv = ""
        self.interview_history = []
        self.report = ""
        self.questions = []
        self.current_question_index = 0
        
        # Initialize voice interaction manager
        self.voice_manager = VoiceInteractionManager(
            use_gtts=getattr(settings, "USE_GTTS", True),
            use_whisper=getattr(settings, "USE_WHISPER", True)
        )
        
        # Interview state
        self.is_interview_active = False
        self.interview_paused = False
        self.stop_requested = False
        
        # Thread management
        self.interview_thread = None
        self.thread_lock = threading.RLock()
        
        # Callbacks for frontend integration
        self.on_question_callback = None
        self.on_answer_callback = None
        self.on_complete_callback = None
        self.on_error_callback = None
    
    def load_file_content(self, file_path: str) -> str:
        """Load content from various file formats (.txt, .pdf, .doc, .docx)."""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_extension == '.txt':
                # Load text file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    return file.read()
            
            elif file_extension == '.pdf':
                # Load PDF file
                text = ""
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page_num in range(len(pdf_reader.pages)):
                        text += pdf_reader.pages[page_num].extract_text() + "\n"
                return text
            
            elif file_extension in ['.doc', '.docx']:
                # Load Word document
                return docx2txt.process(file_path)
            
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
                
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")
            raise
    
    def load_job_description_from_django_file(self, file_object):
        """Load job description from a Django file object."""
        try:
            # Read the content directly from the file object
            content = ""
            file_extension = os.path.splitext(file_object.name)[1].lower()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                for chunk in file_object.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name
        
            # Now process the temp file based on its extension
            try:
                content = self.load_file_content(temp_path)
                # Clean up
                os.unlink(temp_path)
                
                self.job_description = content
                logger.info("✓ Job description loaded successfully")
                return True
            except Exception as e:
                # Clean up in case of error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e
            
        except Exception as e:
            logger.error(f"Error loading job description: {e}")
            return False
    
    def load_cv_from_django_file(self, file_object):
        """Load CV from a Django file object."""
        try:
            # Read the content directly from the file object
            content = ""
            file_extension = os.path.splitext(file_object.name)[1].lower()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                for chunk in file_object.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name
        
            # Now process the temp file based on its extension
            try:
                content = self.load_file_content(temp_path)
                # Clean up
                os.unlink(temp_path)
                
                self.cv = content
                logger.info("✓ CV loaded successfully")
                return True
            except Exception as e:
                # Clean up in case of error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e
            
        except Exception as e:
            logger.error(f"Error loading CV: {e}")
            return False
    
    def generate_questions_via_api(self) -> List[Dict]:
        """Generate interview questions using the provided API."""
        logger.info("Generating interview questions via API...")
        
        try:
            # Prepare the API request payload
            payload = {
                "job_description": self.job_description,
                "cv": self.cv,
                "num_technical_questions": 15,
                "num_non_technical_questions": 5
            }
            
            headers = {
                "Authorization": f"Bearer {self.question_api_key}",
                "Content-Type": "application/json"
            }
            
            # Make the API request
            response = requests.post(
                self.question_api_url,
                json=payload,
                headers=headers,
                timeout=30  # 30 second timeout
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                questions = response.json().get("questions", [])
                logger.info(f" Generated {len(questions)} interview questions via API")
                return questions
            else:
                logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                # Fall back to the AI-based generation
                return self.generate_questions()
                
        except requests.RequestException as e:
            logger.error(f"API request error: {e}")
            # Fall back to the AI-based generation
            return self.generate_questions()
        except Exception as e:
            logger.error(f"Unexpected error in API question generation: {e}")
            # Fall back to the AI-based generation
            return self.generate_questions()
    
    def generate_questions(self) -> List[Dict]:
        """Generate interview questions based on the JD and CV using AI."""
        logger.info("Generating interview questions using AI...")
        
        prompt = f"""
        You are an expert technical interviewer for a company. You need to create 20 interview questions based on the job description and candidate's CV provided below.
        
        # Job Description:
        {self.job_description}
        
        # Candidate's CV:
        {self.cv}
        
        # Instructions:
        - Create exactly 20 questions in total
        - 5 should be non-technical questions:
          - Question #1 MUST ask the candidate to introduce themselves
          - The other 4 should assess soft skills, culture fit, and work experience
        - 15 should be technical questions that test specific skills mentioned in the job description
        - The questions should be detailed and specific, not generic
        - Include cross-questioning elements that dig deeper into the candidate's knowledge
        - The questions should cover different aspects of the job description
        - Format the output as a JSON array of question objects
        
        Each question should have the following structure:
        {{
            "id": 1,
            "type": "technical", // or "non-technical"
            "question": "The detailed question text",
            "context": "Why this question is relevant based on the JD and CV",
            "follow_up_questions": [
                "Follow-up question 1",
                "Follow-up question 2"
            ]
        }}
        
        Return only the JSON array, no other text.
        """
        
        if TOGETHER_AVAILABLE:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert technical interviewer who creates challenging but fair interview questions. Output only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=4000
                )
                
                response_text = response.choices[0].message.content
            except Exception as e:
                logger.error(f"Error calling Together AI API: {e}")
                response_text = self._get_mock_questions_response()
        else:
            # Use mock response for testing
            response_text = self._get_mock_questions_response()
        
        # Extract JSON from the response
        json_match = re.search(r'\`\`\`json\s*([\s\S]*?)\s*\`\`\`|(\[[\s\S]*\])', response_text)
        if json_match:
            json_str = json_match.group(1) or json_match.group(2)
        else:
            json_str = response_text
            
        # Clean up any remaining markdown or text
        json_str = json_str.strip()
        if json_str.startswith('\`\`\`') and json_str.endswith('\`\`\`'):
            json_str = json_str[3:-3].strip()
            
        try:
            questions = json.loads(json_str)
            logger.info(f" Generated {len(questions)} interview questions")
            return questions
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing questions JSON: {e}")
            logger.debug(f"Raw response: {response_text}")
            # Return mock questions as fallback
            return self._get_mock_questions()
    
    def _get_mock_questions_response(self):
        """Return a mock response for testing."""
        return """\`\`\`json
[
  {
    "id": 1,
    "type": "non-technical",
    "question": "Could you please introduce yourself and walk me through your professional journey so far?",
    "context": "Standard opening question to understand the candidate's background and communication style",
    "follow_up_questions": [
      "What aspects of your background do you think are most relevant to this position?",
      "How has your previous experience prepared you for this role?"
    ]
  },
  {
    "id": 2,
    "type": "non-technical",
    "question": "What interests you most about this position and our company?",
    "context": "Assessing candidate's motivation and research about the company",
    "follow_up_questions": [
      "What specific aspects of our company culture appeal to you?",
      "How do you see yourself contributing to our team?"
    ]
  },
  {
    "id": 3,
    "type": "non-technical",
    "question": "Describe a challenging project you worked on and how you overcame obstacles to complete it successfully.",
    "context": "Evaluating problem-solving abilities and resilience",
    "follow_up_questions": [
      "What specific strategies did you use to overcome the challenges?",
      "What did you learn from this experience that you could apply to this role?"
    ]
  },
  {
    "id": 4,
    "type": "non-technical",
    "question": "How do you approach collaborating with team members who have different working styles or perspectives?",
    "context": "Assessing teamwork and interpersonal skills",
    "follow_up_questions": [
      "Can you provide a specific example of when you had to adapt your communication style?",
      "How do you handle disagreements within a team?"
    ]
  },
  {
    "id": 5,
    "type": "non-technical",
    "question": "Where do you see yourself professionally in the next 3-5 years?",
    "context": "Understanding career goals and alignment with company growth",
    "follow_up_questions": [
      "What skills are you currently developing to help you reach these goals?",
      "How does this position fit into your long-term career plan?"
    ]
  },
  {
    "id": 6,
    "type": "technical",
    "question": "Can you explain the difference between REST and GraphQL APIs, and when you would choose one over the other?",
    "context": "Testing knowledge of API design principles mentioned in the job description",
    "follow_up_questions": [
      "What are some challenges you've faced when implementing RESTful APIs?",
      "How would you handle versioning in a REST API?"
    ]
  },
  {
    "id": 7,
    "type": "technical",
    "question": "Explain how you would design a database schema for a user management system with roles and permissions.",
    "context": "Evaluating database design skills mentioned in the CV",
    "follow_up_questions": [
      "How would you handle role inheritance in this schema?",
      "What indexes would you create to optimize performance?"
    ]
  },
  {
    "id": 8,
    "type": "technical",
    "question": "Walk me through your approach to implementing authentication and authorization in a web application.",
    "context": "Security is mentioned as important in the job description",
    "follow_up_questions": [
      "How would you handle JWT token refresh?",
      "What security vulnerabilities should you be aware of in authentication systems?"
    ]
  },
  {
    "id": 9,
    "type": "technical",
    "question": "Describe your experience with containerization and orchestration tools like Docker and Kubernetes.",
    "context": "DevOps skills mentioned in the job description",
    "follow_up_questions": [
      "How would you optimize a Docker image for production?",
      "Explain how you would set up a CI/CD pipeline for a containerized application."
    ]
  },
  {
    "id": 10,
    "type": "technical",
    "question": "How would you implement real-time features in a web application?",
    "context": "Real-time functionality mentioned in job description",
    "follow_up_questions": [
      "Compare WebSockets, Server-Sent Events, and long polling.",
      "How would you ensure scalability in a real-time application?"
    ]
  },
  {
    "id": 11,
    "type": "technical",
    "question": "Explain your approach to writing testable code and what testing strategies you typically employ.",
    "context": "Testing mentioned as important in the job description",
    "follow_up_questions": [
      "What's the difference between unit, integration, and end-to-end tests?",
      "How do you determine appropriate test coverage for a project?"
    ]
  },
  {
    "id": 12,
    "type": "technical",
    "question": "Describe how you would optimize the performance of a web application that's experiencing slow load times.",
    "context": "Performance optimization skills mentioned in the job description",
    "follow_up_questions": [
      "What tools would you use to identify performance bottlenecks?",
      "How would you implement lazy loading for a large application?"
    ]
  },
  {
    "id": 13,
    "type": "technical",
    "question": "How do you approach state management in frontend applications?",
    "context": "Frontend development skills mentioned in the CV",
    "follow_up_questions": [
      "Compare different state management libraries you've worked with.",
      "How would you handle shared state between multiple components?"
    ]
  },
  {
    "id": 14,
    "type": "technical",
    "question": "Explain how you would implement a microservices architecture and the challenges involved.",
    "context": "Architecture skills mentioned in the job description",
    "follow_up_questions": [
      "How would you handle inter-service communication?",
      "What strategies would you use for data consistency across services?"
    ]
  },
  {
    "id": 15,
    "type": "technical",
    "question": "Describe your experience with cloud platforms and serverless architectures.",
    "context": "Cloud experience mentioned in the job description",
    "follow_up_questions": [
      "What are the advantages and disadvantages of serverless computing?",
      "How would you migrate a monolithic application to a cloud-native architecture?"
    ]
  },
  {
    "id": 16,
    "type": "technical",
    "question": "How would you implement a secure authentication system that includes multi-factor authentication?",
    "context": "Security focus mentioned in the job description",
    "follow_up_questions": [
      "What are the best practices for storing user credentials?",
      "How would you handle session management in a distributed system?"
    ]
  },
  {
    "id": 17,
    "type": "technical",
    "question": "Explain your approach to handling errors and exceptions in a production application.",
    "context": "Reliability mentioned as important in the job description",
    "follow_up_questions": [
      "How would you implement a centralized logging system?",
      "What strategies would you use for graceful degradation when services fail?"
    ]
  },
  {
    "id": 18,
    "type": "technical",
    "question": "Describe your experience with implementing and optimizing database queries.",
    "context": "Database optimization mentioned in the job description",
    "follow_up_questions": [
      "How would you identify and fix a slow-performing SQL query?",
      "What are the trade-offs between different types of database indexes?"
    ]
  },
  {
    "id": 19,
    "type": "technical",
    "question": "How would you approach building an API that needs to handle high traffic and maintain low latency?",
    "context": "Scalability mentioned in the job description",
    "follow_up_questions": [
      "What caching strategies would you implement?",
      "How would you handle rate limiting and throttling?"
    ]
  },
  {
    "id": 20,
    "type": "technical",
    "question": "Explain your experience with implementing accessibility features in web applications.",
    "context": "Accessibility mentioned in the job description",
    "follow_up_questions": [
      "How do you test for accessibility compliance?",
      "What are the most common accessibility issues you've encountered and how did you resolve them?"
    ]
  }
]\`\`\`"""
    
    def _get_mock_questions(self):
        """Return mock questions as a fallback."""
        return [
            {
                "id": 1,
                "type": "non-technical",
                "question": "Could you please introduce yourself and walk me through your professional journey so far?",
                "context": "Standard opening question to understand the candidate's background and communication style",
                "follow_up_questions": [
                    "What aspects of your background do you think are most relevant to this position?",
                    "How has your previous experience prepared you for this role?"
                ]
            },
            {
                "id": 2,
                "type": "non-technical",
                "question": "What interests you most about this position and our company?",
                "context": "Assessing candidate's motivation and research about the company",
                "follow_up_questions": [
                    "What specific aspects of our company culture appeal to you?",
                    "How do you see yourself contributing to our team?"
                ]
            },
            {
                "id": 3,
                "type": "technical",
                "question": "Can you explain the difference between REST and GraphQL APIs, and when you would choose one over the other?",
                "context": "Testing knowledge of API design principles",
                "follow_up_questions": [
                    "What are some challenges you've faced when implementing RESTful APIs?",
                    "How would you handle versioning in a REST API?"
                ]
            },
            {
                "id": 4,
                "type": "technical",
                "question": "Explain how you would design a database schema for a user management system with roles and permissions.",
                "context": "Evaluating database design skills",
                "follow_up_questions": [
                    "How would you handle role inheritance in this schema?",
                    "What indexes would you create to optimize performance?"
                ]
            },
            {
                "id": 5,
                "type": "technical",
                "question": "Walk me through your approach to implementing authentication and authorization in a web application.",
                "context": "Security is important for web applications",
                "follow_up_questions": [
                    "How would you handle JWT token refresh?",
                    "What security vulnerabilities should you be aware of in authentication systems?"
                ]
            }
        ]
    
    def start_voice_interview(self) -> bool:
        """Start a voice-based interview session."""
        logger.info("Starting voice interview...")
        
        # Check if we have questions
        if not self.questions:
            try:
                # First try to get questions from the API
                self.questions = self.generate_questions_via_api()
                
                # If API fails or returns empty, fall back to AI generation
                if not self.questions:
                    self.questions = self.generate_questions()
            except Exception as e:
                logger.error(f"Error generating questions: {e}")
                return False
        
        # Reset interview state
        with self.thread_lock:
            self.is_interview_active = True
            self.interview_paused = False
            self.stop_requested = False
            self.current_question_index = 0
        
        # Welcome message
        welcome_message = "Welcome to your AI interview session. I'll be asking you a series of questions based on your CV and the job description. Please speak clearly when answering. Let's begin."
        self.voice_manager.speak(welcome_message)
        
        # Start the interview loop in a separate thread
        self.interview_thread = threading.Thread(
            target=self._voice_interview_loop,
            daemon=True
        )
        self.interview_thread.start()
        
        return True
    
    def _voice_interview_loop(self):
        """Run the voice interview loop in a background thread."""
        try:
            while self.is_interview_active and self.current_question_index < len(self.questions):
                # Check if interview is paused or stopped
                with self.thread_lock:
                    if self.stop_requested:
                        logger.info("Interview stopped")
                        break
                    
                    if self.interview_paused:
                        time.sleep(1)  # Check every second if interview is resumed
                        continue
                    
                    # Get the current question
                    current_question = self.questions[self.current_question_index]
                
                # Notify callback if set
                if self.on_question_callback:
                    try:
                        self.on_question_callback(current_question)
                    except Exception as e:
                        logger.error(f"Error in question callback: {e}")
                
                # Ask the question using TTS - wait for completion before listening
                question_text = current_question["question"]
                logger.info(f"Asking question {self.current_question_index + 1}: {question_text}")
                
                # Speak the question and wait for it to complete
                self.voice_manager.speak(question_text, wait_for_completion=True)
                
                # Small pause after speaking before listening
                time.sleep(1)
                
                # Listen for the answer with retry logic
                logger.info("Listening for answer...")
                answer = self.voice_manager.listen_with_retry(max_retries=3)
                
                # Check if interview was stopped during listening
                with self.thread_lock:
                    if self.stop_requested:
                        logger.info("Interview stopped during answer")
                        break
                
                logger.info(f"Answer received: {answer}")
                
                # Notify callback if set
                if self.on_answer_callback:
                    try:
                        self.on_answer_callback(current_question["id"], answer)
                    except Exception as e:
                        logger.error(f"Error in answer callback: {e}")
                
                # Store the answer in the interview history
                self.interview_history.append({
                    "question": current_question,
                    "answer": answer
                })
                
                # Move to the next question
                with self.thread_lock:
                    self.current_question_index += 1
                
                # Small pause between questions
                time.sleep(2)
            
            # Interview complete
            with self.thread_lock:
                if self.current_question_index >= len(self.questions) and not self.stop_requested:
                    completion_message = "Thank you for completing the interview. Your responses have been recorded."
                    self.voice_manager.speak(completion_message)
                    
                    # Notify callback if set
                    if self.on_complete_callback:
                        try:
                            self.on_complete_callback()
                        except Exception as e:
                            logger.error(f"Error in complete callback: {e}")
                
                self.is_interview_active = False
        
        except Exception as e:
            logger.error(f"Error in voice interview loop: {e}")
            self.is_interview_active = False
            
            # Notify callback if set
            if self.on_error_callback:
                try:
                    self.on_error_callback(str(e))
                except Exception as e:
                    logger.error(f"Error in error callback: {e}")
    
    def pause_interview(self):
        """Pause the ongoing interview."""
        with self.thread_lock:
            if self.is_interview_active and not self.interview_paused:
                self.interview_paused = True
                self.voice_manager.speak("Interview paused. Say 'resume' when you're ready to continue.")
                logger.info("Interview paused")
                return True
        return False
    
    def resume_interview(self):
        """Resume a paused interview."""
        with self.thread_lock:
            if self.is_interview_active and self.interview_paused:
                self.interview_paused = False
                self.voice_manager.speak("Interview resumed.")
                logger.info("Interview resumed")
                return True
        return False
    
    def stop_interview(self):
        """Stop the ongoing interview."""
        with self.thread_lock:
            if self.is_interview_active:
                self.stop_requested = True
                self.is_interview_active = False
                self.interview_paused = False
                logger.info("Interview stop requested")
                return True
        return False
    
    def get_next_question(self) -> Optional[Dict]:
        """Get the next question without using voice interaction."""
        with self.thread_lock:
            if not self.questions or self.current_question_index >= len(self.questions):
                return None
            
            question = self.questions[self.current_question_index]
            self.current_question_index += 1
            return question
    
    def submit_answer(self, question_id: int, answer: str) -> bool:
        """Submit an answer for a specific question."""
        # Find the question with the given ID
        question = next((q for q in self.questions if q.get("id") == question_id), None)
        
        if not question:
            logger.error(f"Question with ID {question_id} not found")
            return False
        
        # Store the answer in the interview history
        self.interview_history.append({
            "question": question,
            "answer": answer
        })
        
        return True
    
    def generate_report(self, interview_data, behavioral_summary=None) -> str:
        """Generate a detailed feedback report based on the interview with enhanced evaluation criteria, including behavioral analysis."""
        if not interview_data:
            logger.warning("No interview data to generate report from")
            return ""
        
        # Organize questions and answers by type for better analysis
        technical_qa_pairs = []
        non_technical_qa_pairs = []
        
        for item in interview_data:
            q_type = item["question_data"]["type"]
            question = item["question_data"]["question"]
            answer = item["answer"]
            
            qa_pair = {
                "id": item["question_data"]["id"],
                "question": question,
                "answer": answer
            }
            
            if q_type == "technical":
                technical_qa_pairs.append(qa_pair)
            else:
                non_technical_qa_pairs.append(qa_pair)
        
        interview_json = json.dumps(interview_data)
        
        # Add behavioral summary to the prompt if provided
        behavioral_section = f"\n\n# Posture and Sentiment Analysis (from video):\n{behavioral_summary}\n" if behavioral_summary else ""
        
        # Count actual questions
        total_questions = len(interview_data)
        technical_questions = [item for item in interview_data if item["question_data"]["type"] == "technical"]
        non_technical_questions = [item for item in interview_data if item["question_data"]["type"] == "non-technical"]
        
        prompt = f"""
        You are an expert technical interviewer analyzing a completed interview. Provide a completely honest, evidence-based assessment.
        
        # Job Description:
        {self.job_description}
        
        # Candidate's CV:
        {self.cv}
        
        # Interview Data:
        Total Questions: {total_questions}
        Technical Questions: {len(technical_questions)}
        Non-Technical Questions: {len(non_technical_questions)}
        
        # Detailed Q&A Analysis:
        {interview_json}
        {behavioral_section}
        
        ## EVALUATION TASK
        Create a thorough, detailed, and critical feedback report for the candidate. Your evaluation must be rigorous, specific, and evidence-based.
        
        ## EVALUATION CRITERIA
        For EACH answer, you must:
        1. Assess factual correctness (Are there any errors or misconceptions?)
        2. Evaluate completeness (Did they cover all important aspects?)
        3. Check for depth of understanding (Do they show deep knowledge or just surface-level familiarity?)
        4. Analyze communication clarity (Was the answer well-structured and clearly articulated?)
        5. Identify specific strengths and weaknesses
        
        ## SCORING RUBRIC
        For each question, assign a score from 0-10 based on these criteria:
        - 0-2: Completely incorrect or irrelevant answer
        - 3-4: Major gaps or errors, minimal understanding
        - 5-6: Basic understanding with some errors or omissions
        - 7-8: Good understanding with minor gaps or imprecisions
        - 9-10: Excellent, comprehensive, and accurate answer
        
        ## REPORT STRUCTURE
        Your report must include these sections:
        
        1. Overall Assessment: An objective summary of the candidate's performance
        
        2. Technical Skills Analysis:
           - Evaluate EACH technical answer individually with specific feedback
           - Identify patterns across technical answers
           - Highlight factual errors, misconceptions, and knowledge gaps
           - Be brutally honest in pointing out major flaws
           - Use exact quotes from responses to highlight issues
        
        3. Non-Technical Skills Analysis:
           - Evaluate EACH non-technical answer individually
           - Assess communication skills, problem-solving approach, and self-awareness
           - Directly reference parts of the answer to justify scores
           - Be critical yet fair, highlighting specific language used
        
        4. Specific Improvement Areas:
           - List 3-5 concrete areas where improvement is most needed
           - For each area, provide specific examples from their answers
           - Avoid generalities; focus on exact issues in understanding
        
        5. Actionable Development Plan:
           - Recommend specific resources, courses, or activities
           - Prioritize recommendations based on critical needs
           - Suggest practical steps based on answer analysis
        
        6. Final Evaluation:
           - Provide a clear hiring recommendation (Strongly Recommend, Recommend, Recommend with Reservations, Do Not Recommend)
           - Justify your recommendation with specific evidence
           - Make sure recommendations align with the overall analysis
        
        7. Detailed Scoring:
           - Score each non-technical question (0-10)
           - Score each technical question (0-10)
           - Calculate averages for each category
           - Calculate final score: (Non-Technical Average × 0.3) + (Technical Average × 0.7)
           - Convert to percentage (0-100%)
        
        ## IMPORTANT REQUIREMENTS
        - Be specific and reference actual answers in your feedback
        - Do not be vague or generic - cite exact statements or omissions
        - Be honest and critical - do not inflate scores or soften criticism
        - Ensure mathematical accuracy in all score calculations
        - Double-check that your evaluation is consistent with the scoring
        
        ## EXAMPLE EVALUATION FORMAT
        For each answer evaluation, use this format:
        
        Question: [Question text]
        Answer: [Answer text]
        Evaluation:
        - Factual Accuracy: [Assessment with specific examples from the answer]
        - Completeness: [Assessment noting missing elements]
        - Depth of Understanding: [Assessment of conceptual grasp]
        - Communication: [Assessment of clarity and structure]
        - Critical Issues: [Highlight major problems, misconceptions, or errors]
        - Answer Quality: [Overall quality assessment with brutal honesty]
        Score: [0-10]/10
        Specific Feedback: [Concrete, harsh but fair criticism and improvement advice]
        
        ## EVALUATION APPROACH - PURELY DYNAMIC ANALYSIS
        - Base your evaluation ONLY on the actual answers provided in the interview data above
        - Quote exact phrases from the candidate's actual responses
        - If behavioral analysis data is provided, incorporate those specific observations
        - Do NOT use any pre-written or template responses
        - Identify specific technical errors from the actual answers given
        - Assess the actual communication style demonstrated in their responses
        - Reference specific behavioral patterns observed during the video analysis
        - Calculate scores based solely on the quality of actual responses provided
        - If no meaningful answers were provided, state this explicitly
        - Be completely honest about the actual performance demonstrated
        """
        
        logger.info("\nGenerating comprehensive interview feedback report...")
        logger.info("This may take a moment...")
        
        if TOGETHER_AVAILABLE:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert technical interviewer who provides detailed, evidence-based feedback. You evaluate each answer thoroughly and provide specific, actionable feedback."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4000
                )
                
                self.report = response.choices[0].message.content
            except Exception as e:
                logger.error(f"Error generating report: {e}")
                self.report = self._get_mock_report()
        else:
            # Use mock report for testing
            self.report = self._get_mock_report()
        
        # Validate and fix the scoring if needed
        self.report = self._validate_and_fix_scoring(self.report, interview_data)
            
        logger.info("✓ Interview report generated")
        return self.report

    def _validate_and_fix_scoring(self, report: str, interview_data: List[Dict]) -> str:
        """Validate and fix the scoring in the report with enhanced accuracy."""
        try:
            # Count the number of technical and non-technical questions
            technical_questions = []
            non_technical_questions = []
            
            for item in interview_data:
                q_type = item["question_data"]["type"]
                if q_type == "technical":
                    technical_questions.append(item)
                elif q_type == "non-technical":
                    non_technical_questions.append(item)
            
            # Extract individual scores from the report
            non_tech_scores = []
            tech_scores = []
            
            # Look for score patterns like "Score: 7/10" or "Score: 7.5/10"
            score_pattern = r'Score:\s*(\d+(\.\d+)?)/10'
            
            # Extract all scores
            all_scores = re.findall(score_pattern, report)
            all_scores = [float(score[0]) for score in all_scores]
            
            # If we found enough scores, separate them into technical and non-technical
            if len(all_scores) >= len(technical_questions) + len(non_technical_questions):
                # Assume first scores are non-technical, rest are technical
                non_tech_scores = all_scores[:len(non_technical_questions)]
                tech_scores = all_scores[len(non_technical_questions):len(non_technical_questions) + len(technical_questions)]
            
            # Extract the reported averages
            non_tech_avg_match = re.search(r'Non-Technical Average[^\d]*(\d+(\.\d+)?)', report)
            tech_avg_match = re.search(r'Technical Average[^\d]*(\d+(\.\d+)?)', report)
            final_score_match = re.search(r'Final Score:?\s*(\d+(\.\d+)?)', report)
            
            reported_non_tech_avg = 0
            reported_tech_avg = 0
            reported_final_score = 0
            
            if non_tech_avg_match:
                reported_non_tech_avg = float(non_tech_avg_match.group(1))
            if tech_avg_match:
                reported_tech_avg = float(tech_avg_match.group(1))
            if final_score_match:
                reported_final_score = float(final_score_match.group(1))
            
            # Calculate correct averages
            correct_non_tech_avg = 0
            if non_tech_scores:
                correct_non_tech_avg = sum(non_tech_scores) / len(non_tech_scores)
            
            correct_tech_avg = 0
            if tech_scores:
                correct_tech_avg = sum(tech_scores) / len(tech_scores)
            
            # Calculate correct final score (0-100 scale)
            correct_final_score = (correct_non_tech_avg * 10 * 0.3) + (correct_tech_avg * 10 * 0.7)
            
            # Check if we need to fix the scores
            needs_fixing = (
                (not non_tech_avg_match or not tech_avg_match or not final_score_match) or
                (abs(reported_non_tech_avg - correct_non_tech_avg) > 0.1 if non_tech_scores else False) or
                (abs(reported_tech_avg - correct_tech_avg) > 0.1 if tech_scores else False) or
                (abs(reported_final_score - correct_final_score) > 1.0)
            )
            
            if needs_fixing:
                logger.info(f"Fixing scoring in report: Non-tech {reported_non_tech_avg} -> {correct_non_tech_avg:.1f}, Tech {reported_tech_avg} -> {correct_tech_avg:.1f}, Final {reported_final_score} -> {correct_final_score:.1f}")
                
                # Create a new scoring section
                new_scoring_section = f"""
## Detailed Scoring (Recalculated for Accuracy)

### Non-Technical Questions (30% of total)
"""
                
                # Add individual non-technical scores
                for i, score in enumerate(non_tech_scores):
                    question_num = i + 1
                    new_scoring_section += f"{question_num}. {score}/10\n"
                
                new_scoring_section += f"\n**Non-Technical Average**: {correct_non_tech_avg:.1f}/10\n\n"
                
                # Add individual technical scores
                new_scoring_section += "### Technical Questions (70% of total)\n"
                for i, score in enumerate(tech_scores):
                    question_num = i + 1
                    new_scoring_section += f"{question_num}. {score}/10\n"
                
                new_scoring_section += f"\n**Technical Average**: {correct_tech_avg:.1f}/10\n\n"
                
                # Add final score calculation
                new_scoring_section += f"""### Final Score Calculation
- Non-Technical Component: {correct_non_tech_avg:.1f} × 0.3 = {correct_non_tech_avg * 0.3:.2f}
- Technical Component: {correct_tech_avg:.1f} × 0.7 = {correct_tech_avg * 0.7:.2f}

**Final Score: {correct_final_score:.1f}%**
"""
                
                # Try to replace the existing scoring section
                scoring_section_match = re.search(r'## Detailed Scoring.*?Final Score:.*?%', report, re.DOTALL)
                if scoring_section_match:
                    report = report.replace(scoring_section_match.group(0), new_scoring_section.strip())
                else:
                    # If we can't find the scoring section, append it to the end
                    report += "\n\n" + new_scoring_section
                
                # Also fix any references to the scores in the text
                if non_tech_avg_match:
                    report = re.sub(
                        r'Non-Technical Average[^\d]*(\d+(\.\d+)?)',
                        f'Non-Technical Average: {correct_non_tech_avg:.1f}',
                        report
                    )
                
                if tech_avg_match:
                    report = re.sub(
                        r'Technical Average[^\d]*(\d+(\.\d+)?)',
                        f'Technical Average: {correct_tech_avg:.1f}',
                        report
                    )
                
                if final_score_match:
                    report = re.sub(
                        r'Final Score:?\s*(\d+(\.\d+)?)',
                        f'Final Score: {correct_final_score:.1f}',
                        report
                    )
        
        except Exception as e:
            logger.error(f"Error validating and fixing scoring: {e}")
        
        return report
    
    def _get_mock_report(self):
        """Return a basic fallback report when no interview data is available."""
        return """# Interview Feedback Report

## System Notice

This is a fallback report generated when actual interview data is not available. 
For accurate assessment, please ensure the interview session has been completed with:
- Recorded answers to all questions
- Camera-based emotion and posture analysis data
- Complete interview session from start to finish

## Recommendations

1. Complete the full interview process
2. Ensure camera permissions are enabled for behavioral analysis
3. Provide detailed answers to all interview questions
4. Allow the system to collect sufficient behavioral data during the session

Once these requirements are met, a comprehensive, personalized report will be generated based on your actual performance.
"""


class MockTogetherClient:
    """Mock implementation of Together AI client for testing."""
    def __init__(self):
        self.chat = MockChatCompletions()

class MockChatCompletions:
    """Mock implementation of chat completions for testing."""
    def create(self, **kwargs):
        return MockResponse()

class MockResponse:
    """Mock response object for testing."""
    def __init__(self):
        self.choices = [MockChoice()]

class MockChoice:
    """Mock choice object for testing."""
    def __init__(self):
        self.message = MockMessage()

class MockMessage:
    """Mock message object for testing."""
    def __init__(self):
        self.content = "Mock response content"

class MockRecognizer:
    """Mock implementation of speech recognition for testing."""
    def __init__(self):
        self.energy_threshold = 300
        self.dynamic_energy_threshold = True
        self.pause_threshold = 2.0
    
    def adjust_for_ambient_noise(self, source, duration=1):
        pass
    
    def listen(self, source, timeout=None, phrase_time_limit=None):
        return MockAudio()
    
    def recognize_google(self, audio, language="en-US"):
        """Mock implementation of Google speech recognition."""
        return "This is a mock response from speech recognition"

class MockAudio:
    """Mock audio object for testing."""
    def get_raw_data(self):
        return b"mock audio data"

class MockTTSEngine:
    """Mock implementation of text-to-speech engine for testing."""
    def __init__(self):
        self.properties = {}
    
    def setProperty(self, name, value):
        self.properties[name] = value
    
    def getProperty(self, name):
        return self.properties.get(name, None)
    
    def say(self, text):
        pass
    
    def runAndWait(self):
        pass
    
    def connect(self, signal, callback):
        pass
