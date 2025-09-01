from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.utils import timezone
from django.db.models import Avg
from django.template.loader import render_to_string
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
import os
import io
import random
from datetime import timedelta
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from .forms import (
    ContactForm, LoginForm, SignUpForm, 
    JobDescriptionForm, ResumeForm, InterviewScheduleForm,
    ProfilePictureForm, UsernameChangeForm, CustomPasswordChangeForm
)
from .models import JobDescription, Resume, Interview, InterviewResult, InterviewQuestion, UserProfile
from .ai_interviewer import AIInterviewer

def home(request):
    return render(request, 'home/index.html')

def about(request):
    return render(request, 'home/about.html')

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your message has been sent successfully! We will get back to you soon.')
            return redirect('contact')
    else:
        form = ContactForm()
    
    return render(request, 'home/contact.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                
                # Redirect to the page the user was trying to access, or dashboard
                next_page = request.GET.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    
    return render(request, 'home/login.html', {'form': form})

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created successfully! Welcome, {user.username}!')
            return redirect('dashboard')
    else:
        form = SignUpForm()
    
    return render(request, 'home/signup.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')

@login_required
def dashboard(request):
    # Get the latest job description and resume for the user
    latest_jd = JobDescription.objects.filter(user=request.user).order_by('-uploaded_at').first()
    latest_resume = Resume.objects.filter(user=request.user).order_by('-uploaded_at').first()
    
    # Check if both JD and resume are uploaded
    can_start_interview = latest_jd is not None and latest_resume is not None
    
    # Get upcoming interviews
    upcoming_interviews = Interview.objects.filter(
        user=request.user,
        scheduled_date__gte=timezone.now(),
        status='scheduled'
    ).order_by('scheduled_date')
    
    context = {
        'latest_jd': latest_jd,
        'latest_resume': latest_resume,
        'can_start_interview': can_start_interview,
        'upcoming_interviews': upcoming_interviews,
        'current_page': 'dashboard'
    }
    
    return render(request, 'home/dashboard.html', context)

@login_required
def upload_job_description(request):
    if request.method == 'POST':
        form = JobDescriptionForm(request.POST, request.FILES)
        if form.is_valid():
            job_description = form.save(commit=False)
            job_description.user = request.user
            job_description.save()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Job description uploaded successfully!',
                    'jd_id': job_description.id,
                    'jd_title': job_description.title
                })
            
            messages.success(request, 'Job description uploaded successfully!')
            return redirect('dashboard')
    else:
        form = JobDescriptionForm()
    
    return render(request, 'home/upload_jd.html', {'form': form})

@login_required
def upload_resume(request):
    if request.method == 'POST':
        form = ResumeForm(request.POST, request.FILES)
        if form.is_valid():
            resume = form.save(commit=False)
            resume.user = request.user
            resume.save()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Resume uploaded successfully!',
                    'resume_id': resume.id,
                    'resume_title': resume.title
                })
            
            messages.success(request, 'Resume uploaded successfully!')
            return redirect('dashboard')
    else:
        form = ResumeForm()
    
    return render(request, 'home/upload_resume.html', {'form': form})

