# Scoring Logic

This document explains the two scoring systems in the platform: **severity scoring** (how urgent is a community need?) and **trust / points scoring** (how reliable are the actors?).

---

## 1. Severity scoring

Implemented in `nlp/severity_engine.py`.

### Formula

```
final_score = nlp_score × category_weight × doc_strength × area_scale × recency_mult
```

All five components produce values in [0, 1]. The final score is clamped to [0, 1] and maps to three bands used for map colouring:

| Band | Score range | Map colour |
|---|---|---|
| CRITICAL | ≥ 0.70 | Red `#E53E3E` |
| MODERATE | ≥ 0.40 | Orange `#DD6B20` |
| LOW | < 0.40 | Yellow `#D69E2E` |

Map circles are also size-coded by affected area (see `build_map_marker()`).

---

### Component 1 — NLP semantic score

The document text is embedded using **Vertex AI `text-embedding-005`** (or TF-IDF in offline mode). Two centroid anchor vectors are pre-computed at engine startup:

- **High-severity centroid** — average of 15 phrases such as "urgent immediate life-threatening emergency", "people are dying", "no access to clean drinking water cholera outbreak".
- **Low-severity centroid** — average of 5 phrases such as "routine maintenance scheduled activity", "awareness campaign educational workshop".

The document embedding is compared to both centroids via cosine similarity:

```
high_sim = cosine(doc_vec, high_anchor)
low_sim  = cosine(doc_vec, low_anchor)
nlp_score = (high_sim − low_sim + 1.0) / 2.0   # maps [−1, 1] → [0, 1]
```

Long documents are split into 2 000-character chunks, each embedded separately, then mean-pooled into a single document vector.

**Explainability:** the top 3 sentences most similar to the high-severity centroid are returned in `SeverityResult.top_evidence` for audit purposes.

---

### Component 2 — Category weight

Each of the six event categories carries a fixed base urgency weight reflecting domain knowledge. These are defined in `nlp/category_config.py` and referenced by the engine.

| Category | Base weight |
|---|---|
| Disaster Relief | 1.00 |
| Water & Sanitation | 0.90 |
| Food Security | 0.85 |
| Education | 0.55 |
| Environment | 0.50 |
| Animal Welfare | 0.45 |
| Custom / unknown | 0.60 |

A document with strong NLP signals can still outscore a weak disaster_relief submission — the category weight scales the NLP score but does not override it.

---

### Component 3 — Area scale factor

Larger affected areas amplify the score. The factor is in [0.5, 1.5] — it can push the score up (large disaster) or slightly down (very localised need). Prefers population estimate; falls back to area in km².

```python
if population:
    raw = log10(population) / 5.0
elif area_km2:
    raw = log10(area_km2) / 4.0
else:
    return 1.0   # neutral — no data

area_scale = clamp(0.5 + raw, 0.5, 1.5)
```

Reference points: 1 000 people → 1.1×, 10 000 → 1.3×, 100 000 → 1.5× (capped).

---

### Component 4 — Recency multiplier

Events reported recently are more likely to represent active needs. The multiplier is 1.0 for the first 90 days, then decays exponentially with a half-life of 180 days, floored at 0.15.

```
if age_days ≤ 90:
    recency_mult = 1.0
else:
    recency_mult = max(0.5 ^ ((age_days − 90) / 180), 0.15)
```

Reference points:

| Document age | Multiplier |
|---|---|
| < 3 months | 1.00 |
| 6 months | 0.71 |
| 1 year | 0.50 |
| 2 years | 0.25 |
| > ~2.5 years | 0.15 (floor) |

Documents with no date get a 0.75 multiplier with a warning in `SeverityResult.warnings`.

---

### Component 5 — Document strength

A heuristic proxy for how much supporting evidence the NGO provided. Ranges from 0.50 (bare minimum) to 1.00 (well-evidenced).

