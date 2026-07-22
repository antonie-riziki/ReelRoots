# ReelRoots Codebase and Product Audit

Audit date: 2026-07-22
Repository: `antonie-riziki/ReelRoots`
Checkout: `main` at `bb6b664` (`unify ReelRoots product experience`)

This audit is read-only with respect to application code. The local `ReelRoots/.env` was populated with the supplied values and is ignored by Git. Secret values are intentionally not reproduced here.

## 1. Executive Summary

ReelRoots is a Django prototype for an African cultural-heritage and archive discovery product. Its strongest implemented slice is the presentation layer: a coherent mobile-first visual experience for landing, authentication, archive discovery, upload, reels, story mode, chat, profile, and archivist screens.

The working application is not yet a unified archive product. It has two disconnected data planes:

- Django ORM/SQLite models for `Archive`, `Tag`, and `Media`.
- Supabase Auth, Postgres tables, and Storage used by the active sign-in/sign-up, explore, upload, and profile flows.

The active archive flows use Supabase, while archive detail uses Django ORM. The checked-in SQLite database is not part of Git and contains zero domain records. The live Supabase archive, media, and tag tables were readable and empty during the audit; one profile row was present.

The reels feed is currently a Pexels stock-video feed, not a ReelRoots content feed. YouTube support exists only as commented-out code. AI is a Gemini chat endpoint with a separate unused “on this day” helper; it is not grounded in archive sources and is not a verification engine. Africa’s Talking is currently used only for a sign-up welcome SMS, with hard-coded sender/user values and no sign-in SMS flow.

The most urgent issues are unauthenticated public publishing, CSRF exemptions, absence of authorization checks, secret/service-key handling, no upload validation or size limits, no rate limiting, XSS-prone chat rendering, missing logout, insecure production defaults, and the split Django/Supabase data model.

## 2. Current Product Understanding

The README describes ReelRoots as an AI-powered social archival platform that turns library and archive material into interactive, visual experiences. The current interface is aimed at younger users and communicates:

- archive discovery and filtering;
- short-form archive reels;
- AI archive assistance;
- story/comic mode;
- community memory contribution;
- archivist stewardship.

The supplied product vision expands that into a trusted cultural heritage discovery platform with short-form storytelling, contextual AI, claim verification, community contributions, and long-term knowledge preservation.

What the code currently represents is an early UX prototype with a few working integrations, not the complete product. The UI often communicates future capabilities that do not yet have domain models, workflows, or persisted behavior.

## 3. Current Architecture

### Repository and runtime

- Django project lives under `ReelRoots/`.
- Project package: `ReelRoots/ReelRoots/`.
- Single Django app: `ReelRoots/ReelRoots_app/`.
- Templates are app-local under `ReelRoots/ReelRoots_app/templates/`.
- Static source is under `ReelRoots/static/`; generated `staticfiles/` artifacts are also tracked.
- SQLite development database is at `ReelRoots/db.sqlite3`, ignored by Git.
- WSGI and ASGI entrypoints exist.
- `ReelRoots/vercel.json` configures a Vercel Python build using `ReelRoots/wsgi.py` and Python 3.12.

### Request path

Most browser routes resolve to function-based views in `views.py`, render Django templates, and use either Supabase or third-party HTTP APIs directly inside the request. There is no service layer, serializer layer, forms layer, API router, background worker, task queue, or domain-level permission layer.

### Important architectural split

`models.py` defines Django models, but active CRUD does not use them. The active upload and explore flows call Supabase tables directly. `archive_details()` alone queries the Django `Archive` model. This creates incompatible identifiers, schemas, data visibility, and storage semantics.

## 4. Existing Django Apps

There is one project app:

### `ReelRoots_app`

- `models.py`: Django archive, tag, and media models.
- `views.py`: all page views, auth handlers, third-party integration calls, upload endpoint, AI endpoint, and reels endpoint.
- `urls.py`: page and endpoint routing.
- `admin.py`: Django admin registrations for `Archive` and `Tag`, with `Media` as an inline.
- `supabase_client.py`: lazy Supabase client wrapper.
- `templates/`: 16 HTML templates.
- `tests.py`: placeholder only; no tests.
- `migrations/0001_initial.py`: initial Django domain schema.

