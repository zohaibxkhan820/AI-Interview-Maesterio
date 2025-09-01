from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Interview, InterviewQuestion, InterviewResult
from .ai_interviewer import AIInterviewer
from .interview_monitor import InterviewMonitor
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import random
import threading
import tempfile
import os
import logging
import base64
from io import BytesIO
from PIL import Image
import numpy as np
import cv2
from .emotion_detector import EfficientEmotionDetector
from .posture_analyzer import MediaPipePostureAnalyzer

# Configure logging
logger = logging.getLogger('ai_interview_views')

# Global dictionary to store AI interviewer instances for each interview
ai_interviewers = {}

# Global dictionary to store behavioral analysis data during interviews
interview_behavioral_data = {}

def generate_behavioral_analysis_summary(interview_id):
    """
    Generate a comprehensive behavioral analysis summary based on collected emotional and postural data.
    """
    try:
        # Get behavioral data for this interview
        behavioral_data = interview_behavioral_data.get(interview_id, {})
        
        if not behavioral_data:
            return "No behavioral analysis data available for this interview."
        
        # Extract emotion and posture data
        emotion_data = behavioral_data.get('emotions', [])
        posture_data = behavioral_data.get('postures', [])
        timestamps = behavioral_data.get('timestamps', [])
        
        # Analyze emotion patterns
        emotion_analysis = analyze_emotion_patterns(emotion_data)
        
        # Analyze posture patterns
        posture_analysis = analyze_posture_patterns(posture_data)
        
        # Calculate confidence and engagement scores
        confidence_score = calculate_confidence_score(emotion_data, posture_data)
        engagement_score = calculate_engagement_score(emotion_data, posture_data)
        communication_score = calculate_communication_score(emotion_data, posture_data)
        
        # Create comprehensive summary
        summary = f"""
## BEHAVIORAL ANALYSIS REPORT

### Emotional State Analysis
{emotion_analysis}

### Posture and Body Language Analysis
{posture_analysis}

### Confidence Assessment
Confidence Score: {confidence_score}/100
{generate_confidence_feedback(confidence_score, emotion_data, posture_data)}

### Engagement Level
Engagement Score: {engagement_score}/100
{generate_engagement_feedback(engagement_score, emotion_data, posture_data)}

### Communication Effectiveness
Communication Score: {communication_score}/100
{generate_communication_feedback(communication_score, emotion_data, posture_data)}

### Behavioral Recommendations
{generate_behavioral_recommendations(emotion_data, posture_data, confidence_score, engagement_score)}

### Timeline Analysis
{generate_timeline_analysis(emotion_data, posture_data, timestamps)}
"""
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating behavioral analysis: {e}")
        return "Error generating behavioral analysis."

def analyze_emotion_patterns(emotion_data):
    """Analyze emotional patterns throughout the interview."""
    if not emotion_data:
        return "No emotion data available."
    
    from collections import Counter
    
    # Count emotions
    emotion_counts = Counter(emotion_data)
    total_detections = len(emotion_data)
    
    # Calculate percentages
    emotion_percentages = {emotion: (count / total_detections) * 100 
                          for emotion, count in emotion_counts.items()}
    
    # Identify dominant emotions
    dominant_emotion = emotion_counts.most_common(1)[0][0] if emotion_counts else "Unknown"
    
    # Generate analysis
    positive_emotions = ['Happy', 'Surprised']
    negative_emotions = ['Sad', 'Angry', 'Disgusted']
    neutral_emotions = ['Neutral', 'Confused']
    
    positive_percentage = sum(emotion_percentages.get(emotion, 0) for emotion in positive_emotions)
    negative_percentage = sum(emotion_percentages.get(emotion, 0) for emotion in negative_emotions)
    neutral_percentage = sum(emotion_percentages.get(emotion, 0) for emotion in neutral_emotions)
    
    analysis = f"""
Dominant Emotion: {dominant_emotion} ({emotion_percentages.get(dominant_emotion, 0):.1f}%)
Positive Emotions: {positive_percentage:.1f}%
Neutral Emotions: {neutral_percentage:.1f}%
Negative Emotions: {negative_percentage:.1f}%

Emotion Distribution:
{chr(10).join([f'- {emotion}: {percentage:.1f}%' for emotion, percentage in emotion_percentages.items()])}

Emotional Stability: {'High' if len(set(emotion_data)) <= 3 else 'Moderate' if len(set(emotion_data)) <= 5 else 'Low'}
"""
    
    return analysis

