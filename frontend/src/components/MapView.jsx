/**
 * MapView.jsx
 * -----------
 * Google Maps integration for the volunteer-matchmaker platform.
 *
 * What this does
 * ~~~~~~~~~~~~~~
 * - Fetches events from your backend API  (/api/events/map)
 * - Geocodes location_name strings → lat/lng via Google Geocoding API
 *   (since EventNLPExtractor gives location names, not coordinates)
 * - Renders severity circles (color + radius from build_map_marker output)
 * - Renders markers with InfoWindow popups showing breakdown + evidence
 * - Filter panel: by category and severity band
 * - Priority strip: top 5 urgent events highlighted
 * - Heatmap toggle using Google Maps Visualization library
 *
 * Backend contract
 * ~~~~~~~~~~~~~~~~
 * Your API should expose:  GET /api/events/map
 * Response shape (matches build_map_marker output from severity_engine.py):
 * {
 *   "events": [
 *     {
 *       "id": "...",
 *       "properties": {
 *         "location":       "Assam, India",
 *         "category":       "disaster_relief",
 *         "severity_score": 0.85,
 *         "severity_band":  "CRITICAL",
 *         "color":          "#E53E3E",
 *         "radius_m":       12000,
 *         "top_evidence":   ["Flooding has submerged 3 villages..."],
 *         "breakdown":      { "nlp_semantic": 0.9, ... },
 *         "warnings":       []
 *       }
 *     }
 *   ]
 * }
 *
 * Setup
 * ~~~~~
 * 1. npm install @react-google-maps/api
 * 2. Set REACT_APP_GOOGLE_MAPS_KEY in your .env
 * 3. Enable: Maps JavaScript API, Geocoding API, Visualization API
 *    (all covered by the $200/month free credit)
 *
 * Usage
 * ~~~~~
 *   import MapView from "./MapView";
 *   <MapView />
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
  GoogleMap,
  LoadScript,
  Marker,
  Circle,
  InfoWindow,
  HeatmapLayer,
} from "@react-google-maps/api";

// ─── Constants ───────────────────────────────────────────────────────────────

const GOOGLE_MAPS_KEY = process.env.REACT_APP_GOOGLE_MAPS_KEY || "";

// Load the visualization library for heatmap support
const LIBRARIES = ["visualization"];

// Default map center (Bengaluru — adjust for your use-case)
const DEFAULT_CENTER = { lat: 12.9716, lng: 77.5946 };
const DEFAULT_ZOOM = 5;

// Severity band → visual config (matches severity_engine.py bands)
const BAND_CONFIG = {
  CRITICAL: {
    color: "#E53E3E",
    pulseColor: "rgba(229,62,62,0.3)",
    label: "Critical",
    icon: "🔴",
  },
  MODERATE: {
    color: "#DD6B20",
    pulseColor: "rgba(221,107,32,0.2)",
    label: "Moderate",
    icon: "🟠",
  },
  LOW: {
    color: "#D69E2E",
    pulseColor: "rgba(214,158,46,0.15)",
    label: "Low",
    icon: "🟡",
  },
};

// Category display labels (matches category_config.py / CATEGORY_WEIGHTS)
const CATEGORY_LABELS = {
  disaster_relief:      "🌊 Disaster Relief",
  water_and_sanitation: "💧 Water & Sanitation",
  food:                 "🍚 Food",
  education:            "📚 Education",
  environment:          "🌿 Environment",
  animal_welfare:       "🐾 Animal Welfare",
};

// ─── Geocoding cache (in-memory for session) ─────────────────────────────────
// Avoids repeated API calls for the same location string.
// EventNLPExtractor gives us location names, not coordinates.
const geocodeCache = new Map();

async function geocodeLocation(locationName) {
  if (!locationName) return null;
  if (geocodeCache.has(locationName)) return geocodeCache.get(locationName);

  try {
    const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(
      locationName
    )}&key=${GOOGLE_MAPS_KEY}`;
    const res = await fetch(url);
    const data = await res.json();

    if (data.status === "OK" && data.results[0]) {
      const { lat, lng } = data.results[0].geometry.location;
      const coords = { lat, lng };
      geocodeCache.set(locationName, coords);
      return coords;
    }
  } catch (err) {
    console.warn(`Geocoding failed for "${locationName}":`, err);
  }
  return null;
}

// ─── Marker icon builder (severity-aware SVG pin) ────────────────────────────

function buildMarkerIcon(severityBand, isHighlighted) {
  const color = BAND_CONFIG[severityBand]?.color || "#888";
  const size = isHighlighted ? 44 : 34;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r="18" fill="${color}" fill-opacity="0.25" />
      <circle cx="22" cy="22" r="11" fill="${color}" />
      <circle cx="22" cy="22" r="5" fill="white" />
      ${isHighlighted ? `<circle cx="22" cy="22" r="20" fill="none" stroke="${color}" stroke-width="2.5" stroke-dasharray="4,3"/>` : ""}
    </svg>
  `;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    scaledSize: { width: size, height: size },
    anchor: { x: size / 2, y: size / 2 },
  };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

/** Breakdown table shown inside InfoWindow */
function BreakdownTable({ breakdown }) {
  const labels = {
    nlp_semantic:    "NLP Semantic",
    category_weight: "Category Weight",
    area_scale:      "Area Scale",
    recency_mult:    "Recency",
    doc_strength:    "Doc Strength",
    final_score:     "Final Score",
  };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
      <tbody>
        {Object.entries(breakdown)
          .filter(([k]) => labels[k])
          .map(([k, v]) => (
            <tr key={k} style={{ borderBottom: "1px solid #eee" }}>
              <td style={{ padding: "2px 6px", color: "#555" }}>{labels[k]}</td>
              <td style={{ padding: "2px 6px", fontWeight: 600, textAlign: "right" }}>
                {typeof v === "number" ? v.toFixed(3) : v}
              </td>
            </tr>
          ))}
      </tbody>
    </table>
  );
}

