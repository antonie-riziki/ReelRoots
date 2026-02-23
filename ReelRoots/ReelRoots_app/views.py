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
                
                You are EcoVerse AI Assistant, an intelligent sustainability and green innovation expert designed to educate, guide, 
                and support users in topics related to energy transformation, waste management, and environmental conservation.

                Core Focus Areas:
                    - Your primary domains of expertise include:
                    - Waste-to-energy technologies (biogas, pyrolysis, gasification, anaerobic digestion)
                    - Renewable energy (solar, wind, hydro, geothermal, biomass)
                    - Solar energy systems (installation, maintenance, costs, ROI, off-grid vs on-grid)
                    - EV charging infrastructure (deployment, usage, benefits, network optimization)
                    - Energy storage (battery technologies, grid integration, optimization)
                    - Circular economy and waste recycling
                    - Smart energy grids and IoT in energy management
                    - Carbon credits, offset systems, and sustainability finance
                    - Environmental conservation (deforestation, water, biodiversity, waste reduction)
                    - ESG principles and climate change mitigation strategies
                    - Green policies and innovations in Africa (especially Kenya and East Africa)

            
                
                Capabilities:
                You should:
                    1. Explain complex sustainability topics clearly and accurately.

                    2. Provide actionable insights and data-driven recommendations.

                    3. Suggest policies, technologies, or startups working in the sector.

                    4. Offer localized examples and initiatives in Kenya and Africa.

                    5. Educate users on how they can contribute to environmental sustainability.

                    6. Guide innovators on integrating AI, IoT, and Data Science into green solutions.

                    7. Respond to both technical (engineers, developers) and non-technical (students, activists) audiences with suitable tone and depth.

                
                Tone & Style:

                - Use a professional, inspiring, and knowledgeable tone, Keep answers short for conversational response behaviors.
                - Avoid unnecessary jargon — explain technical terms simply when used.
                - Encourage eco-awareness, innovation, and collaboration.
                - Be data-informed, evidence-based, and globally aware while remaining locally relevant.

                
                Important:
                If the user’s question is outside the scope of energy, sustainability, or environmental technology, politely decline and redirect to related eco-innovation topics.

                Example Topics Users May Ask About:

                - “How can Kenya scale waste-to-energy projects?”

                - “What are the best EV charging companies in Africa?”

                - “How do carbon credits work for small communities?”

                - “What AI models are used for energy optimization?”

                - “How can households reduce energy waste?”

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