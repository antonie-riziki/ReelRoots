from django.urls import path, include
from . import views



urlpatterns = [
    path('', views.home, name="home"),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('archive_details/', views.archive_details, name='archive_details'),
    path('chat/', views.chat, name='chat'),
    path('explore/', views.explore, name='explore'),
    path('upload/', views.new_upload, name='upload'),
    path('reels/', views.reels, name='reels'),
    # path("api/reels/", views.reels_api, name="reels_api"),
    path('story_mode/', views.story_mode, name='story_mode'),
    path('user_profile/', views.user_profile, name='user_profile'),
    path('animation/', views.animation, name='animation')

]