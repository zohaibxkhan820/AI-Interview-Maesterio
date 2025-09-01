from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import json

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"

class ContactSubmission(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Contact from {self.name} ({self.email}) on {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contact Submission"
        verbose_name_plural = "Contact Submissions"

class JobDescription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_descriptions')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='job_descriptions/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"JD: {self.title} by {self.user.username}"
    
    class Meta:
        ordering = ['-uploaded_at']

class Resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resumes')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='resumes/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"CV: {self.title} by {self.user.username}"
    
    class Meta:
        ordering = ['-uploaded_at']

class Interview(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interviews')
    job_description = models.ForeignKey(JobDescription, on_delete=models.CASCADE)
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="Interview")
    scheduled_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Interview for {self.user.username} on {self.scheduled_date.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        ordering = ['-scheduled_date']

class InterviewResult(models.Model):
    interview = models.OneToOneField(Interview, on_delete=models.CASCADE, related_name='result')
    technical_score = models.IntegerField(default=0)  # 0-100
    non_technical_score = models.IntegerField(default=0)  # 0-100
    overall_score = models.IntegerField(default=0)  # 0-100
    feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    # Store daily progress data as JSON
    daily_progress_data = models.TextField(blank=True, null=True)
    
    # Enhanced analysis data
    emotion_analysis_data = models.TextField(blank=True, null=True)  # JSON for emotion analysis
    posture_analysis_data = models.TextField(blank=True, null=True)  # JSON for posture analysis
    communication_score = models.IntegerField(default=0)  # 0-100
    confidence_score = models.IntegerField(default=0)  # 0-100
    body_language_score = models.IntegerField(default=0)  # 0-100
    eye_contact_score = models.IntegerField(default=0)  # 0-100
    speaking_pace_score = models.IntegerField(default=0)  # 0-100
    
    def set_daily_progress(self, data):
        """Set daily progress data as JSON"""
        self.daily_progress_data = json.dumps(data)
        
    def get_daily_progress(self):
        """Get daily progress data from JSON"""
        if self.daily_progress_data:
            return json.loads(self.daily_progress_data)
        return {}
    
    def set_emotion_analysis(self, data):
        """Set emotion analysis data as JSON"""
        self.emotion_analysis_data = json.dumps(data)
        
    def get_emotion_analysis(self):
        """Get emotion analysis data from JSON"""
        if self.emotion_analysis_data:
            return json.loads(self.emotion_analysis_data)
        return {}
    
    def set_posture_analysis(self, data):
        """Set posture analysis data as JSON"""
        self.posture_analysis_data = json.dumps(data)
        
    def get_posture_analysis(self):
        """Get posture analysis data from JSON"""
        if self.posture_analysis_data:
            return json.loads(self.posture_analysis_data)
        return {}
    
    def __str__(self):
        return f"Result for {self.interview}"
    
    class Meta:
        ordering = ['-created_at']

class InterviewQuestion(models.Model):
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    answer_text = models.TextField(blank=True)
    score = models.IntegerField(default=0)  # 0-100
    feedback = models.TextField(blank=True)
    is_technical = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Question for {self.interview}: {self.question_text[:50]}..."
    
    class Meta:
        ordering = ['created_at']
