from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ReelRoots_app.models import (
    PendingSignup,
    PersonalizationEvent,
    ProfileInterest,
    ProfilePreference,
    Reel,
    ReelComment,
    ReelCreatorFollow,
    ReelLike,
    ReelSave,
    Topic,
    UserProfile,
)
from ReelRoots_app.content_providers import classify_heritage_relevance
from ReelRoots_app.personalization import ranked_interests, record_engagement


class AuthFlowTests(TestCase):
    def setUp(self):
        self.user_id = uuid4()
        self.auth_response = SimpleNamespace(
            user=SimpleNamespace(id=str(self.user_id)),
            session=SimpleNamespace(access_token="access", refresh_token="refresh"),
        )

    def signup_payload(self, **overrides):
        data = {
            "form_type": "signup",
            "name": "Amina Otieno",
            "phone-number": "0712345678",
            "email": "amina@example.com",
            "institution": "ReelRoots Lab",
            "password": "StrongPassword123!",
            "confirm-password": "StrongPassword123!",
            "terms": "on",
        }
        data.update(overrides)
        return data

    def create_profile(self, onboarding_completed=True):
        return UserProfile.objects.create(
            supabase_user_id=self.user_id,
            email="amina@example.com",
            name="Amina Otieno",
            phone_number="+254712345678",
            phone_verified_at=timezone.now(),
            onboarding_completed=onboarding_completed,
        )

    def test_registration_sends_otp_and_stages_account(self):
        with patch("ReelRoots_app.auth_views.AfricaTalkingSMS.__init__", return_value=None), patch("ReelRoots_app.auth_views.AfricaTalkingSMS.send_otp") as send_otp, patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "create_staged_user") as create_user:
            create_user.return_value = SimpleNamespace(id=str(self.user_id))
            with patch("ReelRoots_app.auth_views._code", return_value="123456"):
                response = self.client.post(reverse("auth"), self.signup_payload(), HTTP_HOST="localhost")
        self.assertRedirects(response, reverse("verify-phone"), fetch_redirect_response=False)
        self.assertTrue(PendingSignup.objects.filter(email="amina@example.com").exists())
        self.assertEqual(self.client.session["pending_signup_id"], str(PendingSignup.objects.get().id))
        send_otp.assert_called_once_with("+254712345678", "123456")

    def test_invalid_and_expired_otp_are_rejected(self):
        with patch("ReelRoots_app.auth_views.AfricaTalkingSMS.__init__", return_value=None), patch("ReelRoots_app.auth_views.AfricaTalkingSMS.send_otp"), patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "create_staged_user") as create_user:
            create_user.return_value = SimpleNamespace(id=str(self.user_id))
            with patch("ReelRoots_app.auth_views._code", return_value="123456"):
                self.client.post(reverse("auth"), self.signup_payload(), HTTP_HOST="localhost")
        pending = PendingSignup.objects.get()
        response = self.client.post(reverse("verify-phone"), {"code": "000000"}, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        pending.phone_verification.refresh_from_db()
        self.assertEqual(pending.phone_verification.attempts, 1)
        pending.phone_verification.expires_at = timezone.now() - timedelta(minutes=1)
        pending.phone_verification.save(update_fields=["expires_at"])
        response = self.client.post(reverse("verify-phone"), {"code": "123456"}, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "expired")

    def test_valid_otp_creates_profile_and_session(self):
        with patch("ReelRoots_app.auth_views.AfricaTalkingSMS.__init__", return_value=None), patch("ReelRoots_app.auth_views.AfricaTalkingSMS.send_otp"), patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "create_staged_user") as create_user, patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "confirm_phone") as confirm_phone, patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "sign_in") as sign_in:
            create_user.return_value = SimpleNamespace(id=str(self.user_id))
            sign_in.return_value = self.auth_response
            with patch("ReelRoots_app.auth_views._code", return_value="123456"):
                self.client.post(reverse("auth"), self.signup_payload(), HTTP_HOST="localhost")
            response = self.client.post(reverse("verify-phone"), {"code": "123456"}, HTTP_HOST="localhost")
        profile = UserProfile.objects.get(email="amina@example.com")
        self.assertRedirects(response, reverse("onboarding"), fetch_redirect_response=False)
        self.assertTrue(profile.phone_verified)
        self.assertEqual(self.client.session["profile_id"], str(profile.id))
        confirm_phone.assert_called_once_with(self.user_id)
        sign_in.assert_called_once()

    def test_duplicate_account_is_rejected(self):
        self.create_profile()
        response = self.client.post(reverse("auth"), self.signup_payload(), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already in use")

    def test_login_logout_and_session_handling(self):
        profile = self.create_profile(onboarding_completed=True)
        with patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "sign_in", return_value=self.auth_response):
            response = self.client.post(reverse("auth"), {"form_type": "signin", "email": profile.email, "password": "StrongPassword123!"}, HTTP_HOST="localhost")
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["profile_id"], str(profile.id))
        with patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "sign_out"):
            response = self.client.post(reverse("logout"), HTTP_HOST="localhost")
        self.assertRedirects(response, reverse("landing-page"), fetch_redirect_response=False)
        self.assertNotIn("profile_id", self.client.session)

    def test_unauthorized_views_redirect(self):
        for url_name in ["home", "onboarding", "user-profile", "profile-settings"]:
            response = self.client.get(reverse(url_name), HTTP_HOST="localhost")
            self.assertEqual(response.status_code, 302, url_name)
            self.assertIn(reverse("auth"), response["Location"])
        response = self.client.post(reverse("personalization-event"), data="{}", content_type="application/json", HTTP_HOST="localhost")
        self.assertIn(response.status_code, {302, 403})

    def test_password_reset_is_generic_and_does_not_enumerate_accounts(self):
        with patch.object(__import__("ReelRoots_app.auth_views", fromlist=["SupabaseAuth"]).SupabaseAuth, "request_password_reset") as request_reset:
            response = self.client.post(reverse("forgot-password"), {"email": "unknown@example.com"}, HTTP_HOST="localhost")
        self.assertRedirects(response, reverse("auth"), fetch_redirect_response=False)
        request_reset.assert_called_once_with("unknown@example.com")

    def test_password_reset_completion_page_is_available(self):
        response = self.client.get(reverse("reset-password"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a new password")


class PersonalizationTests(TestCase):
    def setUp(self):
        self.profile = UserProfile.objects.create(
            supabase_user_id=uuid4(),
            email="reader@example.com",
            name="Reader",
            phone_number="+254711111111",
            phone_verified_at=timezone.now(),
            onboarding_completed=True,
        )
        self.history = Topic.objects.get(slug="history")
        self.culture = Topic.objects.get(slug="culture")

    def test_explicit_and_observed_interests_are_ranked_transparently(self):
        ProfileInterest.objects.create(profile=self.profile, topic=self.history, source="explicit", weight=5)
        for event_type in ["watch", "watch", "save", "like", "share"]:
            record_engagement(self.profile, event_type=event_type, topic_slug="culture", content_key="reel-1")
        record_engagement(self.profile, event_type="completion", topic_slug="culture", value=0.9, content_key="reel-1")
        ranked = ranked_interests(self.profile)
        self.assertEqual(ranked[0]["slug"], "culture")
        self.assertEqual(PersonalizationEvent.objects.count(), 6)
        self.assertTrue(ProfileInterest.objects.filter(profile=self.profile, source="observed", topic=self.culture).exists())

    def test_onboarding_persists_interests_and_preferences(self):
        session = self.client.session
        session["profile_id"] = str(self.profile.id)
        session["supabase_user_id"] = str(self.profile.supabase_user_id)
        session.save()
        response = self.client.post(reverse("onboarding"), {
            "topics": ["history", "oral-history"],
            "regions": ["East Africa"],
            "countries": ["Kenya"],
            "languages": ["en", "sw"],
            "content_types": ["short_video", "oral_history"],
        }, HTTP_HOST="localhost")
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.onboarding_completed)
        self.assertEqual(self.profile.interests.filter(source="explicit").count(), 2)
        self.assertTrue(ProfilePreference.objects.filter(profile=self.profile, preference_type="language", value="sw").exists())


class ReelExperienceTests(TestCase):
    def setUp(self):
        self.profile = UserProfile.objects.create(
            supabase_user_id=uuid4(),
            email="reel-reader@example.com",
            name="Reel Reader",
            phone_number="+254722222222",
            phone_verified_at=timezone.now(),
            onboarding_completed=True,
        )
        self.reel = Reel.objects.create(
            creator_profile=self.profile,
            creator_name="Reel Reader",
            creator_handle="reelreader",
            source_platform="pexels",
            external_id="test-heritage-1",
            source_url="https://www.pexels.com/video/test-heritage-1/",
            video_url="https://videos.pexels.com/video-files/test.mp4",
            title="A heritage visual reference",
            description="A short visual story about cultural heritage.",
            source_attribution="Pexels source",
            license_status="licensed",
            content_type="curated_external",
            heritage_relevance="0.85",
            confidence_score="0.20",
            status="published",
        )
        self.reel.topics.add(Topic.objects.get(slug="heritage"))
        session = self.client.session
        session["profile_id"] = str(self.profile.id)
        session["supabase_user_id"] = str(self.profile.supabase_user_id)
        session.save()

    def test_reel_feed_renders_context_and_feed_tabs(self):
        response = self.client.get(reverse("reels"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Context")
        self.assertContains(response, "For You")
        self.assertContains(response, "A heritage visual reference")
        self.assertContains(response, "Open source")

    def test_following_feed_does_not_expose_general_feed_to_anonymous_users(self):
        self.client.session.flush()
        response = self.client.get(reverse("reels") + "?feed=following", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "There are no published reels in this feed yet")

    def test_reel_interactions_and_comments_are_persistent(self):
        interaction_url = reverse("reel-interaction", args=[self.reel.id])
        response = self.client.post(interaction_url, data={"action": "like"}, content_type="application/json", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ReelLike.objects.filter(reel=self.reel, profile=self.profile).exists())
        self.client.post(interaction_url, data={"action": "save"}, content_type="application/json", HTTP_HOST="localhost")
        self.client.post(interaction_url, data={"action": "follow"}, content_type="application/json", HTTP_HOST="localhost")
        self.assertTrue(ReelSave.objects.filter(reel=self.reel, profile=self.profile).exists())
        self.assertTrue(ReelCreatorFollow.objects.filter(profile=self.profile, creator_key=self.reel.creator_key).exists())
        comments_url = reverse("reel-comments", args=[self.reel.id])
        response = self.client.post(comments_url, data={"body": "This made me curious to learn more."}, content_type="application/json", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ReelComment.objects.filter(reel=self.reel).count(), 1)

    def test_reel_interactions_require_authentication(self):
        self.client.session.flush()
        response = self.client.post(reverse("reel-interaction", args=[self.reel.id]), data={"action": "like"}, content_type="application/json", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 401)

    def test_relevance_classifier_only_accepts_heritage_signals(self):
        score, topics = classify_heritage_relevance("Traditional oral history ceremony", "Community storytelling")
        self.assertGreaterEqual(score, 0.45)
        self.assertIn("oral-history", topics)