def analyze_posture_patterns(posture_data):
    """Analyze posture patterns throughout the interview."""
    if not posture_data:
        return "No posture data available."
    
    from collections import Counter
    
    # Count postures
    posture_counts = Counter(posture_data)
    total_detections = len(posture_data)
    
    # Calculate percentages
    posture_percentages = {posture: (count / total_detections) * 100 
                          for posture, count in posture_counts.items()}
    
    # Identify dominant posture
    dominant_posture = posture_counts.most_common(1)[0][0] if posture_counts else "Unknown"
    
    # Categorize postures
    good_postures = ['Attentive', 'Neutral']
    concerning_postures = ['Slouched', 'Leaning Left', 'Leaning Right']
    
    good_percentage = sum(posture_percentages.get(posture, 0) for posture in good_postures)
    concerning_percentage = sum(posture_percentages.get(posture, 0) for posture in concerning_postures)
    
    analysis = f"""
Dominant Posture: {dominant_posture} ({posture_percentages.get(dominant_posture, 0):.1f}%)
Good Posture: {good_percentage:.1f}%
Concerning Posture: {concerning_percentage:.1f}%

Posture Distribution:
{chr(10).join([f'- {posture}: {percentage:.1f}%' for posture, percentage in posture_percentages.items()])}

Postural Consistency: {'Excellent' if good_percentage > 70 else 'Good' if good_percentage > 50 else 'Needs Improvement'}
"""
    
    return analysis

def calculate_confidence_score(emotion_data, posture_data):
    """Calculate confidence score based on emotion and posture data."""
    if not emotion_data or not posture_data:
        return 50  # Default score
    
    confidence_score = 50  # Base score
    
    # Analyze emotions for confidence indicators
    confident_emotions = ['Happy', 'Neutral']
    unconfident_emotions = ['Sad', 'Confused', 'Disgusted']
    
    confident_count = sum(1 for emotion in emotion_data if emotion in confident_emotions)
    unconfident_count = sum(1 for emotion in emotion_data if emotion in unconfident_emotions)
    
    emotion_confidence_factor = (confident_count - unconfident_count) / len(emotion_data) * 30
    
    # Analyze postures for confidence indicators
    confident_postures = ['Attentive', 'Neutral']
    unconfident_postures = ['Slouched']
    
    confident_posture_count = sum(1 for posture in posture_data if posture in confident_postures)
    unconfident_posture_count = sum(1 for posture in posture_data if posture in unconfident_postures)
    
    posture_confidence_factor = (confident_posture_count - unconfident_posture_count) / len(posture_data) * 20
    
    confidence_score += emotion_confidence_factor + posture_confidence_factor
    
    return max(0, min(100, int(confidence_score)))

def calculate_engagement_score(emotion_data, posture_data):
    """Calculate engagement score based on emotion and posture data."""
    if not emotion_data or not posture_data:
        return 50  # Default score
    
    engagement_score = 50  # Base score
    
    # Analyze emotions for engagement indicators
    engaged_emotions = ['Happy', 'Surprised', 'Neutral']
    disengaged_emotions = ['Sad', 'Disgusted']
    
    engaged_count = sum(1 for emotion in emotion_data if emotion in engaged_emotions)
    disengaged_count = sum(1 for emotion in emotion_data if emotion in disengaged_emotions)
    
    emotion_engagement_factor = (engaged_count - disengaged_count) / len(emotion_data) * 25
    
    # Analyze postures for engagement indicators
    engaged_postures = ['Attentive']
    disengaged_postures = ['Slouched']
    
    engaged_posture_count = sum(1 for posture in posture_data if posture in engaged_postures)
    disengaged_posture_count = sum(1 for posture in posture_data if posture in disengaged_postures)
    
    posture_engagement_factor = (engaged_posture_count - disengaged_posture_count) / len(posture_data) * 25
    
    engagement_score += emotion_engagement_factor + posture_engagement_factor
    
    return max(0, min(100, int(engagement_score)))

def calculate_communication_score(emotion_data, posture_data):
    """Calculate communication effectiveness score."""
    if not emotion_data or not posture_data:
        return 50  # Default score
    
    communication_score = 50  # Base score
    
    # Positive communication indicators
    good_emotions = ['Happy', 'Neutral']
    good_postures = ['Attentive', 'Neutral']
    
    good_emotion_percentage = sum(1 for emotion in emotion_data if emotion in good_emotions) / len(emotion_data)
    good_posture_percentage = sum(1 for posture in posture_data if posture in good_postures) / len(posture_data)
    
    communication_score += (good_emotion_percentage * 25) + (good_posture_percentage * 25)
    
    return max(0, min(100, int(communication_score)))