@login_required
def schedule_interview(request):
    # Get the latest job description and resume
    latest_jd = JobDescription.objects.filter(user=request.user).order_by('-uploaded_at').first()
    latest_resume = Resume.objects.filter(user=request.user).order_by('-uploaded_at').first()
    
    if not latest_jd or not latest_resume:
        messages.error(request, 'Please upload both a job description and a resume before scheduling an interview.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = InterviewScheduleForm(request.POST)
        if form.is_valid():
            interview = form.save(commit=False)
            interview.user = request.user
            interview.job_description = latest_jd
            interview.resume = latest_resume
            interview.title = latest_jd.title  # Use job title as interview title
            interview.save()
            
            messages.success(request, 'Interview scheduled successfully!')
            return redirect('interview_detail', interview_id=interview.id)
    else:
        form = InterviewScheduleForm(initial={'scheduled_date': timezone.now()})
    
    context = {
        'form': form,
        'job_description': latest_jd,
        'resume': latest_resume
    }
    
    return render(request, 'home/schedule_interview.html', context)

@login_required
def interview_detail(request, interview_id):
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    return render(request, 'home/interview_detail.html', {'interview': interview})

@login_required
def reports(request):
    # Get completed interviews
    completed_interviews = Interview.objects.filter(
        user=request.user,
        status='completed'
    ).order_by('-scheduled_date')
    
    # Check if there are any completed interviews with results
    has_interview_data = False
    latest_result = None
    
    try:
        # Try to check for interview results
        has_interview_data = InterviewResult.objects.filter(
            interview__user=request.user
        ).exists()
        
        # Get the most recent interview result for charts
        if has_interview_data:
            latest_result = InterviewResult.objects.filter(
                interview__user=request.user
            ).order_by('-created_at').first()
    except:
        # If the table doesn't exist yet or any other error occurs,
        # assume there's no interview data
        has_interview_data = False
        latest_result = None
    
    context = {
        'completed_interviews': completed_interviews,
        'has_interview_data': has_interview_data,
        'latest_result': latest_result,
        'current_page': 'reports'
    }
    
    return render(request, 'home/reports.html', context)

@login_required
def get_report_data(request, result_id):
    """API endpoint to get report data for charts"""
    result = get_object_or_404(InterviewResult, id=result_id, interview__user=request.user)
    
    # Get daily progress data
    daily_progress = result.get_daily_progress()
    
    # Prepare data for pie chart
    pie_data = {
        'technical': result.technical_score,
        'non_technical': result.non_technical_score
    }
    
    # Get behavioral analysis data
    behavioral_data = {
        'confidence_score': getattr(result, 'confidence_score', 0),
        'communication_score': getattr(result, 'communication_score', 0),
        'body_language_score': getattr(result, 'body_language_score', 0),
        'eye_contact_score': getattr(result, 'eye_contact_score', 0),
        'speaking_pace_score': getattr(result, 'speaking_pace_score', 0)
    }
    
    # Get emotion and posture analysis
    emotion_analysis = result.get_emotion_analysis()
    posture_analysis = result.get_posture_analysis()
    
    return JsonResponse({
        'daily_progress': daily_progress,
        'pie_data': pie_data,
        'technical_score': result.technical_score,
        'non_technical_score': result.non_technical_score,
        'overall_score': result.overall_score,
        'behavioral_data': behavioral_data,
        'emotion_analysis': emotion_analysis,
        'posture_analysis': posture_analysis
    })

@login_required
def download_report(request, interview_id):
    """Generate and download a PDF report for an interview"""
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    try:
        result = interview.result
    except InterviewResult.DoesNotExist:
        messages.error(request, "No results found for this interview.")
        return redirect('reports')
    
    # Create a file-like buffer to receive PDF data
    buffer = io.BytesIO()
    
    # Create the PDF object, using the buffer as its "file"
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Add title
    elements.append(Paragraph(f"Interview Report: {interview.title}", title_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Add date
    elements.append(Paragraph(f"Date: {interview.scheduled_date.strftime('%d-%b-%Y')}", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Add scores
    elements.append(Paragraph("Performance Scores", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Create a table for scores
    data = [
        ["Category", "Score"],
        ["Technical", f"{result.technical_score}%"],
        ["Non-Technical", f"{result.non_technical_score}%"],
        ["Overall", f"{result.overall_score}%"]
    ]
    
    score_table = Table(data, colWidths=[3*inch, 1*inch])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(score_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Add behavioral analysis scores if available
    if hasattr(result, 'confidence_score') and result.confidence_score:
        elements.append(Paragraph("Behavioral Analysis", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        behavioral_data = [
            ["Metric", "Score"],
            ["Confidence", f"{result.confidence_score}%"],
            ["Communication", f"{result.communication_score}%"],
            ["Body Language", f"{result.body_language_score}%"],
            ["Eye Contact", f"{result.eye_contact_score}%"],
            ["Speaking Pace", f"{result.speaking_pace_score}%"]
        ]
        
        behavioral_table = Table(behavioral_data, colWidths=[3*inch, 1*inch])
        behavioral_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(behavioral_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Add emotion and posture analysis if available
        emotion_analysis = result.get_emotion_analysis()
        posture_analysis = result.get_posture_analysis()
        
        if emotion_analysis or posture_analysis:
            elements.append(Paragraph("Emotion and Posture Analysis", subtitle_style))
            elements.append(Spacer(1, 0.1*inch))
            
            if emotion_analysis:
                dominant_emotion = emotion_analysis.get('dominant_emotion', 'Unknown')
                emotion_dist = emotion_analysis.get('emotion_distribution', {})
                elements.append(Paragraph(f"Dominant Emotion: {dominant_emotion}", normal_style))
                
                if emotion_dist:
                    emotion_text = ", ".join([f"{emotion}: {count}" for emotion, count in emotion_dist.items()])
                    elements.append(Paragraph(f"Emotion Distribution: {emotion_text}", normal_style))
            
            if posture_analysis:
                dominant_posture = posture_analysis.get('dominant_posture', 'Unknown')
                posture_dist = posture_analysis.get('posture_distribution', {})
                elements.append(Paragraph(f"Dominant Posture: {dominant_posture}", normal_style))
                
                if posture_dist:
                    posture_text = ", ".join([f"{posture}: {count}" for posture, count in posture_dist.items()])
                    elements.append(Paragraph(f"Posture Distribution: {posture_text}", normal_style))
            
            elements.append(Spacer(1, 0.5*inch))
    
    # Add feedback
    elements.append(Paragraph("Feedback", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    # Fix Unicode handling for feedback text
    feedback_text = result.feedback if result.feedback else "No feedback provided."
    # Clean text to prevent Unicode issues
    clean_feedback = feedback_text.encode('ascii', 'ignore').decode('ascii') if feedback_text else "No feedback provided."
    elements.append(Paragraph(clean_feedback, normal_style))
    elements.append(Spacer(1, 0.5*inch))
    
    # Add questions and answers
    elements.append(Paragraph("Questions and Answers", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    questions = interview.questions.all()
    if questions:
        for i, q in enumerate(questions, 1):
            # Clean Unicode characters to prevent encoding issues
            clean_question = q.question_text.encode('ascii', 'ignore').decode('ascii') if q.question_text else "Question not available"
            clean_answer = q.answer_text.encode('ascii', 'ignore').decode('ascii') if q.answer_text else "No answer provided"
            clean_feedback = q.feedback.encode('ascii', 'ignore').decode('ascii') if q.feedback else "No feedback"
            
            elements.append(Paragraph(f"Q{i}: {clean_question}", styles['Heading4']))
            elements.append(Paragraph(f"Answer: {clean_answer}", normal_style))
            elements.append(Paragraph(f"Score: {q.score}%", normal_style))
            elements.append(Paragraph(f"Feedback: {clean_feedback}", normal_style))
            elements.append(Spacer(1, 0.2*inch))
    else:
        elements.append(Paragraph("No questions recorded for this interview.", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create the HTTP response with PDF
    response = HttpResponse(pdf, content_type='application/pdf')
    # Fix Unicode encoding issue by using ASCII-safe filename
    safe_filename = f'interview_report_{interview_id}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
    
    return response

@login_required
def settings(request):
    profile_picture_form = ProfilePictureForm(instance=request.user.profile)
    username_form = UsernameChangeForm(user=request.user)
    password_form = CustomPasswordChangeForm(request.user)
    
    context = {
        'profile_picture_form': profile_picture_form,
        'username_form': username_form,
        'password_form': password_form,
        'current_page': 'settings'
    }
    return render(request, 'home/settings.html', context)

@login_required
def update_profile_picture(request):
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile picture updated successfully!')
            return redirect('settings')
        else:
            messages.error(request, 'Error updating profile picture. Please try again.')
    
    return redirect('settings')

@login_required
def update_username(request):
    if request.method == 'POST':
        form = UsernameChangeForm(request.user, request.POST)
        if form.is_valid():
            new_username = form.cleaned_data.get('new_username')
            request.user.username = new_username
            request.user.save()
            messages.success(request, 'Username updated successfully!')
            return redirect('settings')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    
    return redirect('settings')

@login_required
def update_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update the session to prevent the user from being logged out
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated successfully!')
            return redirect('settings')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    
    return redirect('settings')

@login_required
def mock_interview_result(request, interview_id):
    """
    Create mock interview results for testing the reports page
    This would be replaced by actual interview processing in production
    """
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    # Check if result already exists
    if hasattr(interview, 'result'):
        messages.info(request, "This interview already has results.")
        return redirect('reports')
    
    # Generate random scores
    technical_score = random.randint(30, 95)
    non_technical_score = random.randint(30, 95)
    overall_score = (technical_score + non_technical_score) // 2
    
    # Create result
    result = InterviewResult.objects.create(
        interview=interview,
        technical_score=technical_score,
        non_technical_score=non_technical_score,
        overall_score=overall_score,
        feedback="This is automated feedback for your interview performance. You did well in some areas but need improvement in others."
    )
    
    # Generate daily progress data (last 14 days)
    daily_data = {}
    start_date = timezone.now().date() - timedelta(days=13)
    
    # Start with a base score and vary it
    base_score = 20
    scores = []
    
    for i in range(14):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime('%d-%b-%y')
        
        # Create a somewhat realistic progression
        if i < 3:
            # First few days - low scores
            score = base_score + random.randint(-10, 10)
        elif i < 7:
            # Middle days - improving
            score = base_score + 30 + random.randint(-10, 20)
        elif i < 10:
            # Later days - plateau or slight dip
            score = base_score + 50 + random.randint(-15, 5)
        else:
            # Final days - improvement to final score
            score = base_score + 40 + random.randint(0, 40)
        
        # Ensure score is between 0 and 100
        score = max(0, min(score, 100))
        scores.append(score)
        daily_data[date_str] = score
    
    # Save daily progress data
    result.set_daily_progress(daily_data)
    result.save()
    
    # Create some mock questions and answers
    questions = [
        "Tell me about yourself and your experience.",
        "What are your strengths and weaknesses?",
        "Why do you want to work for this company?",
        "Describe a challenging situation at work and how you handled it.",
        "Where do you see yourself in 5 years?"
    ]
    
    for q_text in questions:
        is_technical = random.choice([True, False])
        score = random.randint(30, 95)
        
        InterviewQuestion.objects.create(
            interview=interview,
            question_text=q_text,
            answer_text="This is a sample answer to the question.",
            score=score,
            feedback="Your answer was good but could be improved by providing more specific examples.",
            is_technical=is_technical
        )
    
    # Update interview status
    interview.status = 'completed'
    interview.save()
    
    # Note: Behavioral data should come from actual camera analysis during interview
    # This mock function now only creates basic interview structure without static behavioral data
    # Real behavioral analysis will be populated when actual interviews are conducted
    
    messages.success(request, "Mock interview structure created. Real behavioral analysis will be populated during actual interviews.")
    return redirect('reports')

def faqs(request):
    return render(request, 'home/faqs.html')

@login_required
def interview_session(request, interview_id=None):
    """
    Render the interview session page.
    If interview_id is provided, it will load that specific interview.
    Otherwise, it will create a new interview session.
    """
    # If interview_id is provided, get that interview
    if interview_id:
        interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    else:
        # Get the latest job description and resume
        latest_jd = JobDescription.objects.filter(user=request.user).order_by('-uploaded_at').first()
        latest_resume = Resume.objects.filter(user=request.user).order_by('-uploaded_at').first()
        
        if not latest_jd or not latest_resume:
            messages.error(request, 'Please upload both a job description and a resume before starting an interview.')
            return redirect('dashboard')
        
        # Create a new interview
        interview = Interview.objects.create(
            user=request.user,
            job_description=latest_jd,
            resume=latest_resume,
            title=f"Interview for {latest_jd.title}",
            scheduled_date=timezone.now(),
            status='in_progress'
        )
    
    # Render the standalone interview template
    return render(request, 'home/interview.html', {'interview': interview})

@login_required
def get_interview_questions(request, interview_id):
    """API endpoint to get AI-generated interview questions."""
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    # Check if questions already exist for this interview
    existing_questions = InterviewQuestion.objects.filter(interview=interview)
    if existing_questions.exists():
        # Return existing questions
        questions_data = []
        for q in existing_questions:
            questions_data.append({
                'id': q.id,
                'type': 'technical' if q.is_technical else 'non-technical',
                'question': q.question_text,
                'follow_up_questions': []  # We could store these in the future
            })
        return JsonResponse({'questions': questions_data})
    
    # Initialize AI Interviewer
    ai_interviewer = AIInterviewer()
    
    # Load job description and CV
    jd_path = interview.job_description.file.path
    cv_path = interview.resume.file.path
    
    try:
        # Load files directly if they exist on disk
        if os.path.exists(jd_path) and os.path.exists(cv_path):
            ai_interviewer.job_description = ai_interviewer.load_file_content(jd_path)
            ai_interviewer.cv = ai_interviewer.load_file_content(cv_path)
        else:
            # Otherwise load from Django file objects
            ai_interviewer.load_job_description_from_django_file(interview.job_description.file)
            ai_interviewer.load_cv_from_django_file(interview.resume.file)
        
        # Generate questions
        questions = ai_interviewer.generate_questions()
        
        # Save questions to database
        for q in questions:
            InterviewQuestion.objects.create(
                interview=interview,
                question_text=q['question'],
                is_technical=(q['type'] == 'technical')
            )
        
        return JsonResponse({'questions': questions})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def submit_interview_answer(request, interview_id):
    """API endpoint to submit an answer to an interview question."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
    
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    try:
        data = json.loads(request.body)
        question_id = data.get('question_id')
        answer = data.get('answer')
        
        if not question_id or not answer:
            return JsonResponse({'error': 'Question ID and answer are required'}, status=400)
        
        # Get the question
        question = get_object_or_404(InterviewQuestion, id=question_id, interview=interview)
        
        # Save the answer
        question.answer_text = answer
        question.save()
        
        return JsonResponse({'success': True})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def complete_interview(request, interview_id):
    """API endpoint to complete an interview and generate a report."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
    
    interview = get_object_or_404(Interview, id=interview_id, user=request.user)
    
    # Get all questions and answers for this interview
    questions = InterviewQuestion.objects.filter(interview=interview)
    
    # Check if all questions have answers
    unanswered = questions.filter(answer_text='')
    if unanswered.exists() and not request.GET.get('force'):
        return JsonResponse({
            'error': 'Not all questions have been answered',
            'unanswered_count': unanswered.count()
        }, status=400)
    
    try:
        # Initialize AI Interviewer
        ai_interviewer = AIInterviewer()
        
        # Load job description and CV
        jd_path = interview.job_description.file.path
        cv_path = interview.resume.file.path
        
        # Load files directly if they exist on disk
        if os.path.exists(jd_path) and os.path.exists(cv_path):
            ai_interviewer.job_description = ai_interviewer.load_file_content(jd_path)
            ai_interviewer.cv = ai_interviewer.load_file_content(cv_path)
        else:
            # Otherwise load from Django file objects
            ai_interviewer.load_job_description_from_django_file(interview.job_description.file)
            ai_interviewer.load_cv_from_django_file(interview.resume.file)
        
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
                'answer': q.answer_text or "No answer provided."
            })
        
        # Generate report
        report = ai_interviewer.generate_report(interview_data)
        
        # Extract scores from the report
        technical_score = 0
        non_technical_score = 0
        overall_score = 0
        
        # Try to extract scores using regex
        import re
        tech_match = re.search(r'Technical Average[^\d]*(\d+(\.\d+)?)', report)
        non_tech_match = re.search(r'Non-Technical Average[^\d]*(\d+(\.\d+)?)', report)
        overall_match = re.search(r'Final Score[^\d]*(\d+(\.\d+)?)', report)
        
        if tech_match:
            technical_score = float(tech_match.group(1)) * 10  # Convert from 0-10 to 0-100
        if non_tech_match:
            non_technical_score = float(non_tech_match.group(1)) * 10  # Convert from 0-10 to 0-100
        if overall_match:
            overall_score = float(overall_match.group(1))
        
        # Create or update the interview result
        result, created = InterviewResult.objects.update_or_create(
            interview=interview,
            defaults={
                'technical_score': technical_score,
                'non_technical_score': non_technical_score,
                'overall_score': overall_score,
                'feedback': report
            }
        )
        
        # Generate daily progress data (last 7 days)
        daily_data = {}
        start_date = timezone.now().date() - timedelta(days=6)
        
        # Create a progression that ends at the overall score
        for i in range(7):
            current_date = start_date + timedelta(days=i)
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
        
        return JsonResponse({
            'success': True,
            'report_id': result.id,
            'technical_score': technical_score,
            'non_technical_score': non_technical_score,
            'overall_score': overall_score
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Add this new view function to handle interview completion
@login_required
def interview_complete(request):
    """
    Handle the completion of an interview session.
    Updates the interview status and creates a placeholder for results.
    """
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        interview_id = request.POST.get('interview_id')
        
        try:
            interview = Interview.objects.get(id=interview_id, user=request.user)
            interview.status = 'completed'
            interview.save()
            
            # Create a placeholder result (in a real app, this would be generated by AI analysis)
            # This is similar to the mock_interview_result function but simplified
            if not hasattr(interview, 'result'):
                technical_score = random.randint(30, 95)
                non_technical_score = random.randint(30, 95)
                overall_score = (technical_score + non_technical_score) // 2
                
                result = InterviewResult.objects.create(
                    interview=interview,
                    technical_score=technical_score,
                    non_technical_score=non_technical_score,
                    overall_score=overall_score,
                    feedback="This is automated feedback for your interview performance."
                )
                
                # Generate simple daily progress data
                daily_data = {}
                start_date = timezone.now().date() - timedelta(days=6)
                for i in range(7):
                    current_date = start_date + timedelta(days=i)
                    date_str = current_date.strftime('%d-%b-%y')
                    score = 30 + (i * 10) + random.randint(-5, 5)
                    score = max(0, min(score, 100))
                    daily_data[date_str] = score
                
                result.set_daily_progress(daily_data)
                result.save()
            
            return JsonResponse({'success': True, 'message': 'Interview completed successfully'})
            
        except Interview.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Interview not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

def faqs(request):
    return render(request, 'home/faqs.html')
