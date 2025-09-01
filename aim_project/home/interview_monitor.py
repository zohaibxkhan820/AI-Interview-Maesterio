import cv2
import numpy as np
import threading
from collections import deque, Counter
from datetime import datetime
import mediapipe as mp
from .emotion_detector import EfficientEmotionDetector
from .posture_analyzer import MediaPipePostureAnalyzer

# Haar cascade paths
FACE_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
EYE_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_eye.xml'
MOUTH_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_smile.xml'
UPPERBODY_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_upperbody.xml'

class InterviewMonitor:
    def __init__(self):
        self.emotion_detector = EfficientEmotionDetector()
        self.posture_analyzer = MediaPipePostureAnalyzer()
        self.enable_emotion = True
        self.enable_posture = True
        self.log = []  # List of (timestamp, emotion, posture)
        self.running = True
        self.toggle_rects = {
            'emotion': ((10, 370), (210, 410)),
            'posture': ((220, 370), (420, 410))
        }

    def _handle_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            for key, (pt1, pt2) in self.toggle_rects.items():
                if pt1[0] <= x <= pt2[0] and pt1[1] <= y <= pt2[1]:
                    if key == 'emotion':
                        self.enable_emotion = not self.enable_emotion
                    elif key == 'posture':
                        self.enable_posture = not self.enable_posture

    def analyze_sentiment(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_box = self.emotion_detector.detect_face(gray)
        if face_box is not None:
            eyes = self.emotion_detector.detect_eyes(gray, face_box)
            mouth = self.emotion_detector.detect_mouth(gray, face_box)
            features = self.emotion_detector.calculate_simple_features(gray, face_box, eyes, mouth)
            emotion, scores = self.emotion_detector.classify_emotion_simple(features)
            smoothed_emotion = self.emotion_detector.smooth_emotion(emotion)
            self.emotion_detector.draw_annotations(frame, face_box, eyes, mouth, smoothed_emotion, scores, features)
            return smoothed_emotion
        return "No Face"

    def analyze_posture(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.posture_analyzer.pose.process(rgb)
        posture = "No Person"
        if results.pose_landmarks:
            posture, _ = self.posture_analyzer.analyze(results.pose_landmarks.landmark)
            self.posture_analyzer.draw_landmarks(frame, results)
        cv2.putText(frame, f"Posture: {posture}", (10, 320), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)
        return posture

    def log_status(self, emotion, posture):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.append({'timestamp': timestamp, 'emotion': emotion, 'posture': posture})

    def summarize(self):
        emotions = [entry['emotion'] for entry in self.log if entry['emotion'] not in ["No Face", None]]
        postures = [entry['posture'] for entry in self.log if entry['posture'] not in ["No Person", None]]
        emotion_counts = Counter(emotions)
        posture_counts = Counter(postures)
        dominant_emotion = emotion_counts.most_common(1)[0][0] if emotion_counts else "Unknown"
        dominant_posture = posture_counts.most_common(1)[0][0] if posture_counts else "Unknown"
        feedback = []
        if dominant_posture == "Slouched":
            feedback.append("Avoid slouching to appear more confident.")
        if dominant_emotion == "Sad":
            feedback.append("Try to appear more relaxed and positive.")
        if dominant_posture == "Attentive":
            feedback.append("Good posture maintained throughout the interview.")
        if dominant_emotion == "Happy":
            feedback.append("Positive attitude detected. Keep it up!")
        summary_text = f"""
Posture and Sentiment Analysis Log (timestamped):\n{self.log}\n\nDominant Emotion: {dominant_emotion}\nDominant Posture: {dominant_posture}\nFeedback: {'; '.join(feedback)}\n\nEmotion Trend: {dict(emotion_counts)}\nPosture Trend: {dict(posture_counts)}\n"""
        return {
            "dominant_emotion": dominant_emotion,
            "dominant_posture": dominant_posture,
            "feedback": feedback,
            "emotion_trend": dict(emotion_counts),
            "posture_trend": dict(posture_counts),
            "raw_log": self.log,
            "summary_text": summary_text
        }

    def run(self):
        cap = cv2.VideoCapture(0)
        cv2.namedWindow("Interview Simulation")
        cv2.setMouseCallback("Interview Simulation", self._handle_mouse)
        print("Click the toggle buttons or press 'q' to quit.")
        while self.running:
            ret, frame = cap.read()
            if not ret:
                break
            emotion, posture = None, None
            if self.enable_emotion:
                emotion = self.analyze_sentiment(frame)
            if self.enable_posture:
                posture = self.analyze_posture(frame)
            for key, (pt1, pt2) in self.toggle_rects.items():
                color = (0,255,0) if (self.enable_emotion if key=='emotion' else self.enable_posture) else (0,0,255)
                label = f"{'ON' if (self.enable_emotion if key=='emotion' else self.enable_posture) else 'OFF'} {key.capitalize()}"
                cv2.rectangle(frame, pt1, pt2, color, -1)
                cv2.putText(frame, label, (pt1[0]+10, pt1[1]+30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.imshow("Interview Simulation", frame)
            self.log_status(emotion if self.enable_emotion else None, posture if self.enable_posture else None)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.running = False
        cap.release()
        cv2.destroyAllWindows()
        summary = self.summarize()
        print("Session Summary:", summary)
        return summary