The built-in Django apps are installed for admin, sessions, messages, auth, and static files. Built-in Django auth is not used by the product-facing auth flow.

## 5. Database Model Map

### Django ORM / SQLite

#### `Archive`

Purpose: structured historical/archive record.

Fields:

- UUID primary key;
- title and unique slug;
- event date and optional end date;
- country, region, county, city, latitude, longitude;
- category, era, impact level;
- summary, description, and full story;
- optional quote text, author, and source;
- verification status: draft, reviewed, verified;
- visibility: public, private, restricted;
- featured flag and view count;
- created/updated timestamps.

Relationships: many-to-many with `Tag`; one-to-many with `Media` through `Media.archive`.

Assessment: retain the conceptual model, but reconcile it with the canonical database and add ownership, provenance, submission status, review history, language/accessibility metadata, source citations, and publication controls.

#### `Tag`

Purpose: reusable archive discovery term.

Fields: unique name.

Relationship: many-to-many with `Archive`.

Assessment: retain, but add normalization/slugging and possibly controlled vocabulary or taxonomy relationships.

#### `Media`

Purpose: file attached to an archive.

Fields: archive foreign key, media type (photo/video/audio/document), local Django `FileField`, caption, upload timestamp.

Assessment: retain as a metadata abstraction, but change the file field to a provider key/object path plus signed/public URL policy, checksum, size, MIME, duration, dimensions, transcription/OCR status, moderation status, and provenance. The active Supabase schema instead uses `file_url`, so the two versions currently do not match.

#### Built-in Django tables

The local SQLite database contains Django auth, groups, permissions, admin log, content types, and sessions. Counts observed during the audit: zero Django users, zero `Archive`, zero `Tag`, and zero `Media` records. Migrations are applied.

### Supabase data plane inferred from code and verified read-only

#### `profiles`

Used for extra user data after Supabase Auth sign-up and for the profile page. The code writes `id`, `name`, `phone_number`, and `institution`. The observed row shape included those fields. The intended relationship is `profiles.id` to the Supabase Auth user ID, but no schema/migration is stored in this repository.

#### `archives`

Used by explore and upload. The code expects title, slug, event date, country, region, category, summary, description, full story, visibility, and verification status. The upload endpoint forces new records to `public` and `verified`.

#### `media`

Used by explore and upload. The code expects archive ID, media type, and `file_url`; media is uploaded to a Supabase Storage bucket named `media`.

#### `tags`

Used for lookup/create by name during upload.

#### `archive_tags`

Join table for archive/tag many-to-many links. The table does not expose an `id` column; selecting `id` failed as expected, while selecting `archive_id` and `tag_id` worked. It is not versioned in the repository.

#### Storage bucket `media`

The upload endpoint writes a generated filename and calls `get_public_url()`. Bucket privacy, file policies, RLS, and lifecycle configuration are external to this repository and were not auditable here.

## 6. Current User Flow

1. Landing page `/` renders a marketing page with Explore Archives, Watch Reels, and auth/contribution calls to action.
2. `/auth` presents sign-in and sign-up tabs. Both forms use CSRF tokens.
3. Sign-up calls Supabase Auth, attempts a `profiles` insert, stores custom Supabase tokens and user ID in the Django session, sends a welcome SMS through Africa’s Talking, and redirects to `/home`.
4. Sign-in calls Supabase `sign_in_with_password`, stores custom Supabase tokens and user ID in the Django session, and redirects to `/home`.
5. `/home` calls Pexels for Kenya culture videos and renders a home dashboard. The “on this day” AI call is commented out, while the template still contains a hard-coded date/title section.
6. `/explore/` reads public, verified Supabase archives and their first media URL. The current live table returned no archive rows.
7. `/archive/<slug>/` reads the Django ORM, not Supabase. Newly uploaded Supabase records therefore do not naturally reach this page.
8. `/reels/` calls Pexels with a random heritage query and renders a snap-scrolling vertical video feed. Likes, comments, and shares are display-only placeholders.
9. `/upload/` renders a client-side form that POSTs multipart data to `/api/archives/create/`. It does not submit a CSRF token.
10. `/user-profile/` requires only the presence of a custom `user_id` session value, then reads the matching Supabase profile. It has no edit, logout, or real contribution data flow.
11. `/chat/` is mostly a static chat screen. The floating chatbox included on home posts JSON to `/chatbot-response/`, which calls Gemini.
12. `/story-mode/`, `/animation/`, and `/admin-dashboard/` are static presentation routes with no connected persistence or workflows.
13. There is no product logout route. There is no working forgot-password flow.

