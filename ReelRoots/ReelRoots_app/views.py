from django.shortcuts import render
from django.http import JsonResponse
import requests
import os

from dotenv import load_dotenv

load_dotenv()


YOUTUBE_API_KEY=os.getenv("YOUTUBE_API_KEY")
PEXEL_API_KEY=os.getenv("PEXEL_API_KEY")

# Create your views here.
def home(request):
    headers = {
        "Authorization": PEXEL_API_KEY
    }

    response = requests.get(
        "https://api.pexels.com/videos/search?query=kenya%20culture/&per_page=10",
        headers=headers
    )

    data = response.json()

    reels = []

    for video in data.get("videos", []):
        reels.append({
            "title": "Historical Visual Archive",
            "summary": "Stock archival style footage",
            "video_url": video["video_files"][0]["link"],
            "creator": "Pexels",
            "likes": "—",
            "comments": "—",
            "shares": "—",
            "hashtags": ["Archive", "VisualHistory"]
        })

    context = {"reels": reels[::-1]}
    return render(request, 'index.html', context)


def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')


def archive_details(request):
    return render(request, 'archive_details.html')


def chat(request):
    return render(request, 'chat.html')


def explore(request):
    return render(request, 'explore.html')


def new_upload(request):
    return render(request, 'new_upload.html')


# def reels(request):
#     search_url = "https://www.googleapis.com/youtube/v3/search"

#     search_params = {
#         "part": "snippet",
#         "q": "history documentary",
#         "type": "video",
#         "maxResults": 5,
#         "videoDuration": "short",
#         "key": YOUTUBE_API_KEY
#     }

#     search_response = requests.get(search_url, params=search_params)
#     search_data = search_response.json()

#     video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]

#     # 🔥 Second call to check embeddable status
#     videos_url = "https://www.googleapis.com/youtube/v3/videos"

#     videos_params = {
#         "part": "status",
#         "id": ",".join(video_ids),
#         "key": YOUTUBE_API_KEY
#     }

#     videos_response = requests.get(videos_url, params=videos_params)
#     videos_data = videos_response.json()

#     reels = []

#     for video in videos_data.get("items", []):
#         if video["status"]["embeddable"]:

#             reels.append({
#                 "video_url": f"https://www.youtube.com/embed/{video['id']}?autoplay=1&mute=1&playsinline=1",
#                 "creator": "YouTube",
#                 "summary": "Historical archive footage",
#                 "likes": "—",
#                 "comments": "—",
#                 "shares": "—",
#                 "hashtags": ["Archive", "History"]
#             })

#         context = {"reels": reels}
#     return render(request, "reels.html", context)
    


def story_mode(request):
    return render(request, 'story_mode.html')


def user_profile(request):
    return render(request, 'user_profile.html')


def animation(request):
    return render(request, 'animation.html')


# def reels_api(request):
#     response = requests.get("https://jsonplaceholder.typicode.com/posts?_limit=5")
#     data = response.json()

#     reels = []

#     for post in data:
#         reels.append({
#             "id": post["id"],
#             "title": post["title"],
#             "summary": post["body"],
#             "video_url": "https://www.w3schools.com/html/mov_bbb.mp4"
#         })

#     return JsonResponse({"reels": reels})



def reels(request):
    headers = {
        "Authorization": PEXEL_API_KEY
    }

    response = requests.get(
        "https://api.pexels.com/videos/search?query=Kenyan heritage/&per_page=10",
        headers=headers
    )

    data = response.json()

    reels = []

    for video in data.get("videos", []):
        reels.append({
            "title": "Historical Visual Archive",
            "summary": "Stock archival style footage",
            "video_url": video["video_files"][0]["link"],
            "creator": "Pexels",
            "likes": "—",
            "comments": "—",
            "shares": "—",
            "hashtags": ["Archive", "VisualHistory"]
        })

    return render(request, "reels.html", {"reels": reels})




# def home(request):
#     search_url = "https://www.googleapis.com/youtube/v3/search"

#     search_params = {
#         "part": "snippet",
#         "q": "history documentary",
#         "type": "video",
#         "maxResults": 5,
#         "videoDuration": "short",
#         "key": YOUTUBE_API_KEY
#     }

#     search_response = requests.get(search_url, params=search_params)
#     search_data = search_response.json()

#     video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]

#     # 🔥 Second call to check embeddable status
#     videos_url = "https://www.googleapis.com/youtube/v3/videos"

#     videos_params = {
#         "part": "status",
#         "id": ",".join(video_ids),
#         "key": YOUTUBE_API_KEY
#     }

#     videos_response = requests.get(videos_url, params=videos_params)
#     videos_data = videos_response.json()

#     reels = []

#     for video in videos_data.get("items", []):
#         if video["status"]["embeddable"]:

#             reels.append({
#                 "video_url": f"https://www.youtube.com/embed/{video['id']}?autoplay=1&mute=1&playsinline=1",
#                 "creator": "YouTube",
#                 "summary": "Historical archive footage",
#                 "likes": "—",
#                 "comments": "—",
#                 "shares": "—",
#                 "hashtags": ["Archive", "History"]
#             })

#         context = {"reels": reels}
#     return render(request, 'index.html', context)