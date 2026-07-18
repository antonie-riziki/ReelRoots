# ReelRoots

**Where History Lives Again**

ReelRoots is an AI-powered social archival platform that transforms traditional library and archive materials into interactive, visual, and engaging digital experiences.

Built for the Africa's Talking Women in Tech Hackathon (Libraries and Archival Services - Nairobi), ReelRoots bridges the gap between static archives and modern digital storytelling.

---

## 🌍 Problem

Libraries and archival institutions face several challenges:

- Poor discoverability of archival materials  
- Low youth engagement  
- Lack of contextual explanations  
- Language and accessibility barriers  
- Limited interactive and digital experiences  

ReelRoots reimagines how communities interact with historical records by making archives searchable, visual, conversational, and shareable.

---

## 🚀 Core Features

### 🔎 Smart Archive Explorer
- Advanced filtering (year, writer, event, location, type, language)
- Grid and timeline views
- Smart tagging system
- Related archive recommendations

### 🤖 AI Archive Assistant
- “Explain Simply” mode
- “Explain as Historian” mode
- Translation support
- Text-to-speech narration
- Contextual timeline insights

### 🎬 Archive Reels
- Convert any archive into a 30-second vertical reel
- AI-generated narration
- Shareable social-style format
- Swipe-based discovery feed

### 🎨 Story Mode
- Transform archives into illustrated slide/comic format
- Captioned panels
- Audio narration
- Downloadable PDF export

### 💬 Ask the Archive
- Chat with archival collections
- AI-generated contextual responses
- Source citation linking to original documents

### 🗣 Community Memory Layer
- Upload oral histories
- Add related photos
- Comment and contribute stories
- Cultural preservation through collective memory

### 🛠 Archivist Dashboard
- Archive upload
- OCR document processing
- Metadata editor
- Tag management
- Analytics dashboard

---

## 🧱 Tech Stack

**Frontend**
- Django templates with Tailwind CSS
- Responsive archive, story, reel, chat, and curator workspaces

**Backend**
- Django / Python
- Supabase for authentication, profiles, archive data, and media storage
- REST APIs for AI assistance and external media providers

**AI Layer**
- Embeddings for semantic search
- Large language model for summarization & Q&A
- Text-to-speech generation
- Image generation for story panels

---

## 📱 Design Principles

- Mobile-first
- Accessible (text resizing, high contrast, dark mode)
- Youth-friendly yet culturally respectful
- Clean, modern SaaS-style UI

---

## 🎯 Vision

ReelRoots transforms archives from static storage systems into living, interactive cultural experiences.

By merging AI, storytelling, and social engagement, we empower communities to rediscover and preserve their heritage in a format that resonates with modern audiences.

---

## 🧭 Product journeys

- **Discover:** Search and filter public records, move into a story, timeline, or reel, then save a source for later.
- **Understand:** Use the AI archive assistant to simplify, translate, narrate, and connect records to their original sources.
- **Contribute:** Submit a community memory with source media, structured metadata, and discoverability tags.
- **Steward:** Review submissions, enrich metadata, verify sources, and monitor the health of the archive.

## 🚢 Deployment checklist

Before publishing, set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` in the hosting environment. Run `python manage.py collectstatic` and `python manage.py migrate`, use a managed PostgreSQL database for production, and configure Supabase RLS policies for every public-facing table and storage bucket. Never commit `.env` or expose a Supabase secret key to the browser.

---

## 👥 Team

Built with passion for innovation, cultural preservation, and inclusive technology.

---

## 📄 License

MIT License

---

## ⭐ Support

If you like the project, consider giving it a star on GitHub and contributing to the future of digital heritage!
