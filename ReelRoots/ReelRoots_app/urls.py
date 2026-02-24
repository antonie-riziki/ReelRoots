from django.urls import path, include
from . import views



urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('auth', views.auth, name='auth'),
    path('home', views.home, name="home"),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('archive-details/', views.archive_details, name='archive_details'),
    path('chat/', views.chat, name='chat'),
    path('explore/', views.explore, name='explore'),
    path('upload/', views.new_upload, name='upload'),
    path('reels/', views.reels, name='reels'),
    # path("api/reels/", views.reels_api, name="reels_api"),
    path('story-mode/', views.story_mode, name='story_mode'),
    path('user-profile/', views.user_profile, name='user_profile'),
    path('animation/', views.animation, name='animation'),
    path('chatbot-response/', views.chatbot_response, name='chatbot-response')

]