def generate_confidence_feedback(confidence_score, emotion_data, posture_data):
    """Generate confidence-specific feedback."""
    if confidence_score >= 80:
        return "Excellent confidence demonstrated throughout the interview. Maintained positive emotional state and good posture."
    elif confidence_score >= 60:
        return "Good confidence level shown. Minor improvements in emotional consistency could enhance overall presentation."
    elif confidence_score >= 40:
        return "Moderate confidence displayed. Focus on maintaining better posture and managing emotional responses during challenging questions."
    else:
        return "Low confidence detected. Significant improvement needed in body language and emotional regulation during interviews."

def generate_engagement_feedback(engagement_score, emotion_data, posture_data):
    """Generate engagement-specific feedback."""
    if engagement_score >= 80:
        return "Highly engaged throughout the interview. Showed consistent interest and attentiveness."
    elif engagement_score >= 60:
        return "Good engagement level. Occasional lapses in attention detected but overall positive."
    elif engagement_score >= 40:
        return "Moderate engagement. Work on maintaining consistent eye contact and active listening posture."
    else:
        return "Low engagement detected. Focus on active participation and showing genuine interest in the conversation."

def generate_communication_feedback(communication_score, emotion_data, posture_data):
    """Generate communication-specific feedback."""
    if communication_score >= 80:
        return "Excellent non-verbal communication skills. Body language supports verbal responses effectively."
    elif communication_score >= 60:
        return "Good communication effectiveness. Minor adjustments in posture could enhance message delivery."
    elif communication_score >= 40:
        return "Adequate communication skills. Focus on synchronizing emotional expressions with verbal content."
    else:
        return "Communication effectiveness needs improvement. Work on body language and emotional expression alignment."

def generate_behavioral_recommendations(emotion_data, posture_data, confidence_score, engagement_score):
    """Generate specific behavioral recommendations."""
    recommendations = []
    
    if confidence_score < 60:
        recommendations.append("Practice power poses before interviews to boost confidence")
        recommendations.append("Work on maintaining eye contact and avoiding fidgeting")
    
    if engagement_score < 60:
        recommendations.append("Practice active listening techniques")
        recommendations.append("Show more enthusiasm through facial expressions")
    
    # Analyze specific issues
    if posture_data and sum(1 for p in posture_data if p == 'Slouched') / len(posture_data) > 0.3:
        recommendations.append("Focus on maintaining upright posture throughout the interview")
    
    if emotion_data and sum(1 for e in emotion_data if e in ['Sad', 'Disgusted']) / len(emotion_data) > 0.2:
        recommendations.append("Practice emotional regulation techniques to maintain positive demeanor")
    
    if not recommendations:
        recommendations.append("Continue maintaining excellent behavioral patterns demonstrated during the interview")
    
    return "\n".join([f"• {rec}" for rec in recommendations])

