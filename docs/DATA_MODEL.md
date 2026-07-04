# Data Model — Mia Social

> Models only. No DB implementation, no ORM. Pure schema definition.

---

## User
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| phone_number | string | WhatsApp identifier, unique |
| name | string | |
| role | enum | `owner` / `staff` |
| business_id | UUID | FK → Business |
| created_at | datetime | |
| updated_at | datetime | |

---

## Business
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| name | string | |
| whatsapp_number | string | |
| timezone | string | e.g. `Asia/Jerusalem` |
| plan | enum | `free` / `pro` |
| created_at | datetime | |
| updated_at | datetime | |

---

## SocialAccount
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| business_id | UUID | FK → Business |
| platform | enum | `instagram` / `facebook` |
| platform_account_id | string | ID from the platform |
| account_name | string | |
| access_token | string | encrypted at rest |
| token_expires_at | datetime | |
| status | enum | `active` / `expired` / `disconnected` |
| created_at | datetime | |

---

## Post
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| business_id | UUID | FK → Business |
| social_account_id | UUID | FK → SocialAccount |
| created_by | UUID | FK → User |
| caption | text | |
| status | enum | `draft` / `scheduled` / `published` / `failed` |
| scheduled_at | datetime | nullable |
| published_at | datetime | nullable |
| platform_post_id | string | returned by Meta API after publish |
| created_at | datetime | |
| updated_at | datetime | |

---

## Media
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| post_id | UUID | FK → Post |
| type | enum | `image` / `video` / `reel` / `story` |
| url | string | storage URL |
| mime_type | string | e.g. `image/jpeg` |
| size_bytes | integer | |
| width | integer | pixels, nullable |
| height | integer | pixels, nullable |
| duration_seconds | integer | video only, nullable |
| created_at | datetime | |

---

## Comment
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| post_id | UUID | FK → Post |
| platform_comment_id | string | ID from the platform |
| author_name | string | |
| text | text | |
| sentiment | enum | `positive` / `neutral` / `negative` / `unknown` |
| replied | boolean | default false |
| reply_text | text | nullable |
| created_at | datetime | |

---

## Notification
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → User |
| type | enum | `post_published` / `post_failed` / `comment_received` / `token_expired` |
| message | string | human-readable text |
| read | boolean | default false |
| created_at | datetime | |

---

## AccessibilityProfile
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → User, unique |
| language | string | `he` / `en` / `ar` |
| font_size | enum | `normal` / `large` |
| high_contrast | boolean | default false |
| rtl | boolean | default true |
| created_at | datetime | |
| updated_at | datetime | |

---

## Relationships Summary

```
Business ──< User
Business ──< SocialAccount
Business ──< Post
Post ──< Media
Post ──< Comment
User ──< Notification
User ──1 AccessibilityProfile
```
