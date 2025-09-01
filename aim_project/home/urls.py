from django.urls import path
from . import views
from . import ai_interview_views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload-job-description/', views.upload_job_description, name='upload_jd'),
    path('upload-resume/', views.upload_resume, name='upload_resume'),
    path('schedule-interview/', views.schedule_interview, name='schedule_interview'),
    path('interview/<int:interview_id>/', views.interview_detail, name='interview_detail'),
    path('reports/', views.reports, name='reports'),
    path('settings/', views.settings, name='settings'),
    path('faqs/', views.faqs, name='faqs'),
    path('api/report-data/<int:result_id>/', views.get_report_data, name='get_report_data'),
    path('download-report/<int:interview_id>/', views.download_report, name='download_report'),
    # For testing only - would be replaced by actual interview process
    path('mock-interview-result/<int:interview_id>/', views.mock_interview_result, name='mock_interview_result'),
    # Settings update paths
    path('settings/update-profile-picture/', views.update_profile_picture, name='update_profile_picture'),
    path('settings/update-username/', views.update_username, name='update_username'),
    path('settings/update-password/', views.update_password, name='update_password'),
    path('interview-session/', views.interview_session, name='interview_session'),
    path('interview-session/<int:interview_id>/', views.interview_session, name='interview_session_with_id'),
    path('interview-complete/', views.interview_complete, name='interview_complete'),
    
    # AI Interviewer API endpoints
    path('api/ai-interview/start/<int:interview_id>/', ai_interview_views.ai_interview_start, name='ai_interview_start'),
    path('api/ai-interview/questions/<int:interview_id>/', ai_interview_views.ai_interview_questions, name='ai_interview_questions'),
    path('api/ai-interview/answer/<int:interview_id>/<int:question_id>/', ai_interview_views.ai_interview_answer, name='ai_interview_answer'),
    path('api/ai-interview/complete/<int:interview_id>/', ai_interview_views.ai_interview_complete, name='ai_interview_complete'),
    path('api/ai-interview/status/<int:interview_id>/', ai_interview_views.ai_interview_status, name='ai_interview_status'),
    path('api/analyze-snapshot/', ai_interview_views.analyze_snapshot, name='analyze_snapshot'),
]
