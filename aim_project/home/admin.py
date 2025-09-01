from django.contrib import admin
from .models import ContactSubmission, JobDescription, Resume, Interview, InterviewResult, InterviewQuestion, UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'avatar')
    search_fields = ('user__username', 'user__email')

@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at')
    search_fields = ('name', 'email', 'message')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

@admin.register(JobDescription)
class JobDescriptionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'uploaded_at')
    search_fields = ('title', 'user__username')
    list_filter = ('uploaded_at',)
    date_hierarchy = 'uploaded_at'

@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'uploaded_at')
    search_fields = ('title', 'user__username')
    list_filter = ('uploaded_at',)
    date_hierarchy = 'uploaded_at'

@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'scheduled_date', 'status')
    search_fields = ('title', 'user__username')
    list_filter = ('status', 'scheduled_date')
    date_hierarchy = 'scheduled_date'

@admin.register(InterviewResult)
class InterviewResultAdmin(admin.ModelAdmin):
    list_display = ('interview', 'technical_score', 'non_technical_score', 'overall_score', 'created_at')
    search_fields = ('interview__title', 'interview__user__username')
    list_filter = ('created_at',)
    date_hierarchy = 'created_at'

@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(admin.ModelAdmin):
    list_display = ('interview', 'question_text', 'score', 'is_technical')
    search_fields = ('question_text', 'interview__title')
    list_filter = ('is_technical', 'created_at')
    date_hierarchy = 'created_at'
