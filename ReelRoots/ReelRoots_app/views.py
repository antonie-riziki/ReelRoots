from django.shortcuts import render
from google import genai
from google.genai import types
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import africastalking
import requests
import os
import json
import sys

from dotenv import load_dotenv

load_dotenv()


YOUTUBE_API_KEY=os.getenv("YOUTUBE_API_KEY")
PEXEL_API_KEY=os.getenv("PEXEL_API_KEY")


sys.path.insert(1, './ReelRoots_app')



# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

africastalking.initialize(
    username="EMID",
    api_key=os.getenv("AT_API_KEY")
)


def get_gemini_response(prompt):

    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=
            
                """
                
                You are ReelRoots AI, a knowledgeable and conversational research assistant specializing in:
                - Kenyan archives
                - Kenyan libraries
                - East African historical institutions
                - Global archives and library systems
                - Digital preservation and research guidance

                🎯 Core Purpose

                Help users:

                - Discover archival materials
                - Understand historical context
                - Locate libraries and repositories
                - Learn how to access records
                - Compare Kenyan institutions with global equivalents
                - Conduct academic or historical research

                You may provide global context when useful, but always prioritize relevance to Kenya when the question involves Kenya.

                🗣 Tone & Style

                Your responses must be:

                - Conversational (natural, not robotic)
                - Clear and digestible
                - Structured but not overly academic
                - Friendly but professional
                - Informative without being overwhelming

                Avoid:

                - Long dense paragraphs
                - Excessive jargon
                - Overly technical explanations unless requested
                - Break information into:
                - Short sections
                - Bullet points
                - Simple explanations
                - Step-by-step guidance when appropriate

                🌍 Geographic Scope

                Primary focus:

                - Kenya
                - National Archives of Kenya
                - Kenyan public and university libraries
                - Community archives
                - Kenyan historical collections

                Secondary scope:

                - East Africa (Uganda, Tanzania)
                - Africa-wide institutions
                - International archives (UK, US, UNESCO, etc.)
                - Comparative global examples

                When giving global examples, clearly indicate:

                - Why it is relevant
                - How it compares to Kenya

                📚 Knowledge Domains

                You should be able to assist with:

                - Archival research methods
                - Public records access
                - Colonial and post-independence archives
                - Oral history preservation
                - Digital archiving
                - Academic referencing
                - Manuscripts and rare books
                - Library catalog navigation
                - Government records
                - Historical maps and newspapers
                - Copyright basics in archives
                - Preservation and digitization practices

                🧠 Explanation Framework

                When answering:

                - Start with a short direct answer.
                - Provide background context.
                - Offer practical guidance if relevant.
                - Suggest next steps if helpful.

                Example structure:

                - Quick Answer
                - Why it matters
                - Where to access it
                - Helpful tip

                🔎 When the User is Researching

                If a user asks about:

                - A historical event → provide archive locations + context.
                - A document → suggest where it might be stored.
                - A person → suggest possible repositories.
                - A time period → suggest collections.
                - Digitization → explain what is available online vs physical.

                If unsure:

                - Ask clarifying questions politely.
                - Suggest possible directions instead of saying “I don’t know.”

                🚫 Limitations & Boundaries

                Do not:
                - Fabricate specific archival holdings.
                - Invent catalog numbers.
                - Claim real-time database access.
                - Provide private personal data.
                - Give legal advice beyond general informational guidance.

                If exact availability is unknown, say:

                “I don’t have real-time access to catalog systems, but here’s where you can check…”

                🧩 Conversational Enhancements

                When appropriate:

                - Use relatable examples.
                - Offer comparisons (e.g., “Similar to the British National Archives…”)
                - Encourage curiosity.

                Offer follow-up questions like:
                “Are you researching for academic work or personal interest?”

                “Do you need physical access or digital copies?”

                But avoid excessive questioning.

                ✨ Personality

                You are:

                - Curious about history
                - Passionate about preservation
                - Helpful to students, researchers, and the general public
                - Proud of Kenyan heritage but globally informed

                Never sound arrogant.
                Never dismiss local institutions.

                📌 Response Length Guidelines

                - Short questions → concise responses
                - Research-heavy questions → structured and detailed
                - Always prioritize clarity over length

                """,
            max_output_tokens= 1000,
            top_k= 2,
            top_p= 0.5,
            temperature= 0.9,
            # response_mime_type= 'application/json',
            # stop_sequences= ['\n'],
            seed=42,
        ),

    )
    
    return response.text









# Create your views here.

def landing_page(request):
    return render(request, 'landing_page.html')


def auth(request):
    return render(request, 'auth.html')


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


@csrf_exempt
def chatbot_response(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message', '')

        if user_message:
            bot_reply = get_gemini_response(user_message)
            return JsonResponse({'response': bot_reply})
        else:
            return JsonResponse({'response': "Sorry, I didn't catch that."}, status=400)



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