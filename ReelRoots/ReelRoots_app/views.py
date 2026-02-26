from django.shortcuts import render, get_object_or_404, redirect
from google import genai
from google.genai import types
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from .models import *
import africastalking
import requests
import os
import json
import sys



from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages


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

sms = africastalking.SMS

headers = {
        "Authorization": PEXEL_API_KEY
    }

todays_date = datetime.today()

def history_highlights(prompt):
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=
            """
            You are ReelRoots AI, a historical assistant that highlights exactly one significant historical event that 
            occurred on today’s calendar date (same day and month, any past year). When prompted, identify today’s date a
            nd select the most globally significant, well-documented event from history that happened on this date. 
            
            Present the response in one concise paragraph (under 150 words) explaining what happened, where it occurred, 
            and why it was historically important. Do not list multiple events, do not ask follow-up questions, do not 
            include emojis, and do not explain your reasoning. Ensure the information is accurate, impactful, and written 
            in a clear, engaging but professional tone.

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





def login_message(phone_number):

    recipients = [f"+254{str(phone_number)}"]

    # Set your message
    message = f"Welcome back to ReelRoots, a living gateway into the stories, cultures, and defining moments of our past!"

    # Set your shortCode or senderId
    sender = "AFTKNG"
 
    try:
        response = sms.send(message, recipients, sender)

        print(response)

    except Exception as e:
        print(f'Houston, we have a problem: {e}')



# Create your views here.

def landing_page(request):
    return render(request, 'landing_page.html')


def auth(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        # ==========================
        # SIGN IN
        # ==========================
        if form_type == "signin":
            sign_in_phone = request.POST.get("sigin-phone-number")
            email = request.POST.get("email")
            password = request.POST.get("password")

            # login_message(sign_in_phone)

            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

            if user is not None:
                login(request, user)
                return redirect("home")
            else:
                messages.error(request, "Invalid email or password")

        # ==========================
        # SIGN UP
        # ==========================
        elif form_type == "signup":
            name = request.POST.get("name")
            email = request.POST.get("email")
            phone = request.POST.get("phone-number")
            institution = request.POST.get("institution")
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm-password")


            if password != confirm_password:
                messages.error(request, "Passwords do not match")
                return redirect("auth")

            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already registered")
                return redirect("auth")

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=name,
                phone_number=phone
            )

            login_message(phone)
            login(request, user)
            
            return redirect("home")
    return render(request, 'auth.html')


def home(request):

    # on_this_day = history_highlights("provide any archive in history that happend on this day " + str(todays_date))

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

    context = {
        "reels": reels[::-1],
        # "highlight": on_this_day
               }
    
    # print("On this day " + str(todays_date))
    
    return render(request, 'index.html', context)


def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')


def archive_details(request, slug):
    archive_details = get_object_or_404(Archive, slug=slug)
    photos = archive_details.media.filter(media_type="photo")
    
    context = {
        "archive_details": archive_details,
        "photos": photos,
               }
    return render(request, 'archive_details.html', context)


def chat(request):
    return render(request, 'chat.html')


def explore(request):
    archives = Archive.objects.filter(
        visibility="public",
        verification_status="verified"
    ).order_by("-event_date")

    context = {
        "archives": archives
    }
    return render(request, 'explore.html', context)


def new_upload(request):
    return render(request, 'new_upload.html')


# import requests
# from django.conf import settings
# from django.shortcuts import render

# def reels(request):
#     search_url = "https://www.googleapis.com/youtube/v3/search"

#     search_params = {
#         "part": "snippet",
#         "q": "history documentary",
#         "type": "video",
#         "maxResults": 1,
#         "videoDuration": "short",
#         "key": os.getenv("YOUTUBE_API_KEY"),
#     }

#     search_response = requests.get(search_url, params=search_params)

#     if search_response.status_code != 200:
#         return render(request, "reels.html", {"reels": []})

#     search_data = search_response.json()

#     video_ids = [
#         item["id"]["videoId"]
#         for item in search_data.get("items", [])
#         if "videoId" in item["id"]
#     ]

#     if not video_ids:
#         return render(request, "reels.html", {"reels": []})

#     # Second call
#     videos_url = "https://www.googleapis.com/youtube/v3/videos"

#     videos_params = {
#         "part": "status",
#         "id": ",".join(video_ids),
#         "key": os.getenv("YOUTUBE_API_KEY"),
#     }

#     videos_response = requests.get(videos_url, params=videos_params)

#     if videos_response.status_code != 200:
#         return render(request, "reels.html", {"reels": []})

#     videos_data = videos_response.json()

#     reels = []

#     for video in videos_data.get("items", []):
#         if video.get("status", {}).get("embeddable"):
#             reels.append({
#                 "video_url": f"https://www.youtube.com/embed/{video['id']}?rel=0",
#             })

#     return render(request, "reels.html", {"reels": reels})
    


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

import random
PEXELS_URL = "https://api.pexels.com/videos/search"

HISTORICAL_QUERIES = [
    "Kenyan heritage documentary style",
    "Maasai traditional ceremony",
    "African independence celebration",
    "African museum artifacts",
    "vintage Africa black and white",
    "Swahili culture Lamu",
    "African traditional storytelling",
]


def reels(request):
    query = random.choice(HISTORICAL_QUERIES)

    headers = {
        "Authorization": PEXEL_API_KEY
    }

    params = {
        "query": query,
        "per_page": 20
    }

    response = requests.get(PEXELS_URL, headers=headers, params=params)

    if response.status_code != 200:
        return render(request, "reels.html", {"reels": []})


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
#         "maxResults": 1,
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