def generate_timeline_analysis(emotion_data, posture_data, timestamps):
    """Generate timeline analysis of behavioral patterns."""
    if not timestamps or len(timestamps) != len(emotion_data):
        return "Timeline analysis not available due to insufficient timestamp data."
    
    # Divide interview into segments
    total_time = len(timestamps)
    segment_size = max(1, total_time // 4)
    
    segments = [
        ("Opening (0-25%)", emotion_data[:segment_size], posture_data[:segment_size]),
        ("Early Middle (25-50%)", emotion_data[segment_size:2*segment_size], posture_data[segment_size:2*segment_size]),
        ("Late Middle (50-75%)", emotion_data[2*segment_size:3*segment_size], posture_data[2*segment_size:3*segment_size]),
        ("Closing (75-100%)", emotion_data[3*segment_size:], posture_data[3*segment_size:])
    ]
    
    analysis = "Behavioral patterns throughout the interview:\n"
    
    for segment_name, seg_emotions, seg_postures in segments:
        if seg_emotions and seg_postures:
            dominant_emotion = max(set(seg_emotions), key=seg_emotions.count)
            dominant_posture = max(set(seg_postures), key=seg_postures.count)
            
            analysis += f"\n{segment_name}: {dominant_emotion} emotion, {dominant_posture} posture"
    
    return analysis

def calculate_body_language_score(emotion_data, posture_data):
    """Calculate body language score based on emotion and posture data."""
    if not emotion_data or not posture_data:
        return 50  # Default score
    
    body_language_score = 50  # Base score
    
    # Good body language indicators
    good_emotions = ['Happy', 'Neutral', 'Surprised']
    good_postures = ['Attentive', 'Neutral']
    
    good_emotion_percentage = sum(1 for emotion in emotion_data if emotion in good_emotions) / len(emotion_data)
    good_posture_percentage = sum(1 for posture in posture_data if posture in good_postures) / len(posture_data)
    
    body_language_score += (good_emotion_percentage * 30) + (good_posture_percentage * 20)
    
    return max(0, min(100, int(body_language_score)))

def calculate_eye_contact_score(emotion_data, posture_data):
    """Calculate eye contact score based on emotion and posture data."""
    if not emotion_data or not posture_data:
        return 70  # Default score
    
    eye_contact_score = 70  # Base score
    
    # Eye contact indicators (based on attentive posture and confident emotions)
    confident_emotions = ['Happy', 'Neutral']
    attentive_postures = ['Attentive']
    
    confident_emotion_percentage = sum(1 for emotion in emotion_data if emotion in confident_emotions) / len(emotion_data)
    attentive_posture_percentage = sum(1 for posture in posture_data if posture in attentive_postures) / len(posture_data)
    
    eye_contact_score += (confident_emotion_percentage * 15) + (attentive_posture_percentage * 15)
    
    return max(0, min(100, int(eye_contact_score)))

@login_required
def ai_interview_start(request, interview_id):
    """Initialize the AI interview and generate questions."""
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    try:
        # Create a new AI interviewer instance for this interview
        ai_interviewer = AIInterviewer()
        
        # Store the AI interviewer instance for this interview
        ai_interviewers[interview_id] = ai_interviewer
        
        # Read the file contents immediately to avoid issues with closed file handles
        jd_content = ""
        cv_content = ""
        
        # Process job description
        jd_file = interview.job_description.file
        jd_extension = os.path.splitext(jd_file.name)[1].lower()
        jd_temp = tempfile.NamedTemporaryFile(delete=False, suffix=jd_extension)
        
        for chunk in jd_file.chunks():
            jd_temp.write(chunk)
        jd_temp.close()
        
        # Process CV/resume
        cv_file = interview.resume.file
        cv_extension = os.path.splitext(cv_file.name)[1].lower()
        cv_temp = tempfile.NamedTemporaryFile(delete=False, suffix=cv_extension)
        
        for chunk in cv_file.chunks():
            cv_temp.write(chunk)
        cv_temp.close()
        
        # Load the content from the temp files
        try:
            jd_content = ai_interviewer.load_file_content(jd_temp.name)
            cv_content = ai_interviewer.load_file_content(cv_temp.name)
            
            # Store the content in the AI interviewer
            ai_interviewer.job_description = jd_content
            ai_interviewer.cv = cv_content
            
            # Clean up temp files
            os.unlink(jd_temp.name)
            os.unlink(cv_temp.name)
        except Exception as e:
            # Clean up in case of error
            if os.path.exists(jd_temp.name):
                os.unlink(jd_temp.name)
            if os.path.exists(cv_temp.name):
                os.unlink(cv_temp.name)
            raise e
        
        # Generate questions in a background thread to avoid blocking the response
        def generate_questions_thread():
            try:
                questions = ai_interviewer.generate_questions()
                
                # Store questions in the database
                for q in questions:
                    InterviewQuestion.objects.create(
                        interview=interview,
                        question_text=q['question'],
                        is_technical=(q['type'] == 'technical')
                    )
            except Exception as e:
                logger.error(f"Error generating questions: {e}")
        
        # Start the thread
        threading.Thread(target=generate_questions_thread, daemon=True).start()
        
        # Update interview status
        interview.status = 'in_progress'
        interview.save()
        
        return JsonResponse({
            'success': True,
            'message': 'AI interview started successfully',
            'interview_id': interview_id
        })
    except Exception as e:
        logger.error(f"Error starting AI interview: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error starting interview: {str(e)}'
        })

@login_required
def ai_interview_questions(request, interview_id):
    """Get the questions for an AI interview."""
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    # Get questions from the database
    questions = interview.questions.all()
    
    if not questions:
        return JsonResponse({
            'success': False,
            'message': 'Questions are still being generated. Please try again in a moment.'
        })
    
    # Format questions for the frontend
    formatted_questions = []
    for q in questions:
        formatted_questions.append({
            'id': q.id,
            'type': 'technical' if q.is_technical else 'non-technical',
            'question': q.question_text,
            'answered': bool(q.answer_text)
        })
    
    return JsonResponse({
        'success': True,
        'questions': formatted_questions
    })

