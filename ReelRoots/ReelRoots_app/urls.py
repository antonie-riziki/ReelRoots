from django.urls import path, include
from . import views

from django.conf import settings
from django.conf.urls.static import static




urlpatterns = [
    path('', views.landing_page, name='landing-page'),
    path('auth', views.auth, name='auth'),
    path('home', views.home, name="home"),
    path('admin-dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path("archive/<slug:slug>/", views.archive_details, name="archive-details"),
    path('chat/', views.chat, name='chat'),
    path('explore/', views.explore, name='explore'),
    path('api/archives/create/', views.create_archive, name='create_archive'),
    path('upload/', views.new_upload, name='upload'),
    path('reels/', views.reels, name='reels'),
    # path("api/reels/", views.reels_api, name="reels_api"),
    path('story-mode/', views.story_mode, name='story-mode'),
    path('user-profile/', views.user_profile, name='user-profile'),
    path('animation/', views.animation, name='animation'),
    path('chatbot-response/', views.chatbot_response, name='chatbot-response')

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)