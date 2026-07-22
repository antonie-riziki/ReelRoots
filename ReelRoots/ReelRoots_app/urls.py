from django.urls import path, include
from . import views

from django.conf import settings
from django.conf.urls.static import static
from . import auth_views
from . import reel_views




urlpatterns = [
    path('', views.landing_page, name='landing-page'),
    path('auth', auth_views.auth_page, name='auth'),
    path('auth/verify-phone/', auth_views.verify_phone, name='verify-phone'),
    path('auth/verify-phone/resend/', auth_views.resend_phone_code, name='resend-phone-code'),
    path('auth/forgot-password/', auth_views.forgot_password, name='forgot-password'),
    path('auth/reset-password/', auth_views.reset_password, name='reset-password'),
    path('auth/logout/', auth_views.logout_view, name='logout'),
    path('home', views.home, name="home"),
    path('admin-dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path("archive/<slug:slug>/", views.archive_details, name="archive-details"),
    path('chat/', views.chat, name='chat'),
    path('explore/', views.explore, name='explore'),
    path('api/archives/create/', views.create_archive, name='create_archive'),
    path('upload/', views.new_upload, name='upload'),
    path('reels/', views.reels, name='reels'),
    path('api/v1/reels/<uuid:reel_id>/interaction/', reel_views.reel_interaction, name='reel-interaction'),
    path('api/v1/reels/<uuid:reel_id>/comments/', reel_views.reel_comments, name='reel-comments'),
    # path("api/reels/", views.reels_api, name="reels_api"),
    path('story-mode/', views.story_mode, name='story-mode'),
    path('user-profile/', views.user_profile, name='user-profile'),
    path('onboarding/', auth_views.onboarding, name='onboarding'),
    path('settings/profile/', auth_views.profile_settings, name='profile-settings'),
    path('api/v1/personalization/events/', auth_views.personalization_event, name='personalization-event'),
    path('animation/', views.animation, name='animation'),
    path('chatbot-response/', views.chatbot_response, name='chatbot-response')

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