@login_required
@csrf_exempt  # For simplicity in this example - consider using proper CSRF protection in production
def ai_interview_answer(request, interview_id, question_id):
    """Submit an answer to a question in the AI interview."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    question = get_object_or_404(InterviewQuestion, id=question_id, interview=interview)
    
    try:
        data = json.loads(request.body)
        answer = data.get('answer', '')
        
        # Save the answer
        question.answer_text = answer
        question.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Answer submitted successfully'
        })
    except Exception as e:
        logger.error(f"Error submitting answer: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error submitting answer: {str(e)}'
        }, status=400)

@login_required
def ai_interview_complete(request, interview_id):
    """Complete the AI interview and generate a report."""
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    # Check if all questions have been answered
    questions = interview.questions.all()
    unanswered_questions = questions.filter(answer_text='')
    
    if unanswered_questions.exists():
        return JsonResponse({
            'success': False,
            'message': f'There are {unanswered_questions.count()} unanswered questions. Please answer all questions before completing the interview.'
        })
    
    # Get the AI interviewer instance for this interview
    ai_interviewer = ai_interviewers.get(interview_id)
    
    if not ai_interviewer:
        # Create a new instance if not found
        ai_interviewer = AIInterviewer()
        
        # Read the file contents immediately to avoid issues with closed file handles
        jd_content = ""
        cv_content = ""
        
        # Process job description
        jd_file = interview.job_description.file
        jd_extension = os.path.splitext(jd_file.name)[1].lower()
        jd_temp = tempfile.NamedTemporaryFile(delete=False, suffix=jd_extension)
        
        for chunk in jd_file.chunks():
            jd_temp.write(chunk)
        jd_temp.close()
        
        # Process CV/resume
        cv_file = interview.resume.file
        cv_extension = os.path.splitext(cv_file.name)[1].lower()
        cv_temp = tempfile.NamedTemporaryFile(delete=False, suffix=cv_extension)
        
        for chunk in cv_file.chunks():
            cv_temp.write(chunk)
        cv_temp.close()
        
        # Load the content from the temp files
        try:
            jd_content = ai_interviewer.load_file_content(jd_temp.name)
            cv_content = ai_interviewer.load_file_content(cv_temp.name)
            
            # Store the content in the AI interviewer
            ai_interviewer.job_description = jd_content
            ai_interviewer.cv = cv_content
            
            # Clean up temp files
            os.unlink(jd_temp.name)
            os.unlink(cv_temp.name)
        except Exception as e:
            # Clean up in case of error
            if os.path.exists(jd_temp.name):
                os.unlink(jd_temp.name)
            if os.path.exists(cv_temp.name):
                os.unlink(cv_temp.name)
            raise e
    
    # Prepare interview data for report generation
    interview_data = []
    for q in questions:
        interview_data.append({
            'question_number': q.id,
            'question_data': {
                'id': q.id,
                'type': 'technical' if q.is_technical else 'non-technical',
                'question': q.question_text
            },
            'answer': q.answer_text
        })
    
    # Generate report in a background thread
    def generate_report_thread():
        try:
            # Prepare interview data with more context
            enhanced_interview_data = []
            
            # Get all questions with their answers
            for q in questions:
                # Determine if the question is technical
                is_technical = q.is_technical
                
                # Create enhanced question data with more context
                enhanced_interview_data.append({
                    'question_number': q.id,
                    'question_data': {
                        'id': q.id,
                        'type': 'technical' if is_technical else 'non-technical',
                        'question': q.question_text,
                        # Add additional context if available
                        'context': f"This question assesses the candidate's knowledge of {'technical skills' if is_technical else 'soft skills'}"
                    },
                    'answer': q.answer_text or "No answer provided."
                })
            
            # Create a comprehensive behavioral analysis summary
            behavioral_summary = generate_behavioral_analysis_summary(interview_id)
            
            # Generate the report with enhanced data and behavioral analysis
            report = ai_interviewer.generate_report(enhanced_interview_data, behavioral_summary)
            
            # Clean report text to prevent Unicode issues
            try:
                clean_report = report.encode('utf-8', 'ignore').decode('utf-8') if report else "Report generation failed."
            except Exception as e:
                logger.error(f"Unicode encoding error in report: {e}")
                clean_report = "Report generation encountered encoding issues. Please try again."
                report = clean_report
            
            # Extract scores from the report using enhanced analysis
            technical_score = 0
            non_technical_score = 0
            overall_score = 0
            
            # Get behavioral analysis data
            behavioral_data = interview_behavioral_data.get(interview_id, {})
            emotion_data = behavioral_data.get('emotions', [])
            posture_data = behavioral_data.get('postures', [])
            
            # Calculate behavioral scores
            confidence_score = calculate_confidence_score(emotion_data, posture_data)
            engagement_score = calculate_engagement_score(emotion_data, posture_data)
            communication_score = calculate_communication_score(emotion_data, posture_data)
            body_language_score = calculate_body_language_score(emotion_data, posture_data)
            eye_contact_score = calculate_eye_contact_score(emotion_data, posture_data)
            speaking_pace_score = 75  # Default score, can be enhanced with actual speech analysis
            
            # Try to extract scores using regex
            import re
            tech_match = re.search(r'Technical Average[^\d]*(\d+(\.\d+)?)', report)
            if tech_match:
                technical_score = float(tech_match.group(1)) * 10  # Convert from 0-10 to 0-100
            
            # Look for non-technical score
            non_tech_match = re.search(r'Non-Technical Average[^\d]*(\d+(\.\d+)?)', report)
            if non_tech_match:
                non_technical_score = float(non_tech_match.group(1)) * 10  # Convert from 0-10 to 0-100
            
            # Look for final score
            final_match = re.search(r'Final Score:?\s*(\d+(\.\d+)?)', report)
            if final_match:
                overall_score = float(final_match.group(1))
            
            # Calculate scores based on actual LLM analysis only
            if technical_score == 0 and non_technical_score == 0 and overall_score == 0:
                logger.warning("No scores found in LLM report - this indicates the analysis failed")
                # Only set minimal fallback scores if absolutely no analysis was possible
                technical_score = 50  # Neutral score indicating analysis unavailable
                non_technical_score = 50
                overall_score = 50
            
            # Update individual question scores based on the report
            try:
                # Extract individual scores from the report
                score_pattern = r'Question:\s*(.*?)\nAnswer:.*?Score:\s*(\d+(\.\d+)?)/10'
                question_scores = re.findall(score_pattern, report, re.DOTALL)
                
                if question_scores:
                    for q_text, score_str, _ in question_scores:
                        # Find the matching question in the database
                        q_text_trimmed = q_text.strip()
                        matching_questions = [q for q in questions if q.question_text.strip() in q_text_trimmed or q_text_trimmed in q.question_text.strip()]
                        
                        if matching_questions:
                            q = matching_questions[0]
                            # Convert score from 0-10 to 0-100
                            q.score = float(score_str) * 10
                            q.save()
                            logger.info(f"Updated score for question {q.id}: {q.score}")
            except Exception as e:
                logger.error(f"Error updating individual question scores: {e}")
            
            # Create or update the interview result with enhanced data
            result, created = InterviewResult.objects.update_or_create(
                interview=interview,
                defaults={
                    'technical_score': int(technical_score),
                    'non_technical_score': int(non_technical_score),
                    'overall_score': int(overall_score),
                    'feedback': report,
                    'confidence_score': confidence_score,
                    'communication_score': communication_score,
                    'body_language_score': body_language_score,
                    'eye_contact_score': eye_contact_score,
                    'speaking_pace_score': speaking_pace_score
                }
            )
            
            # Store behavioral analysis data in the result
            if emotion_data or posture_data:
                from collections import Counter
                result.set_emotion_analysis({
                    'emotions': emotion_data,
                    'emotion_distribution': dict(Counter(emotion_data)) if emotion_data else {},
                    'dominant_emotion': max(set(emotion_data), key=emotion_data.count) if emotion_data else 'Unknown'
                })
                
                result.set_posture_analysis({
                    'postures': posture_data,
                    'posture_distribution': dict(Counter(posture_data)) if posture_data else {},
                    'dominant_posture': max(set(posture_data), key=posture_data.count) if posture_data else 'Unknown'
                })
                
                result.save()
            
            # Generate daily progress data for visualization
            daily_data = {}
            start_date = timezone.now().date() - timezone.timedelta(days=6)
            
            # Create a progression that ends at the overall score
            for i in range(7):
                current_date = start_date + timezone.timedelta(days=i)
                date_str = current_date.strftime('%d-%b-%y')
                
                # Start low and progress toward the final score
                progress_factor = i / 6.0  # 0 to 1
                base_score = 30 + (overall_score - 30) * progress_factor
                variation = random.randint(-5, 5)
                score = max(0, min(100, base_score + variation))
                
                daily_data[date_str] = score
            
            # Save daily progress data
            result.set_daily_progress(daily_data)
            result.save()
            
            # Update interview status
            interview.status = 'completed'
            interview.save()
            
            logger.info(f"Report generated for interview {interview_id} with scores: Tech={technical_score}, Non-Tech={non_technical_score}, Overall={overall_score}")
        except Exception as e:
            logger.error(f"Error generating report: {e}")
        finally:
            # Clean up
            if interview_id in ai_interviewers:
                del ai_interviewers[interview_id]
    
    # Start the thread
    threading.Thread(target=generate_report_thread, daemon=True).start()
    
    return JsonResponse({
        'success': True,
        'message': 'Interview completed successfully. Your report is being generated and will be available soon.',
        'redirect_url': f'/reports/'
    })

@login_required
def ai_interview_status(request, interview_id):
    """Get the status of an AI interview."""
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    # Get questions and count answered ones
    questions = interview.questions.all()
    total_questions = questions.count()
    answered_questions = questions.exclude(answer_text='').count()
    
    # Check if report is available
    report_available = hasattr(interview, 'result')
    
    return JsonResponse({
        'success': True,
        'status': interview.status,
        'total_questions': total_questions,
        'answered_questions': answered_questions,
        'report_available': report_available
    })

@login_required
def start_voice_interview(request, interview_id):
    """Start a voice-based AI interview."""
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    try:
        # Get or create AI interviewer instance
        ai_interviewer = ai_interviewers.get(interview_id)
        if not ai_interviewer:
            ai_interviewer = AIInterviewer()
            ai_interviewers[interview_id] = ai_interviewer
            
            # Load job description and CV
            jd_content = ai_interviewer.load_job_description_from_django_file(interview.job_description.file)
            cv_content = ai_interviewer.load_cv_from_django_file(interview.resume.file)
            
            ai_interviewer.job_description = jd_content
            ai_interviewer.cv = cv_content
        
        # Initialize voice interaction
        ai_interviewer.voice_manager = VoiceInteractionManager(use_gtts=True, use_whisper=True)
        
        # Update interview status
        interview.status = 'in_progress'
        interview.save()
        
        # Start the interview in a background thread
        def interview_thread():
            try:
                # Generate questions
                questions = ai_interviewer.generate_questions()
                
                # Store questions in the database
                for q in questions:
                    question = InterviewQuestion.objects.create(
                        interview=interview,
                        question_text=q['question'],
                        is_technical=(q['type'] == 'technical')
                    )
                    
                    # Notify frontend about new question
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"interview_{interview_id}",
                        {
                            "type": "interview.message",
                            "message": {
                                "type": "question",
                                "question": q['question'],
                                "question_id": question.id
                            }
                        }
                    )
                    
                    # Speak the question
                    ai_interviewer.voice_manager.speak(q['question'])
                    
                    # Wait for user to start speaking
                    while True:
                        # Check if user has started speaking
                        message = async_to_sync(channel_layer.group_receive)(
                            f"interview_{interview_id}",
                            {"type": "start_listening"}
                        )
                        if message.get("type") == "start_listening":
                            break
                    
                    # Listen for answer
                    answer = ai_interviewer.voice_manager.listen_with_retry()
                    
                    # Save the answer
                    question.answer_text = answer
                    question.save()
                    
                    # Notify frontend about the answer
                    async_to_sync(channel_layer.group_send)(
                        f"interview_{interview_id}",
                        {
                            "type": "interview.message",
                            "message": {
                                "type": "answer",
                                "question_id": question.id,
                                "answer": answer
                            }
                        }
                    )
                
                # Interview complete
                interview.status = 'completed'
                interview.save()
                
                # Generate and save report
                interview_data = []
                for q in interview.questions.all():
                    interview_data.append({
                        'question_number': q.id,
                        'question_data': {
                            'id': q.id,
                            'type': 'technical' if q.is_technical else 'non-technical',
                            'question': q.question_text
                        },
                        'answer': q.answer_text
                    })
                
                report = ai_interviewer.generate_report(interview_data)
                InterviewResult.objects.create(
                    interview=interview,
                    report=report
                )
                
                # Notify frontend about completion
                async_to_sync(channel_layer.group_send)(
                    f"interview_{interview_id}",
                    {
                        "type": "interview.message",
                        "message": {
                            "type": "complete",
                            "message": "Interview completed successfully"
                        }
                    }
                )
                
            except Exception as e:
                logger.error(f"Error in interview thread: {e}")
                async_to_sync(channel_layer.group_send)(
                    f"interview_{interview_id}",
                    {
                        "type": "interview.message",
                        "message": {
                            "type": "error",
                            "error": str(e)
                        }
                    }
                )
        
        # Start the interview thread
        threading.Thread(target=interview_thread, daemon=True).start()
        
        return JsonResponse({
            'success': True,
            'message': 'Voice interview started successfully'
        })
        
    except Exception as e:
        logger.error(f"Error starting voice interview: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error starting interview: {str(e)}'
        })

@login_required
def pause_voice_interview(request, interview_id):
    """Pause a voice-based interview session."""
    ai_interviewer = ai_interviewers.get(interview_id)
    
    if not ai_interviewer:
        return JsonResponse({
            'success': False,
            'message': 'No active interview found'
        })
    
    success = ai_interviewer.pause_interview()
    
    return JsonResponse({
        'success': success,
        'message': 'Interview paused' if success else 'Failed to pause interview'
    })

@login_required
def resume_voice_interview(request, interview_id):
    """Resume a paused voice-based interview session."""
    ai_interviewer = ai_interviewers.get(interview_id)
    
    if not ai_interviewer:
        return JsonResponse({
            'success': False,
            'message': 'No active interview found'
        })
    
    success = ai_interviewer.resume_interview()
    
    return JsonResponse({
        'success': success,
        'message': 'Interview resumed' if success else 'Failed to resume interview'
    })

@login_required
def stop_voice_interview(request, interview_id):
    """Stop a voice-based interview session."""
    ai_interviewer = ai_interviewers.get(interview_id)
    
    if not ai_interviewer:
        return JsonResponse({
            'success': False,
            'message': 'No active interview found'
        })
    
    success = ai_interviewer.stop_interview()
    
    return JsonResponse({
        'success': success,
        'message': 'Interview stopped' if success else 'Failed to stop interview'
    })

@csrf_exempt
@login_required
def analyze_snapshot(request):
    """
    Receives a base64-encoded image and toggle states, runs sentiment and posture analysis, and returns the results as JSON.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    try:
        data = json.loads(request.body)
        image_b64 = data.get('image')
        enable_emotion = data.get('enable_emotion', True)
        enable_posture = data.get('enable_posture', True)
        interview_id = data.get('interview_id')  # Get interview ID to store behavioral data
        
        if not image_b64:
            return JsonResponse({'success': False, 'error': 'No image provided'})
        
        # Decode base64 image
        image_data = base64.b64decode(image_b64.split(',')[-1])
        image = Image.open(BytesIO(image_data)).convert('RGB')
        frame = np.array(image)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # Run analysis
        result = {}
        emotion = None
        posture = None
        
        if enable_emotion:
            detector = EfficientEmotionDetector()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_box = detector.detect_face(gray)
            if face_box is not None:
                eyes = detector.detect_eyes(gray, face_box)
                mouth = detector.detect_mouth(gray, face_box)
                features = detector.calculate_simple_features(gray, face_box, eyes, mouth)
                emotion, _ = detector.classify_emotion_simple(features)
                result['emotion'] = emotion
            else:
                result['emotion'] = 'No Face'
                emotion = 'No Face'
        
        if enable_posture:
            analyzer = MediaPipePostureAnalyzer()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = analyzer.pose.process(rgb)
            posture = 'No Person'
            if results.pose_landmarks:
                posture, _ = analyzer.analyze(results.pose_landmarks.landmark)
            result['posture'] = posture
        
        # Store behavioral data for the interview if interview_id is provided
        if interview_id and (emotion or posture):
            try:
                # Initialize behavioral data if not exists
                if interview_id not in interview_behavioral_data:
                    interview_behavioral_data[interview_id] = {
                        'emotions': [],
                        'postures': [],
                        'timestamps': []
                    }
                
                # Store the data
                if emotion and emotion != 'No Face':
                    interview_behavioral_data[interview_id]['emotions'].append(emotion)
                if posture and posture != 'No Person':
                    interview_behavioral_data[interview_id]['postures'].append(posture)
                
                # Add timestamp
                from datetime import datetime
                interview_behavioral_data[interview_id]['timestamps'].append(datetime.now().isoformat())
                
                # Limit the data to last 1000 entries to prevent memory issues
                for key in ['emotions', 'postures', 'timestamps']:
                    if len(interview_behavioral_data[interview_id][key]) > 1000:
                        interview_behavioral_data[interview_id][key] = interview_behavioral_data[interview_id][key][-1000:]
                        
            except Exception as e:
                logger.error(f"Error storing behavioral data: {e}")
        
        return JsonResponse({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Error in analyze_snapshot: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

def run_interview_monitor_and_get_summary():
    """
    Launches the OpenCV-based interview monitor, returns the session summary for report integration.
    """
    monitor = InterviewMonitor()
    summary = monitor.run()  # This will block until the user quits the window
    return summary

# Example integration in ai_interview_complete (add after report generation):
# summary = run_interview_monitor_and_get_summary()
# Pass summary['summary_text'] to the LLM (AIInterviewer) as part of the report prompt.