## 7. Current Reels Architecture

The only active reels source is Pexels:

- `/home` uses a fixed query for Kenya culture and maps the returned first video file into a lightweight dictionary.
- `/reels/` selects one random query from a list covering Kenyan heritage, Maasai ceremony, African independence, museums, vintage Africa, Lamu, and storytelling.
- The feed template uses full-screen/snap-scroll video cards, autoplay, muted playback, and a mobile-oriented bottom navigation.
- Creator, likes, comments, shares, hashtags, and summaries are fabricated display values.
- No Reel model exists.
- No archive-to-reel relationship exists.
- No creator, moderation, duration selection, caption/transcript, source attribution, engagement, feed ranking, or reporting exists.
- YouTube integration is only commented-out code and is not invoked.

This is a visual feed prototype, not a trusted cultural heritage reels system. Pexels footage is also not automatically historical evidence and should not be presented as an archive record without explicit source labeling.

## 8. Current Authentication Architecture

The product-facing flow uses Supabase Auth directly from server-side Django code. Tokens are copied into Django session keys named `supabase_access_token`, `supabase_refresh_token`, and `user_id`.

The built-in Django `User`, `authenticate`, `login`, and `logout` imports are unused. No Django user is created or linked to the Supabase identity. No middleware verifies the stored Supabase access token on each request. The profile page treats the existence of `user_id` as sufficient identity evidence.

Observed issues:

- no logout endpoint or session invalidation;
- no token refresh/revocation flow;
- sign-up can set `user_id` even when Supabase did not return a session, depending on email-confirmation settings;
- no role/permission model for archivists, reviewers, contributors, or administrators;
- `/admin-dashboard/` is not protected even though its name implies privileged access;
- no rate limits or abuse controls around auth or SMS;
- phone input is collected but sign-in SMS is commented out;
- hard-coded `+254` formatting accepts no normalized international strategy;
- built-in Django admin is a separate identity system from product users.

## 9. Current AI Architecture

`google-genai` is used through a lazily created Gemini client keyed by `GOOGLE_API_KEY`.

Active:

- `get_gemini_response()` sends arbitrary user chat text to `gemini-2.0-flash` with a long archival assistant instruction.
- `/chatbot-response/` accepts JSON POST and returns the model text.

Dormant:

- `history_highlights()` is designed to generate a single “on this day” event, but the home view call is commented out.

Missing for the product vision:

- archive/source retrieval;
- embeddings/vector search;
- citation enforcement;
- claim extraction;
- evidence comparison;
- model-output audit trail;
- prompt/version tracking;
- user quotas and rate limits;
- safety and uncertainty handling;
- asynchronous processing.

The current AI layer is a general chatbot, not a trusted contextualization or misinformation-verification engine.

## 10. Current Content Architecture

The content concept is archive-first, with metadata, tags, optional quotes, verification status, visibility, and media. However, the implementation has no content ownership, submitter, reviewer, source URL, original institution, rights/license, language, transcription, OCR text, citation, correction, revision, or moderation records.

The active upload flow:

- accepts image, video, or PDF in the browser;
- performs only required-field checks in JavaScript and a small server-side presence check;
- creates a Supabase archive record;
- uploads a file to the `media` bucket;
- inserts a media row;
- creates tags and join rows;
- forces `verification_status = verified` and `visibility = public`;
- does not link the record to the submitting user;
- does not use Django forms or the Django models;
- does not implement the UI promise that submissions are reviewed before publishing.

