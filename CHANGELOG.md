# Changelog — Mia Social

All notable changes to this project will be documented here.
Format: [version] — date — description

---

## [0.1.0] — 2026-07-05 — Foundation

### Added
- Repository structure (`backend/`, `frontend/`, `docs/`, `automation/`, `database/`, `scripts/`)
- `docs/ARCHITECTURE.md` — Worker-based architecture, OAuth & Webhook URL strategy per environment
- `docs/AGENTS.md` — 9 Workers defined: Vision, Copy, Media, Publish, Community, Analytics, Planner, Accessibility, Memory
- `docs/DATA_MODEL.md` — 7 models: User, Business, SocialAccount, Post, Media, Comment, Notification, AccessibilityProfile
- `docs/ONBOARDING.md` — 7-step onboarding flow, Meta OAuth (no manual token copy), natural language approval
- `docs/PRODUCT_PRINCIPLES.md` — 7 core principles (forgiving UX, natural conversation, <2min connection)
- `docs/ENVIRONMENT.md` — Environment variables, dev/production separation, Render from day one
- `docs/VISION.md` — placeholder
- `docs/USER_JOURNEY.md` — placeholder
- `docs/API.md` — placeholder
- `.gitignore`
- `.env.example`
- `CHANGELOG.md`

### Decisions
- No ngrok — Render used from day one for stable OAuth & Webhook URLs
- Architecture built around capabilities (Workers), not platforms
- All secrets via env only — no hardcoded tokens anywhere
- Development environment: `https://mia-dev.onrender.com`
- Production target: `https://app.miasocial.co.il`

---

## Upcoming — [0.2.0]

- Flask backend: `GET /health`, `GET /webhook`, `POST /webhook`
- Deploy to Render (`mia-social-backend`)
- Webhook verification against Meta
