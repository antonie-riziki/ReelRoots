from django.shortcuts import render

# Create your views here.
def home(request):
    return render(request, 'index.html')


def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')


def archive_details(request):
    return render(request, 'archive_details.html')


def chat(request):
    return render(request, 'caht.html')


def explore(request):
    return render(request, 'explore.html')


def new_upload(request):
    return render(request, 'new_upload.html')


def reels(request):
    return render(request, 'reels.html')


def story_mode(request):
    return render(request, 'story_mode.html')


def user_profile(request):
    return render(request, 'user_profile.html')