The archive detail page uses the unused Django content plane, so it is not a continuation of the active upload path.

## 11. Current UI/UX Architecture

Design system:

- Tailwind CSS is loaded from the CDN in templates, often with inline Tailwind configuration.
- Google Fonts and Material Symbols are loaded from external CDNs.
- Lucide is used on landing/auth pages.
- Custom styles are in `static/css/style.css` and `static/css/reelroots.css`.
- `static/js/script.js` handles dark mode, Lucide initialization, mobile menu behavior, smooth anchors, and navbar shadow.
- Many templates use inline CSS/JS rather than shared components.

Reusable pieces:

- `navbar.html` is included across application pages.
- `chatbox.html` is included on home.
- Shared static assets and media are present.

Responsive behavior:

- Strong mobile-oriented patterns: fixed bottom navigation, vertical reel cards, safe-area padding, snap scrolling, mobile container framing.
- Desktop navigation is added by media queries in the shared navbar.
- Upload and archive pages have desktop grids.
- The UI is not a component system; duplicated markup and hard-coded values are common.

Material issues:

- Many templates reference `/static/css/reelroots.css`; that file exists after materializing the full checkout, but Django test-client requests do not serve static files because only media is appended to URL patterns. `runserver`/staticfiles behavior should be tested separately.
- Many links are `#` placeholders.
- Several page actions are visual only.
- Chat inserts user text and model text with `innerHTML`, creating an XSS risk.
- Profile counts, badges, reels, and engagement are hard-coded.
- `script.js` assumes `nav` exists in its global scroll handler; on pages without a matching nav this can throw when scrolling.
- There is no accessibility review of focus behavior, video captions, reduced motion beyond CSS, keyboard interactions, or screen-reader state.

## 12. Deployment Architecture

The repository contains `vercel.json` for Vercel Python:

- build source: `ReelRoots/wsgi.py`;
- runtime: Python 3.12;
- catch-all route to the WSGI app;
- no explicit static/media strategy.

Settings currently configure:

- `DEBUG=True` by default;
- local SQLite by default;
- `STATIC_URL=/static/`, `STATIC_ROOT=static_root`, and `STATICFILES_DIRS=static`;
- `MEDIA_ROOT=static/img` and `/media/` only served by Django when `DEBUG=True`;
- secure cookies, HTTPS redirect, and HSTS only when `DEBUG=False`;
- environment-based `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS`.

README deployment guidance mentions managed PostgreSQL, `collectstatic`, migrations, and Supabase RLS, but no deployment automation, platform environment manifest, database URL handling, health check, logging, monitoring, worker, or media CDN configuration is present.

The Vercel runtime is configured for Python 3.12 while the audited local environment is Python 3.14.2 and Django 6.0.2. `requirements.txt` is unpinned and contains both `google-generativeai` and `google-genai`, plus unused Flask. Reproducible deployment is therefore weak.

## 13. Technical Debt

High priority:

- dual Django/Supabase data model;
- no canonical authentication/authorization boundary;
- public upload endpoint marks records verified;
- CSRF-exempt mutation endpoints;
- no upload validation, quotas, or malware scanning;
- no tests;
- synchronous external API calls inside page requests with no timeouts;
- broad wildcard imports and unused imports;
- large monolithic `views.py` containing UI, integration, auth, and domain logic;
- unversioned Supabase schema and RLS policies;
- unpinned dependencies;
- tracked generated static files and duplicate media trees;
- no structured logging, error monitoring, or background processing.

Medium priority:

- hard-coded content and metrics in templates;
- placeholder links/actions;
- missing logout and password reset;
- unused YouTube path and dormant AI helper;
- fixed Kenya-only assumptions in phone/SMS and prompts;
- no pagination/filter implementation on explore;
- no database indexes defined for likely feed/search fields;
- no form/serializer validation layer;
- no content ownership or audit history.