```
strength = 0.50
         + 0.20 × min(char_count / 5000, 1.0)       # content volume
         + 0.20 × min(numeric_mentions / 5, 1.0)     # quantitative claims
         + 0.10 × min(num_docs / 3, 1.0)             # number of files
```

`numeric_mentions` counts regex matches of numbers followed by units like "people", "families", "km", "cases", "deaths", etc.

---

### Worked example

| Component | Value | Notes |
|---|---|---|
| NLP score | 0.81 | Cholera outbreak, deaths mentioned |
| Category weight | 0.90 | Water & Sanitation |
| Area scale | 1.15 | 800 people affected |
| Recency mult | 0.50 | 1-year-old document |
| Doc strength | 0.78 | 2 docs, some numbers |
| **Final** | **0.81 × 0.90 × 1.15 × 0.50 × 0.78 = 0.26** | LOW band |

The same event with a current document would score ~0.52 (MODERATE). This illustrates why recency matters: a year-old cholera report may already be resolved.

---

## 2. NGO trust score

Implemented in `nlp/trust_scorer.py`. **Internal only — visible to admins, never exposed in any public API.**

### Formula

```
trust = 0.40 × avg_review_score
      + 0.25 × avg_goal_completion
      + 0.20 × avg_attendance_ratio
      + 0.15 × activity_score
```

Each component is updated with **exponential moving average** (α = 0.25) after each post-event audit, so early poor performance fades over time:

```
new_value = 0.25 × audit_result + 0.75 × previous_value
```

### Component definitions

**`avg_review_score`** — volunteer star ratings (1–5) normalised to [0, 1]: `(stars − 1) / 4`. Weight 0.40 because volunteer experience is the strongest signal of NGO quality.

**`avg_goal_completion`** — fraction of events where the NGO marked the stated goal as met. Weight 0.25.

**`avg_attendance_ratio`** — `actual_volunteers / expected_volunteers`, capped at 1.0. Measures whether the NGO's estimates are realistic and whether their events are run well enough to retain volunteers. Weight 0.20.

**`activity_score`** — log-scaled count of *completed* events. Creating events without completing them does not improve this score. Weight 0.15. Formula: `log(n + 1) / log(101)` — saturates near 1.0 at ~100 completed events.

### Event creation gate

NGOs with `composite_score < 0.40` cannot create new events. The response from `can_create_event()` includes a human-readable reason shown to the NGO manager.

New NGOs start at 0.50 across all components (neutral prior) to avoid penalising them before they have any history. The gate is therefore open by default — it closes if audits go badly.

### Verified tag

Admin-only. Not awarded automatically by score. Set via `admin_set_verified(True)`. An informational `TRUST_VERIFIED_SIGNAL = 0.70` constant exists for admin dashboards to surface high-trust NGOs, but the Verified tag itself requires human judgement.

---

## 3. Volunteer points

Also in `nlp/trust_scorer.py`. **Public — shown on volunteer profiles.**

### Points per event

| Action | Points |
|---|---|
| Showed up | 10 |
| Event goal was met | 15 |
| CRITICAL severity event | +10 bonus |
| MODERATE severity event | +5 bonus |
| Verified skill was used | +5 |
| Accepted assignment within 24h | +3 |
| Received 5-star NGO review | +5 |

Maximum possible per event: 48 points (all bonuses, critical event, perfect review).

### Reliability score

`reliability = events_attended / events_assigned` — used internally by the matching engine, not shown publicly. Volunteers below 0.60 are deprioritised in matching and flagged for manual review before auto-assignment to CRITICAL events.

---

## 4. Entity extraction confidence

`nlp/event_nlp_extractor.py` notes the `extraction_method` field in `ExtractedEntities`:

- `"gcp_nl"` — Cloud Natural Language API was used; location entities are high-confidence.
- `"regex"` — offline fallback; population numbers are reliable, location names are heuristic.

The severity engine treats both equally — the extracted population feeds `area_scale` and the urgency level feeds into routing logic, but neither directly alters the composite score formula (the NLP score already captures urgency from the raw text).