/** Score bar visualization */
function ScoreBar({ score, color }) {
  return (
    <div style={{ background: "#eee", borderRadius: 4, height: 6, margin: "6px 0" }}>
      <div
        style={{
          width: `${Math.round(score * 100)}%`,
          background: color,
          height: "100%",
          borderRadius: 4,
          transition: "width 0.5s ease",
        }}
      />
    </div>
  );
}

/** Filter panel (category + band toggles) */
function FilterPanel({ filters, onChange }) {
  const bandOrder = ["CRITICAL", "MODERATE", "LOW"];

  return (
    <div style={styles.filterPanel}>
      <p style={styles.filterTitle}>FILTER BY SEVERITY</p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        {bandOrder.map((band) => {
          const cfg = BAND_CONFIG[band];
          const active = filters.bands.includes(band);
          return (
            <button
              key={band}
              onClick={() => onChange("band", band)}
              style={{
                ...styles.filterChip,
                background: active ? cfg.color : "#1a1a2e",
                color: active ? "#fff" : "#888",
                border: `1px solid ${active ? cfg.color : "#333"}`,
              }}
            >
              {cfg.icon} {cfg.label}
            </button>
          );
        })}
      </div>

      <p style={styles.filterTitle}>FILTER BY CATEGORY</p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {Object.entries(CATEGORY_LABELS).map(([key, label]) => {
          const active = filters.categories.includes(key);
          return (
            <button
              key={key}
              onClick={() => onChange("category", key)}
              style={{
                ...styles.filterChip,
                background: active ? "#2d3748" : "#1a1a2e",
                color: active ? "#e2e8f0" : "#666",
                border: `1px solid ${active ? "#4a5568" : "#2d2d2d"}`,
              }}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Top 5 priority strip */
function PriorityStrip({ events, onSelect }) {
  const top5 = [...events]
    .sort((a, b) => b.properties.severity_score - a.properties.severity_score)
    .slice(0, 5);

  if (!top5.length) return null;

  return (
    <div style={styles.priorityStrip}>
      <span style={styles.priorityLabel}>⚡ TOP PRIORITY</span>
      {top5.map((ev, i) => (
        <button
          key={ev.id}
          onClick={() => onSelect(ev)}
          style={styles.priorityChip}
          title={ev.properties.location}
        >
          <span style={{ color: BAND_CONFIG[ev.properties.severity_band]?.color }}>
            #{i + 1}
          </span>{" "}
          {ev.properties.location}
          <span style={{ marginLeft: 6, opacity: 0.7 }}>
            {(ev.properties.severity_score * 100).toFixed(0)}%
          </span>
        </button>
      ))}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function MapView() {
  const [events, setEvents] = useState([]);          // raw from API (with coords)
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [filters, setFilters] = useState({
    bands:      ["CRITICAL", "MODERATE", "LOW"],
    categories: Object.keys(CATEGORY_LABELS),
  });
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [highlightedId, setHighlightedId] = useState(null);

  const mapRef = useRef(null);

  // ── Fetch + geocode events ────────────────────────────────────────────────
  useEffect(() => {
    async function load() {
      try {
        setLoading(true);

        // ── Replace with your actual API URL ──────────────────────────
        // The response should match build_map_marker() output from severity_engine.py
        const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8080";
        const res = await fetch(`${API_URL}/api/events/map`);

        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const data = await res.json();

        // Geocode each event's location_name → lat/lng
        const geocoded = await Promise.all(
          (data.events || []).map(async (ev) => {
            const coords = await geocodeLocation(ev.properties.location);
            return coords ? { ...ev, coords } : null;
          })
        );

        setEvents(geocoded.filter(Boolean));
      } catch (err) {
        setError(err.message);
        console.error("Map load error:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // ── Filter logic ──────────────────────────────────────────────────────────
  const visibleEvents = events.filter(
    (ev) =>
      filters.bands.includes(ev.properties.severity_band) &&
      filters.categories.includes(ev.properties.category)
  );

  // ── Heatmap data ──────────────────────────────────────────────────────────
  const heatmapData = visibleEvents.map((ev) => ({
    location: new window.google.maps.LatLng(ev.coords.lat, ev.coords.lng),
    weight: ev.properties.severity_score,
  }));

  // ── Filter toggle handler ─────────────────────────────────────────────────
  const handleFilterChange = useCallback((type, value) => {
    setFilters((prev) => {
      const key = type === "band" ? "bands" : "categories";
      const current = prev[key];
      const updated = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      // Prevent deselecting all
      if (updated.length === 0) return prev;
      return { ...prev, [key]: updated };
    });
  }, []);

  // ── Priority strip click → pan + highlight ────────────────────────────────
  const handlePrioritySelect = useCallback((ev) => {
    setSelectedEvent(ev);
    setHighlightedId(ev.id);
    mapRef.current?.panTo(ev.coords);
    mapRef.current?.setZoom(10);
  }, []);

  // ── Map load callback ─────────────────────────────────────────────────────
  const onMapLoad = useCallback((map) => {
    mapRef.current = map;
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <LoadScript googleMapsApiKey={GOOGLE_MAPS_KEY} libraries={LIBRARIES}>
      <div style={styles.container}>

        {/* ── Header ─────────────────────────────────────────────── */}
        <div style={styles.header}>
          <div>
            <h1 style={styles.headerTitle}>Crisis Intelligence Map</h1>
            <p style={styles.headerSub}>
              Real-time prioritization — severity derived from NLP scoring
            </p>
          </div>
          <div style={styles.headerControls}>
            <button
              onClick={() => setShowHeatmap((v) => !v)}
              style={{
                ...styles.controlBtn,
                background: showHeatmap ? "#4299e1" : "#2d3748",
              }}
            >
              {showHeatmap ? "🔥 Heatmap ON" : "🔥 Heatmap"}
            </button>
            <div style={styles.legend}>
              {Object.entries(BAND_CONFIG).map(([band, cfg]) => (
                <span key={band} style={styles.legendItem}>
                  <span style={{ ...styles.legendDot, background: cfg.color }} />
                  {cfg.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* ── Priority strip ──────────────────────────────────────── */}
        <PriorityStrip events={visibleEvents} onSelect={handlePrioritySelect} />

        {/* ── Main layout ─────────────────────────────────────────── */}
        <div style={styles.body}>

          {/* ── Filter panel ──────────────────────────────────────── */}
          <FilterPanel filters={filters} onChange={handleFilterChange} />

          {/* ── Map ───────────────────────────────────────────────── */}
          <div style={styles.mapWrap}>
            {loading && (
              <div style={styles.overlay}>
                <div style={styles.spinner} />
                <p style={{ color: "#888", marginTop: 12 }}>
                  Loading events & geocoding locations…
                </p>
              </div>
            )}
            {error && (
              <div style={styles.overlay}>
                <p style={{ color: "#E53E3E" }}>⚠ {error}</p>
                <p style={{ color: "#666", fontSize: 13 }}>
                  Check that your backend is running at{" "}
                  {process.env.REACT_APP_API_URL || "http://localhost:8080"}
                </p>
              </div>
            )}

            <GoogleMap
              mapContainerStyle={{ width: "100%", height: "100%" }}
              center={DEFAULT_CENTER}
              zoom={DEFAULT_ZOOM}
              onLoad={onMapLoad}
              options={MAP_OPTIONS}
            >
              {/* ── Heatmap layer ─────────────────────────────────── */}
              {showHeatmap && window.google && (
                <HeatmapLayer
                  data={heatmapData}
                  options={{ radius: 40, opacity: 0.6 }}
                />
              )}

              {/* ── Per-event circles + markers ───────────────────── */}
              {!showHeatmap &&
                visibleEvents.map((ev) => {
                  const { severity_score, severity_band, color, radius_m } =
                    ev.properties;
                  const isHighlighted = ev.id === highlightedId;

                  return (
                    <div key={ev.id}>
                      {/* Outer glow circle */}
                      <Circle
                        center={ev.coords}
                        radius={radius_m * 1.4}
                        options={{
                          fillColor: color,
                          fillOpacity: 0.06,
                          strokeOpacity: 0,
                          clickable: false,
                        }}
                      />
                      {/* Main severity circle */}
                      <Circle
                        center={ev.coords}
                        radius={radius_m}
                        options={{
                          fillColor: color,
                          fillOpacity: isHighlighted ? 0.35 : 0.22,
                          strokeColor: color,
                          strokeOpacity: 0.6,
                          strokeWeight: isHighlighted ? 2 : 1,
                          clickable: true,
                        }}
                        onClick={() => setSelectedEvent(ev)}
                      />
                      {/* Marker pin */}
                      <Marker
                        position={ev.coords}
                        icon={buildMarkerIcon(severity_band, isHighlighted)}
                        onClick={() => {
                          setSelectedEvent(ev);
                          setHighlightedId(ev.id);
                        }}
                        title={`${ev.properties.location} — ${(severity_score * 100).toFixed(0)}% severity`}
                      />
                    </div>
                  );
                })}

              {/* ── InfoWindow popup ──────────────────────────────── */}
              {selectedEvent && (
                <InfoWindow
                  position={selectedEvent.coords}
                  onCloseClick={() => {
                    setSelectedEvent(null);
                    setHighlightedId(null);
                  }}
                  options={{ maxWidth: 320 }}
                >
                  <div style={styles.infoWindow}>
                    {/* Band badge */}
                    <span
                      style={{
                        ...styles.bandBadge,
                        background:
                          BAND_CONFIG[selectedEvent.properties.severity_band]?.color,
                      }}
                    >
                      {BAND_CONFIG[selectedEvent.properties.severity_band]?.icon}{" "}
                      {selectedEvent.properties.severity_band}
                    </span>

                    <h3 style={styles.infoTitle}>
                      {selectedEvent.properties.location}
                    </h3>
                    <p style={styles.infoCategory}>
                      {CATEGORY_LABELS[selectedEvent.properties.category] ||
                        selectedEvent.properties.category}
                    </p>

                    {/* Score bar */}
                    <div style={{ marginBottom: 8 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 12,
                          color: "#555",
                        }}
                      >
                        <span>Severity Score</span>
                        <strong>
                          {(selectedEvent.properties.severity_score * 100).toFixed(1)}%
                        </strong>
                      </div>
                      <ScoreBar
                        score={selectedEvent.properties.severity_score}
                        color={
                          BAND_CONFIG[selectedEvent.properties.severity_band]?.color
                        }
                      />
                    </div>

                    {/* Score breakdown */}
                    {selectedEvent.properties.breakdown && (
                      <>
                        <p style={styles.infoSectionLabel}>Score Breakdown</p>
                        <BreakdownTable
                          breakdown={selectedEvent.properties.breakdown}
                        />
                      </>
                    )}

                    {/* Top evidence */}
                    {selectedEvent.properties.top_evidence?.length > 0 && (
                      <>
                        <p style={{ ...styles.infoSectionLabel, marginTop: 10 }}>
                          Key Evidence
                        </p>
                        {selectedEvent.properties.top_evidence
                          .slice(0, 2)
                          .map((sentence, i) => (
                            <p key={i} style={styles.evidenceLine}>
                              "{sentence.slice(0, 120)}
                              {sentence.length > 120 ? "…" : ""}"
                            </p>
                          ))}
                      </>
                    )}

                    {/* Warnings */}
                    {selectedEvent.properties.warnings?.length > 0 && (
                      <div style={styles.warningBox}>
                        ⚠{" "}
                        {selectedEvent.properties.warnings.join(" · ")}
                      </div>
                    )}

                    {/* Radius info */}
                    <p style={styles.radiusNote}>
                      Affected radius:{" "}
                      {(selectedEvent.properties.radius_m / 1000).toFixed(1)} km
                    </p>
                  </div>
                </InfoWindow>
              )}
            </GoogleMap>
          </div>

          {/* ── Stats sidebar ────────────────────────────────────── */}
          <StatsSidebar events={visibleEvents} />
        </div>
      </div>
    </LoadScript>
  );
}

// ─── Stats sidebar ────────────────────────────────────────────────────────────

function StatsSidebar({ events }) {
  const counts = {
    CRITICAL: events.filter((e) => e.properties.severity_band === "CRITICAL").length,
    MODERATE: events.filter((e) => e.properties.severity_band === "MODERATE").length,
    LOW:      events.filter((e) => e.properties.severity_band === "LOW").length,
  };
  const avgScore =
    events.length
      ? (
          events.reduce((s, e) => s + e.properties.severity_score, 0) /
          events.length
        ).toFixed(3)
      : "—";

  return (
    <div style={styles.sidebar}>
      <p style={styles.filterTitle}>OVERVIEW</p>
      {Object.entries(counts).map(([band, count]) => (
        <div key={band} style={styles.statRow}>
          <span style={{ color: BAND_CONFIG[band].color }}>
            {BAND_CONFIG[band].icon} {BAND_CONFIG[band].label}
          </span>
          <span style={{ fontWeight: 700, color: "#e2e8f0" }}>{count}</span>
        </div>
      ))}
      <div style={{ ...styles.statRow, marginTop: 12, borderTop: "1px solid #2d3748", paddingTop: 12 }}>
        <span style={{ color: "#888" }}>Avg Severity</span>
        <span style={{ fontWeight: 700, color: "#e2e8f0" }}>{avgScore}</span>
      </div>
      <div style={styles.statRow}>
        <span style={{ color: "#888" }}>Visible Events</span>
        <span style={{ fontWeight: 700, color: "#e2e8f0" }}>{events.length}</span>
      </div>
    </div>
  );
}

// ─── Google Maps style (dark theme) ──────────────────────────────────────────

const MAP_OPTIONS = {
  styles: [
    { elementType: "geometry", stylers: [{ color: "#0f1117" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#0f1117" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#746855" }] },
    { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#d59563" }] },
    { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#d59563" }] },
    { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#263c3f" }] },
    { featureType: "poi.park", elementType: "labels.text.fill", stylers: [{ color: "#6b9a76" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#1a1a2e" }] },
    { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#212121" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#2c2c44" }] },
    { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#1f1f38" }] },
    { featureType: "transit", elementType: "geometry", stylers: [{ color: "#2f3948" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#0a0e1a" }] },
    { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#515c6d" }] },
    { featureType: "water", elementType: "labels.text.stroke", stylers: [{ color: "#17263c" }] },
  ],
  disableDefaultUI: false,
  zoomControl: true,
  streetViewControl: false,
  mapTypeControl: false,
  fullscreenControl: true,
};

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: "#0a0e1a",
    fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
    color: "#e2e8f0",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 20px",
    background: "#0f1117",
    borderBottom: "1px solid #1e2535",
    flexShrink: 0,
  },
  headerTitle: {
    margin: 0,
    fontSize: 18,
    fontWeight: 700,
    letterSpacing: "0.03em",
    color: "#f7fafc",
  },
  headerSub: {
    margin: "2px 0 0",
    fontSize: 12,
    color: "#718096",
    letterSpacing: "0.02em",
  },
  headerControls: {
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  controlBtn: {
    padding: "6px 14px",
    borderRadius: 6,
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    color: "#fff",
    transition: "background 0.2s",
  },
  legend: {
    display: "flex",
    gap: 12,
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    fontSize: 12,
    color: "#a0aec0",
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: "50%",
  },
  priorityStrip: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 20px",
    background: "#0d1020",
    borderBottom: "1px solid #1e2535",
    overflowX: "auto",
    flexShrink: 0,
  },
  priorityLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: "#4299e1",
    whiteSpace: "nowrap",
    letterSpacing: "0.08em",
  },
  priorityChip: {
    padding: "4px 10px",
    background: "#161b2e",
    border: "1px solid #2d3748",
    borderRadius: 20,
    fontSize: 12,
    color: "#cbd5e0",
    cursor: "pointer",
    whiteSpace: "nowrap",
    transition: "border-color 0.2s",
  },
  body: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
  filterPanel: {
    width: 230,
    flexShrink: 0,
    padding: 16,
    background: "#0f1117",
    borderRight: "1px solid #1e2535",
    overflowY: "auto",
  },
  filterTitle: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.1em",
    color: "#4a5568",
    margin: "0 0 8px",
  },
  filterChip: {
    padding: "5px 10px",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 500,
    transition: "all 0.15s",
  },
  mapWrap: {
    flex: 1,
    position: "relative",
  },
  overlay: {
    position: "absolute",
    inset: 0,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    background: "rgba(10,14,26,0.85)",
    zIndex: 10,
  },
  spinner: {
    width: 36,
    height: 36,
    border: "3px solid #2d3748",
    borderTop: "3px solid #4299e1",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  sidebar: {
    width: 180,
    flexShrink: 0,
    padding: 16,
    background: "#0f1117",
    borderLeft: "1px solid #1e2535",
    overflowY: "auto",
  },
  statRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "5px 0",
    fontSize: 13,
  },
  // InfoWindow (Google renders this in a white popup; keep styles inline)
  infoWindow: {
    fontFamily: "'DM Sans', sans-serif",
    minWidth: 260,
    maxWidth: 300,
    padding: 4,
  },
  bandBadge: {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 700,
    color: "#fff",
    marginBottom: 6,
  },
  infoTitle: {
    margin: "0 0 2px",
    fontSize: 15,
    fontWeight: 700,
    color: "#1a202c",
  },
  infoCategory: {
    margin: "0 0 8px",
    fontSize: 12,
    color: "#718096",
  },
  infoSectionLabel: {
    margin: "8px 0 4px",
    fontSize: 11,
    fontWeight: 700,
    color: "#4a5568",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
  },
  evidenceLine: {
    margin: "4px 0",
    fontSize: 12,
    color: "#4a5568",
    fontStyle: "italic",
    lineHeight: 1.5,
  },
  warningBox: {
    marginTop: 8,
    padding: "5px 8px",
    background: "#fffbeb",
    borderRadius: 4,
    fontSize: 11,
    color: "#744210",
  },
  radiusNote: {
    marginTop: 8,
    fontSize: 11,
    color: "#a0aec0",
  },
};