## 14. Missing Core Features

Against the stated product vision, the following are absent or only visual placeholders:

- first-party Reel model and archive-backed short-form feed;
- trusted source/provenance/citation model;
- URL/article/document/video submission for claim analysis;
- claim extraction and evidence-based verification workflow;
- confidence, uncertainty, verdict, and reviewer audit records;
- OCR/transcription and multilingual content support;
- community oral-history contribution workflow;
- contributor profiles, ownership, attribution, consent, and rights management;
- moderation queue and role-based archivist review;
- comments, likes, saves, shares, follows, reports, and notifications;
- search, real filtering, semantic discovery, and recommendations;
- archive-to-story-mode generation and PDF export;
- AI contextualization grounded in source material;
- user settings, logout, password recovery, and account security;
- analytics tied to persisted content;
- operations: jobs, retries, rate limits, observability, and backups.

## 15. Critical Risks

### Security

- `create_archive` is `@csrf_exempt`, has no authentication requirement, and allows anonymous public/verified publishing.
- `chatbot_response` is also `@csrf_exempt`, unauthenticated, and unthrottled.
- The upload form does not send a CSRF token.
- User and AI messages are rendered with `innerHTML` in `chatbox.html`.
- Supabase chooses `SUPABASE_SECRET_KEY` before the publishable key. This is acceptable only in strictly server-side code with correct RLS/operational controls; it must never reach browser code.
- User-supplied session identity is not tied to a verified Django `request.user` or validated Supabase JWT.
- No roles protect the custom admin dashboard.
- Production defaults fall back to an insecure Django secret and `DEBUG=True`.
- Secrets supplied in this conversation should be rotated if this environment or conversation is not treated as a secure secret-management boundary.

### Reliability

- Pexels and Supabase requests are synchronous and mostly lack explicit timeouts.
- `home()` assumes a successful JSON response and a first video file link.
- Pexels content may disappear or change independently of the feed.
- Local filesystem media is not durable on serverless deployment.
- The active upload path and archive-detail path do not share a database.

### Product trust

- Uploads are immediately marked verified without review.
- Stock footage is presented as historical/archival-style content without first-party provenance.
- The AI assistant is not grounded in source documents and has no citation record.
- “Archivist” and “verified” UI language currently overstates implemented controls.

## 16. Recommended Architecture

### Recommended baseline

Keep Django as the backend and orchestration layer for the next phase, keep the existing templates as the first client surface, and establish one canonical Postgres-backed domain model. Use Supabase for Postgres/Storage/Auth only where the boundary is explicit.

Recommended ownership of concerns:

- Django: domain models, request validation, permissions, moderation workflows, AI orchestration, verification orchestration, admin, and public APIs.
- Postgres/Supabase: canonical relational data with migrations and documented RLS.
- Supabase Storage: private source media and derived media with signed URLs and object metadata.
- Supabase Auth: end-user identity, with server-side JWT verification and a mapped internal profile/member record.
- Django admin or a dedicated staff surface: review, moderation, and audit actions.
- Background worker: media processing, OCR/transcription, AI generation, claim extraction, notifications, and retries.
- Provider adapters: Gemini, Africa’s Talking, Pexels, and YouTube behind small service interfaces with timeouts, retries, quotas, and structured errors.

### Suggested bounded domains

- `accounts`: identity mapping, profiles, roles, sessions, consent, phone verification.
- `archives`: records, metadata, collections, tags, languages, locations, source citations.
- `media`: uploads, variants, media processing, transcripts/OCR, storage objects, rights.
- `reels`: Reel records, archive/source references, captions, duration, feed ranking, engagement.
- `moderation`: submissions, review states, reviewer decisions, reports, audit log.
- `verification`: claims, evidence sources, extraction runs, verdicts, confidence, citations.
- `ai`: prompt/version records, retrieval, model usage, cached responses, safety/quotas.
- `notifications`: SMS/email/in-app events and delivery status.

### Required invariants

