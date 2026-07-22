from django.shortcuts import render, get_object_or_404, redirect
from google import genai
from google.genai import types
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import datetime
from .models import Archive
from .content_providers import WikimediaCommonsVideoProvider, seed_provider_feed
from .decorators import get_session_profile, onboarding_required, reelroots_login_required
from .personalization import profile_preferences, ranked_interests
from .reel_feed import get_ranked_reels
import requests
import os
import json



from .supabase_client import supabase


YOUTUBE_API_KEY=os.getenv("YOUTUBE_API_KEY")


# Keep optional integrations lazy so routes such as landing, upload, and auth can
# render even if an external provider is temporarily unavailable.
_genai_client = None


def get_genai_client():
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _genai_client

todays_date = datetime.today()

def history_highlights(prompt):
    response = get_genai_client().models.generate_content(
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

    response = get_genai_client().models.generate_content(
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


@onboarding_required
def home(request):

    # on_this_day = history_highlights("provide any archive in history that happend on this day " + str(todays_date))

    reels = []
    try:
        for item in WikimediaCommonsVideoProvider().fetch(feed_type="for-you", per_page=10):
            reels.append({
                "title": item.title,
                "summary": item.description,
                "video_url": item.video_url,
                "creator": item.creator_name,
                "likes": "—",
                "comments": "—",
                "shares": "—",
                "hashtags": list(item.topic_slugs),
            })
    except requests.RequestException:
        pass

    context = {
        "reels": reels[::-1],
        "interest_profile": ranked_interests(request.reelroots_profile),
        # "highlight": on_this_day
               }
    
    # print("On this day " + str(todays_date))
    
    return render(request, 'index.html', context)


@reelroots_login_required
def admin_dashboard(request):
    if not request.reelroots_profile.is_moderator:
        return render(request, "moderation_forbidden.html", status=403)
    return render(request, 'admin_dashboard.html')


def archive_details(request, slug):
    archive_details = get_object_or_404(Archive, slug=slug)
    photos = archive_details.media.filter(media_type="photo")
    
    context = {
        "archive_details": archive_details,
        "photos": photos,
               }
    return render(request, 'archive_details.html', context)


@onboarding_required
def chat(request):
    return render(request, 'chat.html')


def explore(request):
    try:
        response = supabase.table("archives") \
            .select("*, media(file_url)") \
            .eq("visibility", "public") \
            .eq("verification_status", "verified") \
            .order("event_date", desc=True) \
            .execute()
        
        archives = response.data
        
        for arch in archives:
            arch["media_url"] = arch["media"][0]["file_url"] if arch.get("media") and len(arch["media"]) > 0 else None

    except Exception as e:
        print(f"Error fetching from Supabase: {e}")
        archives = []

    context = {
        "archives": archives
    }
    return render(request, 'explore.html', context)


from django.utils.text import slugify
import uuid

@require_POST
@reelroots_login_required
def create_archive(request):
    try:
        title = request.POST.get("title")
        event_date = request.POST.get("event_date")
        country = request.POST.get("country")
        region = request.POST.get("region")
        category = request.POST.get("category")
        summary = request.POST.get("summary")
        full_story = request.POST.get("full_story")
        description = ""  # Removed from UI but required by schema

        media_file = request.FILES.get("media")
        tags_json = request.POST.get("tags")

        if not all([title, event_date, country, region, category, summary, full_story, media_file]):
            return JsonResponse({"error": "All fields including media are required"}, status=400)

        # Create a unique slug
        base_slug = slugify(title)
        slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

        new_record = {
            "title": title,
            "slug": slug,
            "event_date": event_date,
            "country": country,
            "region": region,
            "category": category,
            "summary": summary,
            "description": description,
            "full_story": full_story,
            "visibility": "private",
            "verification_status": "draft"
        }

        # 1. Insert Archive
        response = supabase.table("archives").insert(new_record).execute()
        if not response.data:
            return JsonResponse({"error": "Failed to create archive"}, status=400)

        archive_id = response.data[0]["id"]

        # 2. Upload Media to Supabase Storage
        file_extension = media_file.name.split('.')[-1]
        file_name = f"{archive_id}_{uuid.uuid4().hex[:6]}.{file_extension}"

        file_content = media_file.read()
        mime_type = media_file.content_type

        supabase.storage.from_("media").upload(
            file_name,
            file_content,
            {"content-type": mime_type}
        )

        public_url = supabase.storage.from_("media").get_public_url(file_name)

        media_type = "photo" if mime_type.startswith("image") else ("video" if mime_type.startswith("video") else "document")
        supabase.table("media").insert({
            "archive_id": archive_id,
            "media_type": media_type,
            "file_url": public_url
        }).execute()

        # 3. Handle Tags
        if tags_json:
            tags = json.loads(tags_json)
            for tag_name in tags:
                # Check if tag exists
                tag_res = supabase.table("tags").select("id").eq("name", tag_name).execute()
                if tag_res.data:
                    tag_id = tag_res.data[0]["id"]
                else:
                    new_tag_res = supabase.table("tags").insert({"name": tag_name}).execute()
                    tag_id = new_tag_res.data[0]["id"]

                supabase.table("archive_tags").insert({
                    "archive_id": archive_id,
                    "tag_id": tag_id
                }).execute()

        return JsonResponse({"message": "Archive created successfully", "data": response.data[0]}, status=201)

    except Exception as e:
        print(f"Error in create_archive: {e}")
        return JsonResponse({"error": "Unable to create archive"}, status=500)

@reelroots_login_required
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


@reelroots_login_required
def user_profile(request):
    profile = request.reelroots_profile
    return render(request, 'user_profile.html', {
        "profile": profile,
        "interest_profile": ranked_interests(profile),
        "preferences": profile_preferences(profile),
    })


def animation(request):
    return render(request, 'animation.html')


@require_POST
@reelroots_login_required
def chatbot_response(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'response': "Invalid request."}, status=400)
    user_message = data.get('message', '')
    if user_message:
        bot_reply = get_gemini_response(user_message[:4000])
        return JsonResponse({'response': bot_reply})
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
    feed_type = request.GET.get("feed", "for-you")
    allowed_feeds = {"for-you", "following", "trending", "recent", "history", "culture", "heritage", "oral-history", "indigenous-knowledge", "architecture", "music", "food", "art"}
    if feed_type not in allowed_feeds:
        feed_type = "for-you"
    profile = get_session_profile(request)
    feed_reels = get_ranked_reels(profile, feed_type=feed_type)
    if not feed_reels and feed_type != "following":
        try:
            seed_provider_feed(feed_type)
        except requests.RequestException:
            pass
        feed_reels = get_ranked_reels(profile, feed_type=feed_type)

    reel_cards = []
    for reel in feed_reels:
        context = {
            "summary": reel.context_summary or reel.description,
            "claims": reel.key_claims,
            "historical_context": reel.historical_context or "Context is being prepared by the ReelRoots editorial team.",
            "people": reel.important_people,
            "locations": reel.important_locations,
            "timeline": reel.timeline,
            "topics": [topic.name for topic in reel.topics.all()],
            "sources": reel.external_references,
            "verification_status": reel.get_verification_status_display(),
            "confidence": float(reel.confidence_score or 0),
        }
        reel_cards.append({
            "id": str(reel.id),
            "video_url": reel.video_url,
            "thumbnail_url": reel.thumbnail_url,
            "title": reel.title,
            "description": reel.description,
            "creator": reel.creator_name,
            "creator_handle": reel.creator_handle or reel.creator_name.lower().replace(" ", ""),
            "duration": reel.duration_seconds,
            "source_url": reel.source_url,
            "source_attribution": reel.source_attribution,
            "verification_status": reel.get_verification_status_display(),
            "confidence": float(reel.confidence_score or 0),
            "topics": [{"slug": topic.slug, "name": topic.name} for topic in reel.topics.all()],
            "context_json": json.dumps(context),
            "likes": reel.likes.count(),
            "comments": reel.comments.filter(is_hidden=False).count(),
            "saves": reel.saves.count(),
        })

    return render(request, "reels.html", {
        "reels": reel_cards,
        "feed_type": feed_type,
        "profile": profile,
        "is_authenticated": profile is not None,
        "feed_tabs": [
            ("for-you", "For You"),
            ("following", "Following"),
            ("trending", "Trending"),
            ("recent", "Recent"),
            ("heritage", "Heritage"),
            ("culture", "Culture"),
            ("history", "History"),
        ],
    })




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
