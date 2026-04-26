# API Reference

Base URL (production): `https://api.ngo-platform.run.app`  
Base URL (local dev): `http://localhost:8080`

All endpoints require a Firebase Auth JWT in the `Authorization: Bearer <token>` header unless marked **public**.

Roles: `admin` · `ngo_manager` · `volunteer`

---

## Authentication — `POST /auth/*`

### `POST /auth/register/ngo`
Register a new NGO manager account.

**Role:** none (public registration; admin must grant Verified tag separately)

**Request body**
```json
{
  "email": "manager@ngo.org",
  "password": "...",
  "org_name": "Relief India",
  "org_registration_number": "MH/2019/0042",
  "allowed_categories": ["disaster_relief", "water_and_sanitation"],
  "custom_subtypes": {
    "disaster_relief": "industrial_fire_response"
  }
}
```

**Response `201`**
```json
{
  "ngo_id": "abc123",
  "firebase_uid": "...",
  "allowed_categories": ["disaster_relief", "water_and_sanitation"],
  "trust_score": null
}
```

> `trust_score` is always `null` in public responses. It is only returned to `admin` via the admin endpoints.

---

### `POST /auth/register/volunteer`
Register a new volunteer account.

**Role:** none (public)

**Request body**
```json
{
  "email": "volunteer@example.com",
  "password": "...",
  "full_name": "Priya Sharma",
  "age": 26,
  "phone": "+91-9876543210",
  "location": {
    "city": "Bengaluru",
    "state": "Karnataka",
    "lat": 12.9716,
    "lng": 77.5946
  },
  "willing_to_travel_km": 50,
  "skills": ["first_aid", "teaching"],
  "preferred_categories": ["disaster_relief", "education"],
  "strengths": "Fluent in Kannada and Hindi",
  "past_experience": "Red Cross volunteer 2022-2024"
}
```

**Response `201`**
```json
{
  "volunteer_id": "vol_xyz",
  "total_points": 0,
  "reliability_score_public": null
}
```

---

### `POST /auth/login`
Exchange email + password for a Firebase ID token. Thin proxy — prefer Firebase client SDK on the frontend.

---

## Events — `GET|POST /events/*`

### `POST /events`
Create a new event. Requires NGO trust score ≥ 0.40.

**Role:** `ngo_manager`

**Request** — multipart form:
- `data` (JSON part):
```json
{
  "title": "Flood relief — Assam villages",
  "category": "disaster_relief",
  "subtype": "flood",
  "location_name": "Dhubri, Assam",
  "lat": 26.02,
  "lng": 89.97,
  "affected_population": 12000,
  "affected_area_km2": 85,
  "num_volunteers_needed": 30,
  "manager_context": "Three embankments breached on 14 June...",
  "reported_at": "2025-06-14T08:00:00Z",
  "date": null
}
```
- `files[]` (optional): PDF / DOCX / MD supporting documents

**Response `201`**
```json
{
  "event_id": "evt_001",
  "severity_score": 0.74,
  "severity_band": "CRITICAL",
  "map_color": "#E53E3E",
  "radius_m": 5200,
  "tags": ["active"],
  "top_evidence": [
    "Three embankments breached, 12 000 people displaced.",
    "No access to food or clean water for 48 hours."
  ],
  "warnings": []
}
```

**Errors**
- `403` — NGO trust score below threshold (reason included in body)
- `422` — category not in NGO's allowed list

---

### `GET /events`
List all events. Supports filtering.  **Public.**

**Query params**

| Param | Type | Description |
|---|---|---|
| `category` | string | Filter by category key |
| `band` | string | `CRITICAL` \| `MODERATE` \| `LOW` |
| `tags` | string | Comma-separated: `active,ongoing` |
| `lat`, `lng`, `radius_km` | float | Bounding circle filter |
| `limit` | int | Default 50, max 200 |
| `cursor` | string | Firestore pagination cursor |

**Response `200`**
```json
{
  "events": [
    {
      "event_id": "evt_001",
      "title": "Flood relief — Assam villages",
      "category": "disaster_relief",
      "severity_band": "CRITICAL",
      "map_color": "#E53E3E",
      "radius_m": 5200,
      "lat": 26.02,
      "lng": 89.97,
      "tags": ["active"],
      "num_volunteers_needed": 30,
      "num_volunteers_assigned": 12,
      "date": null,
      "ngo_name": "Relief India",
      "ngo_verified": true
    }
  ],
  "next_cursor": "..."
}
```

> `severity_score` (the raw float) is not returned in list responses — only `severity_band`. Score is internal.

---

### `GET /events/{event_id}`
Full event detail. **Public.**

Returns everything from the list response plus `top_evidence`, `manager_context`, `affected_population`, `affected_area_km2`, and the open volunteer application list (anonymised).

---

### `PATCH /events/{event_id}`
Update event status, date, or volunteer count.

**Role:** `ngo_manager` (own events only) · `admin`

**Request body** — any subset of:
```json
{
  "tags": ["inactive"],
  "date": "2025-07-01",
  "num_volunteers_needed": 45
}
```

---

### `DELETE /events/{event_id}`
Soft-delete (marks as inactive). Hard-delete is admin-only.

