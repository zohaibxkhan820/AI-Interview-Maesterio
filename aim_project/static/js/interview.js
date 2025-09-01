document.addEventListener("DOMContentLoaded", () => {
    // Check for MediaDevices API support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error("MediaDevices API or getUserMedia is not supported in this browser")

        // Find the chat messages element
        const chatMessages = document.getElementById("chat-messages")

        // Add error message if the element exists
        if (chatMessages) {
            const messageElement = document.createElement("div")
            messageElement.className = "system-message error-message"

            messageElement.innerHTML = `
        <div class="message-content">
          <p><strong>Browser Compatibility Error:</strong> Your browser does not support the required features for video interviews.</p>
          <p>Please try using the latest version of Chrome, Firefox, Safari, or Edge.</p>
        </div>
        <div class="message-time">Now</div>
      `

            chatMessages.appendChild(messageElement)
        }

        // Disable the start button
        const startButton = document.getElementById("start-interview")
        if (startButton) {
            startButton.disabled = true
            startButton.title = "Your browser does not support video interviews"
        }
    }

    // DOM Elements
    const startButton = document.getElementById("start-interview")
    const pauseButton = document.getElementById("pause-interview")
    const endButton = document.getElementById("end-interview")
    const videoElement = document.getElementById("user-video")
    const videoOverlay = document.getElementById("video-overlay")
    const timerDisplay = document.getElementById("timer-display")
    const micToggle = document.getElementById("mic-toggle")
    const cameraToggle = document.getElementById("camera-toggle")
    const chatMessages = document.getElementById("chat-messages")
    const userMessageInput = document.getElementById("user-message")
    const sendMessageButton = document.getElementById("send-message")
    const connectionStatus = document.getElementById("connection-status")
    const statusText = document.getElementById("status-text")
    const questionCounter = document.getElementById("question-counter")

    // Bootstrap Modal
    const interviewCompleteModalElement = document.getElementById("interview-complete-modal")
    let interviewCompleteModal = null
    try {
        interviewCompleteModal = new bootstrap.Modal(interviewCompleteModalElement)
    } catch (error) {
        console.error("Bootstrap not properly initialized:", error)
    }

    // Global Variables
    let stream = null
    let mediaRecorder = null
    let audioChunks = []
    let timerInterval = null
    let timeRemaining = 20 * 60 // 20 minutes in seconds
    let isPaused = false
    let isInterviewActive = false
    let currentQuestionIndex = 0
    let totalQuestions = 10
    const interviewId = document.body.dataset.interviewId
    let questions = []
    let currentQuestion = null

    // Speech Recognition Setup
    let recognition = null;
    let isListening = false;
    let speechSynthesis = window.speechSynthesis;
    let speaking = false;
    let voices = [];

    // Initialize speech recognition
    function initializeSpeechRecognition() {
        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            recognition.onresult = function(event) {
                const transcript = event.results[0][0].transcript;
                userMessageInput.value = transcript;
                sendMessage();
            };

            recognition.onerror = function(event) {
                console.error('Speech recognition error:', event.error);
                addSystemMessage(`Speech recognition error: ${event.error}`);
                isListening = false;
                micToggle.innerHTML = '<i class="fas fa-microphone"></i>';
                micToggle.classList.remove('listening');
            };

            recognition.onend = function() {
                isListening = false;
                micToggle.innerHTML = '<i class="fas fa-microphone"></i>';
                micToggle.classList.remove('listening');
            };

            console.log('Speech recognition initialized successfully');
        } else {
            console.error('Speech recognition not supported');
            addSystemMessage('Speech recognition is not supported in your browser. Please use Chrome for the best experience.');
        }
    }

    // Initialize speech synthesis voices
    function initializeSpeechSynthesis() {
        if (speechSynthesis) {
            // Load voices
            voices = speechSynthesis.getVoices();

            // If voices are not loaded yet, wait for them
            if (voices.length === 0) {
                speechSynthesis.onvoiceschanged = () => {
                    voices = speechSynthesis.getVoices();
                    console.log('Available voices:', voices);
                };
            }

            console.log('Speech synthesis initialized successfully');
        } else {
            console.error('Speech synthesis not supported');
            addSystemMessage('Text-to-speech is not supported in your browser.');
        }
    }

    // Speak text function
    function speakText(text) {
        if (!speechSynthesis) {
            console.error('Speech synthesis not available');
            return;
        }

        // Cancel any ongoing speech
        speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        // Get available voices and set a good voice
        if (voices.length > 0) {
            const preferredVoice = voices.find(voice =>
                voice.name.includes('Google') ||
                voice.name.includes('Microsoft') ||
                voice.name.includes('Samantha')
            ) || voices[0];

            if (preferredVoice) {
                utterance.voice = preferredVoice;
                console.log('Using voice:', preferredVoice.name);
            }
        }

        utterance.onstart = () => {
            speaking = true;
            console.log('Started speaking:', text);
        };

        utterance.onend = () => {
            speaking = false;
            console.log('Finished speaking');
        };

        utterance.onerror = (event) => {
            console.error('Speech synthesis error:', event);
            speaking = false;
        };

        try {
            speechSynthesis.speak(utterance);
        } catch (error) {
            console.error('Error speaking text:', error);
        }
    }

    // ===== CAMERA AND AUDIO FUNCTIONS =====

    // Initialize media devices
    async function initializeMedia() {
        try {
            // Clear any previous error messages
            addSystemMessage("Requesting camera and microphone access...")

            // Request with explicit constraints
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: "user",
                },
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            })

            // Check if we actually got both audio and video tracks
            const videoTracks = stream.getVideoTracks()
            const audioTracks = stream.getAudioTracks()

            if (videoTracks.length === 0) {
                throw new Error("No video track available. Camera may be in use by another application.")
            }

            if (audioTracks.length === 0) {
                throw new Error("No audio track available. Microphone may be in use by another application.")
            }

            // Set the stream as the video source
            videoElement.srcObject = stream
            videoElement.onloadedmetadata = () => {
                videoElement.play().catch((e) => {
                    console.error("Error playing video:", e)
                    addSystemMessage("Error playing video: " + e.message)
                })
            }

            videoOverlay.style.display = "none"

            // Initialize media recorder for audio
            try {
                mediaRecorder = new MediaRecorder(stream)

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data)
                    }
                }
            } catch (recorderError) {
                console.error("Error initializing MediaRecorder:", recorderError)
                addSystemMessage("Warning: Audio recording may not work properly. " + recorderError.message)
                    // Continue anyway as we can still use the camera and mic for live interaction
            }

            updateStatus("connected", "Camera and microphone connected")
            addSystemMessage("Camera and microphone connected successfully!")
            return true
        } catch (error) {
            console.error("Error accessing media devices:", error)

            // Provide more specific error messages based on the error
            if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
                updateStatus("disconnected", "Permission denied")
                addSystemMessage(
                    "Camera or microphone access was denied. Please check your browser permissions and try again. You may need to click the camera icon in your browser's address bar and allow access.",
                )
            } else if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
                updateStatus("disconnected", "No camera/mic found")
                addSystemMessage(
                    "No camera or microphone found. Please connect a camera and microphone to your device and try again.",
                )
            } else if (error.name === "NotReadableError" || error.name === "TrackStartError") {
                updateStatus("disconnected", "Camera/mic in use")
                addSystemMessage(
                    "Could not access your camera or microphone. They might be in use by another application. Please close other applications that might be using your camera or microphone and try again.",
                )
            } else if (error.name === "OverconstrainedError") {
                updateStatus("disconnected", "Camera constraints error")
                addSystemMessage("Your camera does not meet the required constraints. Please try using a different camera.")
            } else if (error.name === "SecurityError") {
                updateStatus("disconnected", "Security error")
                addSystemMessage("A security error occurred. This might be due to insecure context (not using HTTPS).")
            } else {
                updateStatus("disconnected", "Media access error")
                addSystemMessage(
                    `Error accessing camera or microphone: ${error.message}. Please check your device connections and browser settings.`,
                )
            }

            return false
        }
    }

    // Toggle microphone
    function toggleMicrophone() {
        if (!stream) {
            addSystemMessage("Please start the interview first.");
            return;
        }

        const audioTracks = stream.getAudioTracks();
        if (audioTracks.length === 0) {
            addSystemMessage("No audio track available.");
            return;
        }

        if (!recognition) {
            initializeSpeechRecognition();
        }

        if (!isListening) {
            try {
                // Start listening
                recognition.start();
                isListening = true;
                micToggle.innerHTML = '<i class="fas fa-microphone"></i>';
                micToggle.classList.add('listening');
                addSystemMessage("Listening... Speak your answer.");
            } catch (error) {
                console.error('Error starting speech recognition:', error);
                addSystemMessage("Error starting speech recognition. Please try again.");
                isListening = false;
            }
        } else {
            // Stop listening
            try {
                recognition.stop();
            } catch (error) {
                console.error('Error stopping speech recognition:', error);
            }
            isListening = false;
            micToggle.innerHTML = '<i class="fas fa-microphone"></i>';
            micToggle.classList.remove('listening');
        }
    }

    // Toggle camera
    function toggleCamera() {
        if (!stream) return

        const videoTracks = stream.getVideoTracks()
        if (videoTracks.length === 0) return

        const enabled = !videoTracks[0].enabled
        videoTracks[0].enabled = enabled

        if (enabled) {
            cameraToggle.innerHTML = '<i class="fas fa-video"></i>'
            cameraToggle.classList.remove("disabled")
        } else {
            cameraToggle.innerHTML = '<i class="fas fa-video-slash"></i>'
            cameraToggle.classList.add("disabled")
        }
    }

    // Stop all media tracks
    function stopMediaTracks() {
        if (stream) {
            stream.getTracks().forEach((track) => track.stop())
            stream = null
        }
    }

    // ===== TIMER FUNCTIONS =====

    // Format time as MM:SS
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60)
        const remainingSeconds = seconds % 60
        return `${minutes.toString().padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`
    }

    // Start the timer
    function startTimer() {
        if (timerInterval) clearInterval(timerInterval)

        timerDisplay.textContent = formatTime(timeRemaining)

        timerInterval = setInterval(() => {
            if (!isPaused) {
                timeRemaining--
                timerDisplay.textContent = formatTime(timeRemaining)

                // Warning when 5 minutes remaining
                if (timeRemaining === 300) {
                    timerDisplay.style.color = "#ffc107" // Warning color
                    addSystemMessage("5 minutes remaining in your interview.")
                }

                // Warning when 1 minute remaining
                if (timeRemaining === 60) {
                    timerDisplay.style.color = "#ff4d4d" // Error color
                    addSystemMessage("1 minute remaining in your interview.")
                }

                // End interview when time is up
                if (timeRemaining <= 0) {
                    endInterview()
                }
            }
        }, 1000)
    }

    // Pause the timer
    function pauseTimer() {
        isPaused = true
    }

    // Resume the timer
    function resumeTimer() {
        isPaused = false
    }

    // Reset the timer
    function resetTimer() {
        if (timerInterval) clearInterval(timerInterval)
        timeRemaining = 20 * 60
        timerDisplay.textContent = formatTime(timeRemaining)
        timerDisplay.style.color = "" // Reset color
    }

    // ===== CHAT FUNCTIONS =====

    // Add a system message to the chat
    function addSystemMessage(message) {
        const messageElement = document.createElement("div")
        messageElement.className = "system-message"

        const now = new Date()
        const timeString = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

        messageElement.innerHTML = `
            <div class="message-content">
                <p>${message}</p>
            </div>
            <div class="message-time">${timeString}</div>
        `

        chatMessages.appendChild(messageElement)
        scrollToBottom()
    }

    // Add a user message to the chat
    function addUserMessage(message) {
        const messageElement = document.createElement("div")
        messageElement.className = "user-message"

        const now = new Date()
        const timeString = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

        messageElement.innerHTML = `
            <div class="message-content">
                <p>${message}</p>
            </div>
            <div class="message-time">${timeString}</div>
        `

        chatMessages.appendChild(messageElement)
        scrollToBottom()
    }

    // Add an AI message to the chat
    function addAIMessage(message) {
        const messageElement = document.createElement("div");
        messageElement.className = "ai-message";

        messageElement.innerHTML = `
            <div class="message-content">
                <p>${message}</p>
            </div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;

        chatMessages.appendChild(messageElement);
        scrollToBottom();

        // Speak the AI message
        if (speechSynthesis) {
            // Small delay to ensure the message is displayed first
            setTimeout(() => {
                speakText(message);
            }, 100);
        }
    }

    // Scroll chat to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight
    }

    // Send a user message
    function sendMessage() {
        const message = userMessageInput.value.trim()
        if (!message || !currentQuestion) return

        addUserMessage(message)
        userMessageInput.value = ""

        // Send the answer to the server
        submitAnswer(currentQuestion.id, message)
            .then(() => {
                // Move to the next question
                showNextQuestion()
            })
            .catch((error) => {
                console.error("Error submitting answer:", error)
                addSystemMessage("There was an error submitting your answer. Please try again.")
            })
    }

    // Update the question counter
    function updateQuestionCounter() {
        if (questions.length > 0) {
            const answeredCount = questions.filter((q) => q.answered).length
            questionCounter.textContent = `Question: ${answeredCount}/${questions.length}`
        } else {
            questionCounter.textContent = `Question: ${currentQuestionIndex}/${totalQuestions}`
        }
    }

    // ===== API FUNCTIONS =====

    // Start the AI interview
    async function startAIInterview() {
        try {
            const response = await fetch(`/api/ai-interview/start/${interviewId}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute("content"),
                },
            })

            const data = await response.json()

            if (data.success) {
                addSystemMessage("AI interview started. Generating questions based on your CV and the job description...")

                // Poll for questions
                pollForQuestions()
            } else {
                addSystemMessage(`Failed to start AI interview: ${data.message}`)
            }
        } catch (error) {
            console.error("Error starting AI interview:", error)
            addSystemMessage("There was an error starting the AI interview. Please try again.")
        }
    }

    // Poll for questions
    async function pollForQuestions() {
        try {
            const response = await fetch(`/api/ai-interview/questions/${interviewId}/`)
            const data = await response.json()

            if (data.success) {
                questions = data.questions
                totalQuestions = questions.length

                // Update question counter
                updateQuestionCounter()

                // Show the first question
                showNextQuestion()
            } else {
                // If questions are not ready yet, poll again after a delay
                setTimeout(pollForQuestions, 3000)
            }
        } catch (error) {
            console.error("Error polling for questions:", error)
            setTimeout(pollForQuestions, 5000)
        }
    }

    // Show the next question
    function showNextQuestion() {
        // Find the next unanswered question
        const nextQuestion = questions.find((q) => !q.answered)

        if (nextQuestion) {
            currentQuestion = nextQuestion
            addAIMessage(nextQuestion.question)
        } else {
            // All questions have been answered
            addSystemMessage("You have answered all the questions. You can now complete the interview.")

            // Enable the end interview button
            endButton.disabled = false
        }
    }

    // Submit an answer
    async function submitAnswer(questionId, answer) {
        try {
            const response = await fetch(`/api/ai-interview/answer/${interviewId}/${questionId}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute("content"),
                },
                body: JSON.stringify({ answer }),
            })

            const data = await response.json()

            if (data.success) {
                // Mark the question as answered
                const questionIndex = questions.findIndex((q) => q.id === questionId)
                if (questionIndex !== -1) {
                    questions[questionIndex].answered = true
                }

                // Update question counter
                updateQuestionCounter()

                return data
            } else {
                throw new Error(data.message)
            }
        } catch (error) {
            console.error("Error submitting answer:", error)
            throw error
        }
    }

    // Complete the AI interview
    async function completeAIInterview() {
        try {
            const response = await fetch(`/api/ai-interview/complete/${interviewId}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute("content"),
                },
            })

            const data = await response.json()

            if (data.success) {
                addSystemMessage(data.message)

                // Show completion modal
                if (interviewCompleteModal) {
                    interviewCompleteModal.show()
                }

                return data
            } else {
                throw new Error(data.message)
            }
        } catch (error) {
            console.error("Error completing AI interview:", error)
            addSystemMessage(`Error completing interview: ${error.message}`)
            throw error
        }
    }

    // ===== INTERVIEW CONTROL FUNCTIONS =====

    // Start the interview
    async function startInterview() {
        // Disable the start button to prevent multiple clicks
        startButton.disabled = true

        // Update UI to show we're attempting to connect
        updateStatus("connecting", "Connecting to camera...")
        addSystemMessage("Initializing interview session. Please allow camera and microphone access when prompted.")

        try {
            const mediaInitialized = await initializeMedia()
            if (!mediaInitialized) {
                // Re-enable the start button if media initialization failed
                startButton.disabled = false
                return
            }

            isInterviewActive = true

            // Update UI
            pauseButton.disabled = false
            endButton.disabled = true
            userMessageInput.disabled = false
            sendMessageButton.disabled = false

            // Start timer
            startTimer()

            // Add welcome message
            addSystemMessage(
                "Interview started. The AI interviewer will now ask you questions based on your CV and the job description.",
            )

            // Start the AI interview
            startAIInterview()
        } catch (error) {
            console.error("Error starting interview:", error)
            addSystemMessage(`Failed to start interview: ${error.message}. Please try again.`)
            updateStatus("disconnected", "Start failed")
            startButton.disabled = false
        }
    }

    // Pause the interview
    function pauseInterview() {
        if (!isInterviewActive) return

        if (isPaused) {
            // Resume
            resumeTimer()
            pauseButton.innerHTML = '<i class="fas fa-pause"></i> Pause Interview'
            addSystemMessage("Interview resumed.")
        } else {
            // Pause
            pauseTimer()
            pauseButton.innerHTML = '<i class="fas fa-play"></i> Resume Interview'
            addSystemMessage("Interview paused.")
        }
    }

    // End the interview
    function endInterview() {
        if (!isInterviewActive) return

        isInterviewActive = false

        // Stop timer
        if (timerInterval) clearInterval(timerInterval)

        // Stop recording
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop()
        }

        // Update UI
        startButton.disabled = false
        pauseButton.disabled = true
        endButton.disabled = true
        userMessageInput.disabled = true
        sendMessageButton.disabled = true

        // Reset UI
        videoOverlay.style.display = "flex"
        resetTimer()

        // Stop media tracks
        stopMediaTracks()

        // Add completion message
        addSystemMessage("Interview completed. Thank you for your participation.")

        // Complete the AI interview
        completeAIInterview()
            .then((data) => {
                // Show completion modal
                if (interviewCompleteModal) {
                    interviewCompleteModal.show()
                }
            })
            .catch((error) => {
                console.error("Error completing interview:", error)
            })

        // Reset audio chunks
        audioChunks = []

        // Reset question counter
        currentQuestionIndex = 0
        updateQuestionCounter()
    }

    // Update connection status
    function updateStatus(status, message) {
        connectionStatus.className = "fas fa-circle status-indicator " + status
        statusText.textContent = message
    }

    // ===== ANALYSIS TOGGLE SWITCHES =====

    // Analysis Toggle Switches
    const toggleEmotion = document.getElementById('toggle-emotion');
    const togglePosture = document.getElementById('toggle-posture');
    let emotionAnalysisEnabled = toggleEmotion ? toggleEmotion.checked : true;
    let postureAnalysisEnabled = togglePosture ? togglePosture.checked : true;
    let analysisInterval = null;
    let lastAnalysisResult = { emotion: '', posture: '' };

    if (toggleEmotion) {
        toggleEmotion.addEventListener('change', function() {
            emotionAnalysisEnabled = this.checked;
        });
    }
    if (togglePosture) {
        togglePosture.addEventListener('change', function() {
            postureAnalysisEnabled = this.checked;
        });
    }

    // UI for displaying analysis results
    const analysisResultDiv = document.createElement('div');
    analysisResultDiv.id = 'analysis-result';
    analysisResultDiv.style.position = 'absolute';
    analysisResultDiv.style.top = '10px';
    analysisResultDiv.style.right = '10px';
    analysisResultDiv.style.background = 'rgba(0,0,0,0.7)';
    analysisResultDiv.style.color = '#fff';
    analysisResultDiv.style.padding = '10px 18px';
    analysisResultDiv.style.borderRadius = '8px';
    analysisResultDiv.style.zIndex = '10';
    analysisResultDiv.style.fontSize = '1.1em';
    analysisResultDiv.innerHTML = '';
    document.querySelector('.video-container').appendChild(analysisResultDiv);

    function updateAnalysisResultUI(result) {
        let html = '';
        if (result.emotion) html += `<b>Emotion:</b> ${result.emotion} <br/>`;
        if (result.posture) html += `<b>Posture:</b> ${result.posture}`;
        analysisResultDiv.innerHTML = html;
    }

    // Periodically send snapshots for analysis
    function startAnalysisSnapshots() {
        if (analysisInterval) clearInterval(analysisInterval);
        analysisInterval = setInterval(() => {
            if (!emotionAnalysisEnabled && !postureAnalysisEnabled) return;
            if (!videoElement || videoElement.readyState < 2) return;
            // Draw video frame to canvas
            const canvas = document.createElement('canvas');
            canvas.width = videoElement.videoWidth;
            canvas.height = videoElement.videoHeight;
            const ctx = canvas.getContext('2d');
            // Un-mirror the video by flipping horizontally before drawing
            ctx.save();
            ctx.translate(canvas.width, 0);
            ctx.scale(-1, 1);
            ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
            ctx.restore();
            const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
            // Send to backend
            fetch('/api/analyze-snapshot/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image: dataUrl,
                        enable_emotion: emotionAnalysisEnabled,
                        enable_posture: postureAnalysisEnabled
                    })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.result) {
                        lastAnalysisResult = data.result;
                        updateAnalysisResultUI(data.result);
                    }
                })
                .catch(err => { /* Optionally handle error */ });
        }, 2000); // every 2 seconds
    }

    // Start analysis when interview starts
    if (startButton) {
        startButton.addEventListener('click', () => {
            startAnalysisSnapshots();
        });
    }
    // Stop analysis when interview ends
    if (endButton) {
        endButton.addEventListener('click', () => {
            if (analysisInterval) clearInterval(analysisInterval);
            analysisResultDiv.innerHTML = '';
        });
    }

    // ===== EVENT LISTENERS =====

    // Start interview button
    startButton.addEventListener("click", startInterview)

    // Pause interview button
    pauseButton.addEventListener("click", pauseInterview)

    // End interview button
    endButton.addEventListener("click", endInterview)

    // Mic toggle button
    micToggle.addEventListener("click", toggleMicrophone)

    // Camera toggle button
    cameraToggle.addEventListener("click", toggleCamera)

    // Send message button
    sendMessageButton.addEventListener("click", sendMessage)

    // Send message on Enter key
    userMessageInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            sendMessage()
        }
    })

    // Initialize the page
    updateStatus("connecting", "Ready to start")
    updateQuestionCounter()

    // Initialize speech features
    initializeSpeechRecognition();
    initializeSpeechSynthesis();

    // Request microphone permission early
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                stream.getTracks().forEach(track => track.stop()); // Stop the stream after getting permission
                console.log('Microphone permission granted');
            })
            .catch(error => {
                console.error('Error getting microphone permission:', error);
                addSystemMessage('Please allow microphone access for speech recognition to work.');
            });
    }

    // Cleanup on page unload
    window.addEventListener("beforeunload", () => {
        stopMediaTracks()
        if (timerInterval) clearInterval(timerInterval)
    })
})