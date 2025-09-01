# -*- coding: utf-8 -*-
__all__ = ['EfficientEmotionDetector']
import cv2
import numpy as np
from collections import deque

FACE_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
EYE_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_eye.xml'
MOUTH_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_smile.xml'

class EfficientEmotionDetector:
    """
    Efficient emotion detection with realistic, detectable thresholds.
    """
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
        self.eye_cascade = cv2.CascadeClassifier(EYE_CASCADE_PATH)
        self.mouth_cascade = cv2.CascadeClassifier(MOUTH_CASCADE_PATH)
        self.emotion_history = deque(maxlen=5)

    def detect_face(self, gray):
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(100, 100))
        if len(faces) > 0:
            valid_faces = [f for f in faces if f[0] > 10 and f[1] > 10 
                         and f[0] + f[2] < gray.shape[1] - 10 
                         and f[1] + f[3] < gray.shape[0] - 10]
            if valid_faces:
                return max(valid_faces, key=lambda f: f[2] * f[3])
            return max(faces, key=lambda f: f[2] * f[3])
        return None

    def detect_eyes(self, gray, face_box):
        x, y, w, h = face_box
        roi_gray = gray[y:y+h//2, x:x+w]
        eyes = self.eye_cascade.detectMultiScale(
            roi_gray, 1.15, 4,
            minSize=(w//12, h//12),
            maxSize=(w//3, h//3)
        )
        eyes = [(x+ex, y+ey, ew, eh) for ex, ey, ew, eh in eyes]
        if len(eyes) >= 2:
            sorted_eyes = sorted(eyes, key=lambda e: e[0])
            left_eyes = [e for e in sorted_eyes if e[0] < x + w//2]
            right_eyes = [e for e in sorted_eyes if e[0] >= x + w//2]
            result = []
            if left_eyes:
                result.append(max(left_eyes, key=lambda e: e[2]*e[3]))
            if right_eyes:
                result.append(max(right_eyes, key=lambda e: e[2]*e[3]))
            return result
        return sorted(eyes, key=lambda e: e[2]*e[3], reverse=True)[:2]

    def detect_mouth(self, gray, face_box):
        x, y, w, h = face_box
        roi_y = y + int(h * 0.6)
        roi_h = y + h - roi_y
        roi_gray = gray[roi_y:y+h, x:x+w]
        mouth_params = [
            (1.7, 11, w//4, h//4),
            (1.5, 13, w//5, h//5),
            (1.9, 9, w//3, h//3)
        ]
        for scale, neighbors, min_w, min_h in mouth_params:
            mouths = self.mouth_cascade.detectMultiScale(
                roi_gray, scale, neighbors,
                minSize=(min_w, min_h),
                maxSize=(w, h//2)
            )
            if len(mouths) > 0:
                center_x = w // 2
                mx, my, mw, mh = min(mouths, 
                    key=lambda m: abs((m[0] + m[2]//2) - center_x))
                return (x+mx, roi_y+my, mw, mh)
        return None

    def calculate_simple_features(self, gray, face_box, eyes, mouth):
        x, y, w, h = face_box
        features = {
            'num_eyes': len(eyes),
            'eye_height_ratio': 0.0,
            'eye_width_ratio': 0.0,
            'eye_vertical_pos': 0.0,
            'mouth_detected': mouth is not None,
            'mouth_size_ratio': 0.0,
            'mouth_vertical_pos': 0.0,
            'mouth_width_ratio': 0.0,
            'face_ratio': w / h
        }
        if eyes:
            total_eye_height = sum(eh for _, _, _, eh in eyes)
            total_eye_width = sum(ew for _, _, ew, _ in eyes)
            avg_eye_y = sum(ey for _, ey, _, _ in eyes) / len(eyes)
            features['eye_height_ratio'] = total_eye_height / h
            features['eye_width_ratio'] = total_eye_width / w
            features['eye_vertical_pos'] = (avg_eye_y - y) / h
        if mouth:
            mx, my, mw, mh = mouth
            features['mouth_size_ratio'] = (mw * mh) / (w * h)
            features['mouth_vertical_pos'] = (my - y) / h
            features['mouth_width_ratio'] = mw / w
        return features

    def classify_emotion_simple(self, features):
        scores = {
            'Happy': 0,
            'Sad': 0,
            'Angry': 0,
            'Surprised': 0,
            'Neutral': 0,
            'Confused': 0,
            'Disgusted': 0
        }
        if features['mouth_detected']:
            if 0.016 < features['mouth_size_ratio'] < 0.045 and 0.25 < features['mouth_width_ratio'] < 0.52:
                scores['Happy'] += 5
            if 0.53 < features['mouth_vertical_pos'] < 0.72:
                scores['Happy'] += 2
            if features['eye_height_ratio'] > 0.10:
                scores['Happy'] += 1
            if features['mouth_width_ratio'] > 0.38 and features['mouth_vertical_pos'] < 0.65:
                scores['Happy'] += 2
        if features['eye_height_ratio'] > 0.16 and features['mouth_detected'] and features['mouth_size_ratio'] > 0.03:
            scores['Surprised'] += 4
        elif features['eye_height_ratio'] > 0.14:
            scores['Surprised'] += 2
        if features['mouth_detected'] and features['mouth_size_ratio'] < 0.012:
            scores['Sad'] += 2
        if 0.23 < features['eye_vertical_pos'] < 0.32:
            scores['Sad'] += 2
        if features['mouth_detected'] and features['mouth_vertical_pos'] > 0.68:
            scores['Sad'] += 1
        if not features['mouth_detected']:
            scores['Angry'] += 2
        if features['eye_height_ratio'] < 0.08 and 0.18 < features['eye_vertical_pos'] < 0.23:
            scores['Angry'] += 3
        if features['face_ratio'] > 0.92:
            scores['Angry'] += 1
        if features['num_eyes'] < 2:
            scores['Confused'] += 2
        if 0.16 < features['eye_vertical_pos'] < 0.19:
            scores['Confused'] += 1
        if features['mouth_detected'] and 0.008 < features['mouth_size_ratio'] < 0.015:
            scores['Confused'] += 2
        if features['mouth_detected'] and features['mouth_size_ratio'] < 0.01:
            scores['Disgusted'] += 2
        if features['mouth_detected'] and features['mouth_vertical_pos'] > 0.72:
            scores['Disgusted'] += 2
        if features['eye_height_ratio'] < 0.055:
            scores['Disgusted'] += 1
        neutral_conditions = [
            features['mouth_detected'],
            0.013 < features['mouth_size_ratio'] < 0.022,
            0.18 < features['eye_vertical_pos'] < 0.22,
            0.08 < features['eye_height_ratio'] < 0.12,
            0.32 < features['mouth_width_ratio'] < 0.41
        ]
        if all(neutral_conditions):
            scores['Neutral'] += 6
        max_score = max(scores.values())
        if max_score < 3:
            return 'Neutral', scores
        max_emotions = [k for k, v in scores.items() if v == max_score]
        priority = ['Happy', 'Neutral', 'Sad', 'Surprised', 'Confused', 'Disgusted', 'Angry']
        for emo in priority:
            if emo in max_emotions:
                return emo, scores
        return max_emotions[0], scores

    def smooth_emotion(self, emotion):
        self.emotion_history.append(emotion)
        if len(self.emotion_history) < 3:
            return emotion
        weights = [1.0, 0.8, 0.6, 0.4, 0.2]
        emotion_scores = {}
        for i, e in enumerate(reversed(self.emotion_history)):
            if i >= len(weights):
                break
            emotion_scores[e] = emotion_scores.get(e, 0) + weights[i]
        current = self.emotion_history[-2] if len(self.emotion_history) > 1 else emotion
        max_emotion = max(emotion_scores.items(), key=lambda x: x[1])
        threshold = emotion_scores.get(current, 0) * 1.3 if current != 'Neutral' else 0
        return max_emotion[0] if max_emotion[1] > threshold else current

    def draw_annotations(self, frame, face_box, eyes, mouth, emotion, scores, features):
        x, y, w, h = face_box
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        for ex, ey, ew, eh in eyes:
            cv2.rectangle(frame, (ex, ey), (ex+ew, ey+eh), (255, 255, 0), 2)
        if mouth:
            mx, my, mw, mh = mouth
            cv2.rectangle(frame, (mx, my), (mx+mw, my+mh), (255, 0, 255), 2)
        max_score = max(scores.values())
        cv2.putText(frame, f"Emotion: {emotion} (Score: {max_score})", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        info_y = 60
        cv2.putText(frame, f"Eyes: {features['num_eyes']}, Eye pos: {features['eye_vertical_pos']:.2f}", 
                   (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        info_y += 20
        cv2.putText(frame, f"Mouth: {features['mouth_detected']}, Size: {features['mouth_size_ratio']:.3f}", 
                   (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        info_y += 20
        sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:4]
        for i, (emo, score) in enumerate(sorted_emotions):
            if score > 0:
                cv2.putText(frame, f"{emo}: {score}", 
                           (10, info_y + i*15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