**Role:** `ngo_manager` (own) · `admin`

---

## Volunteers — `GET|POST /volunteers/*`

### `GET /volunteers/me`
Fetch the current volunteer's profile and public points.

**Role:** `volunteer`

---

### `POST /volunteers/certificates`
Upload a skill certificate for verification.

**Role:** `volunteer`

**Request** — multipart form:
- `skill_key` (string): e.g. `first_aid`
- `file` (image/pdf): certificate file

**Response `200`**
```json
{
  "skill_key": "first_aid",
  "status": "verified",
  "issue_date": "2023-03-15",
  "expiry_date": "2026-03-15",
  "requires_manual": false
}
```

Possible statuses: `verified` · `pending_review` · `expired` · `rejected` · `self_declared` · `missing`

---

### `POST /volunteers/events/{event_id}/apply`
Apply to volunteer at a MODERATE or LOW severity event (open call).

**Role:** `volunteer`

**Response `200`**
```json
{ "application_id": "app_001", "status": "pending" }
```

---

### `POST /volunteers/assignments/{assignment_id}/confirm`
Confirm or decline an assignment (after being assigned to a CRITICAL event).

**Role:** `volunteer`

**Request body**
```json
{ "accepted": true }
```

If `accepted: false`, the system reassigns and the volunteer's reliability score is unaffected for a single decline (grace policy).

---

### `GET /volunteers/{volunteer_id}/points`
Public points and event history for a volunteer. **Public.**

```json
{
  "volunteer_id": "vol_xyz",
  "total_points": 148,
  "events_completed": 9,
  "recent_events": [
    { "event_id": "evt_001", "points_earned": 38, "category": "disaster_relief" }
  ]
}
```

---

## NGO management — `GET|PATCH /ngo/*`

### `GET /ngo/me`
Current NGO's profile and category config.

**Role:** `ngo_manager`

---

### `PATCH /ngo/me/subtypes`
Register or update the custom subtype for a category.

**Role:** `ngo_manager`

**Request body**
```json
{ "category": "food", "custom_subtype": "Diwali food drive" }
```

Max one custom subtype per category. Overwrites the previous value.

---

## Audit — `POST /audit/*`

### `POST /audit/events/{event_id}/ngo`
NGO submits post-event attendance and outcome.

**Role:** `ngo_manager`

```json
{
  "actual_volunteers": 24,
  "expected_volunteers": 30,
  "goal_met": true,
  "notes": "Reached all 3 villages; food packets distributed."
}
```

---

### `POST /audit/events/{event_id}/volunteer`
Volunteer submits a review of the NGO.

**Role:** `volunteer`

```json
{
  "star_rating": 4,
  "comment": "Well organised. Could have communicated pickup point earlier."
}
```

Star ratings are 1–5 (integer). `comment` is optional, max 500 chars.

---

## Admin — `GET|POST|PATCH /admin/*`

All endpoints require role `admin`.

### `GET /admin/ngos`
List all NGOs with their internal trust scores and flags.

### `GET /admin/ngos/{ngo_id}/trust`
Full trust breakdown for one NGO:
```json
{
  "composite_score": 0.63,
  "avg_review_score": 0.72,
  "avg_goal_completion": 0.80,
  "avg_attendance_ratio": 0.61,
  "activity_score": 0.52,
  "total_events_completed": 14,
  "is_verified": true,
  "is_suspended": false
}
```

### `PATCH /admin/ngos/{ngo_id}/verify`
Grant or revoke Verified tag.
```json
{ "verified": true, "note": "Checked registration docs manually." }
```

### `PATCH /admin/ngos/{ngo_id}/suspend`
Suspend an NGO (prevents login and event creation).
```json
{ "reason": "Suspected fraudulent event reports." }
```

### `PATCH /admin/ngos/{ngo_id}/trust/override`
Override composite trust score directly. Logged with admin UID and note.
```json
{ "new_score": 0.35, "note": "Penalising for repeated no-show events." }
```

### `GET /admin/certificates/queue`
List certificates pending manual review (where Vision OCR could not auto-verify).

### `PATCH /admin/certificates/{cert_id}`
Manually approve or reject a certificate.
```json
{ "approved": true, "note": "Verified via phone call with issuing body." }
```

---

## Map feed — `GET /map/markers`

Returns all active events as a GeoJSON FeatureCollection for the Leaflet frontend. **Public.**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [89.97, 26.02] },
      "properties": {
        "event_id": "evt_001",
        "title": "Flood relief — Assam villages",
        "category": "disaster_relief",
        "severity_band": "CRITICAL",
        "color": "#E53E3E",
        "radius_m": 5200,
        "ngo_name": "Relief India",
        "ngo_verified": true,
        "tags": ["active"],
        "num_volunteers_needed": 30
      }
    }
  ]
}
```

The raw `severity_score` float is **not** included in this response.

---

## Error format

All errors follow:
```json
{
  "detail": "Human-readable message.",
  "code": "MACHINE_READABLE_CODE"
}
```

Common codes: `TRUST_BELOW_THRESHOLD` · `CATEGORY_NOT_ALLOWED` · `CERT_EXPIRED` · `INSUFFICIENT_ROLE` · `NOT_FOUND`