- A submitted record is never automatically `verified`.
- Every public Reel resolves to a source archive/media record or is explicitly labeled as an external/stock item.
- Every claim verdict stores its evidence and analysis version.
- Every mutation requires a verified identity and permission.
- Browser code never receives a Supabase secret/service key.
- Source media is private by default; derived public assets use explicit publication policy.

## 17. Recommended Implementation Roadmap

### Phase 0 — decisions and safety

1. Rotate the exposed credentials and place secrets in a deployment secret manager.
2. Decide whether Supabase Auth or Django auth is canonical; recommended: Supabase Auth for end users with a verified server-side identity bridge, Django staff roles for administration.
3. Decide whether Supabase Postgres or Django ORM owns the schema; recommended: one Postgres schema accessed through Django domain models, with Supabase Storage/Auth retained as services.
4. Freeze the current UI as a prototype baseline and add a small smoke-test suite.

### Phase 1 — foundation

1. Introduce structured settings for development, test, and production.
2. Pin dependencies and align Python/Django versions with Vercel.
3. Add canonical migrations and remove the active split between SQLite models and Supabase table CRUD.
4. Add authentication middleware, token verification, logout, password recovery, roles, and `login_required`/permission gates.
5. Add CSRF protection, upload limits, MIME/content validation, storage policies, rate limiting, and secure error handling.

### Phase 2 — trusted archive core

1. Implement archive ownership, citations, rights, languages, locations, provenance, and moderation states.
2. Build a contributor submission queue and archivist review UI.
3. Make archive detail, explore, upload, and admin use the same canonical data path.
4. Add search, pagination, filters, real counts, and empty/error states.

### Phase 3 — ReelRoots reels

1. Create Reel and engagement models linked to archive/media records.
2. Build a real feed from approved records; keep Pexels/YouTube as explicitly labeled external sources.
3. Add captions/transcripts, accessibility, source attribution, save/share/report, and moderation.
4. Add media processing/transcoding asynchronously.

### Phase 4 — AI contextualization

1. Add OCR/transcription and source chunking.
2. Add embeddings/vector retrieval with source citations.
3. Build contextual explanations that return evidence links and uncertainty.
4. Add model usage logging, caching, quotas, prompt versions, and human-review escalation.

### Phase 5 — verification engine

1. Accept URLs, articles, documents, and videos as verification submissions.
2. Extract claims and store them as first-class records.
3. Retrieve primary/secondary evidence, compare claims, and produce a structured analysis.
4. Add verdict taxonomy, confidence, citation requirements, reviewer override, and immutable audit history.

### Phase 6 — community and Africa’s Talking

1. Add oral-history consent, contributor attribution, community moderation, and notification preferences.
2. Integrate Africa’s Talking behind a provider service with normalized Kenyan/international numbers, delivery tracking, retries, opt-in/opt-out, and rate limits.
3. Add SMS verification or notifications only after the auth decision and compliance requirements are confirmed.

### Phase 7 — production operations

1. Configure managed Postgres, private storage, RLS, backups, migrations, and signed media URLs.
2. Add CI for checks, migrations, tests, dependency/security scans, and deployment.
3. Add structured logging, error monitoring, metrics, health checks, and job dashboards.
4. Run Django deployment checks with production environment variables and perform an end-to-end browser/security review.

## Ambiguities and Information Needed

The repository does not answer these questions and implementation should wait for decisions:

1. Is Supabase Auth the intended long-term identity system, or should Django auth replace it?
2. Is Supabase Postgres the source of truth, or should the Django models become canonical?
3. What exact Supabase RLS, Storage bucket, and Auth email-confirmation policies are configured outside the repository?
4. Which roles can submit, review, verify, publish, and administer records?
5. What rights/consent/licensing policy applies to oral histories, archival scans, stock footage, and derived AI media?
6. What verdict taxonomy and evidence standard should the verification engine use?
7. What Africa’s Talking SMS flows, sender IDs, phone format, opt-in requirements, and delivery behavior should be implemented?
8. Should external Pexels/YouTube content remain in the product, and how must it be labeled relative to first-party heritage records?
