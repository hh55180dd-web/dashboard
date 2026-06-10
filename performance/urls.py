from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('add/', views.add_performance, name='add_performance'),
    path('report/', views.branch_report, name='branch_report'),
    path('employee/<int:employee_id>/', views.employee_profile, name='employee_profile'),
    path('ai-chat/', views.ai_chat_page, name='ai_chat'),
    path('api/ai-chat/', views.ai_chat_api, name='ai_chat_api'),
    
    # مسارات تسجيل الدخول والخروج
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
]