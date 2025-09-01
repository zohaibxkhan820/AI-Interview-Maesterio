import cv2
import numpy as np
import mediapipe as mp

class MediaPipePostureAnalyzer:
    """
    Accurate posture analysis using MediaPipe pose landmarks (shoulders, nose).
    """
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5, min_tracking_confidence=0.5)

    def analyze(self, landmarks):
        idx = self.mp_pose.PoseLandmark
        try:
            left_shoulder = np.array([landmarks[idx.LEFT_SHOULDER.value].x, landmarks[idx.LEFT_SHOULDER.value].y])
            right_shoulder = np.array([landmarks[idx.RIGHT_SHOULDER.value].x, landmarks[idx.RIGHT_SHOULDER.value].y])
            nose = np.array([landmarks[idx.NOSE.value].x, landmarks[idx.NOSE.value].y])
        except Exception:
            return "No Person", {}
        shoulder_center_x = (left_shoulder[0] + right_shoulder[0]) / 2
        shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
        nose_offset = (nose[0] - shoulder_center_x) / (shoulder_width + 1e-6)
        shoulder_tilt = left_shoulder[1] - right_shoulder[1]
        details = {
            "shoulder_tilt": float(shoulder_tilt),
            "nose_offset": float(nose_offset),
            "shoulder_center_x": float(shoulder_center_x),
            "nose_x": float(nose[0]),
            "shoulder_width": float(shoulder_width)
        }
        TILT_THRESH = 0.07
        OFFSET_THRESH = 0.18
        SLOUCH_Y_THRESH = 0.08
        avg_shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2
        nose_y = nose[1]
        nose_vs_shoulder = nose_y - avg_shoulder_y
        if nose_vs_shoulder > SLOUCH_Y_THRESH:
            posture = "Slouched"
        elif nose_offset > OFFSET_THRESH or shoulder_tilt < -TILT_THRESH:
            posture = "Leaning Right"
        elif nose_offset < -OFFSET_THRESH or shoulder_tilt > TILT_THRESH:
            posture = "Leaning Left"
        elif abs(nose_offset) < 0.08 and abs(shoulder_tilt) < 0.04 and nose_vs_shoulder < 0.02:
            posture = "Attentive"
        else:
            posture = "Neutral"
        return posture, details

    def draw_landmarks(self, frame, results):
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing.draw_landmarks(
            frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0,255,0), thickness=1, circle_radius=1),
            mp_drawing.DrawingSpec(color=(0,0,255), thickness=1, circle_radius=1)
        )

    def process_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)
        posture = "No Person"
        if results.pose_landmarks:
            posture, _ = self.analyze(results.pose_landmarks.landmark)
            self.draw_landmarks(frame, results)
        cv2.putText(frame, f"Posture: {posture}", (10, 320), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)
        return frame
