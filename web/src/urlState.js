// Shareable state in the URL hash, e.g.
//
//   #map=9.5/37.2/-119.3&fire=3f9c0a1b2c3d&q=creek&years=2010-2019&states=US-CA
//
// Only what differs from the defaults is written, so plain views get short
// links. Everything read back is validated, since links get hand-edited and
// outlive the data they were made from.
import { REASON_CODES } from "./constants.js";
import { DURATION_STOPS, SIZE_STOPS } from "./filterLogic.js";
import { LIST_SCOPES } from "./settings.js";

const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
const CAUSES = Object.keys(REASON_CODES).map(Number);

export function parseHash(hash) {
  const params = new Map();
  for (const part of hash.replace(/^#/, "").split("&")) {
    if (!part) continue;
    const [key, ...rest] = part.split("=");
    try {
      params.set(decodeURIComponent(key), decodeURIComponent(rest.join("=")));
    } catch {
      // Mangled escapes: skip that one
    }
  }
  return params;
}

// Slashes and commas are left alone so links stay readable
const encodeValue = (value) =>
  encodeURIComponent(value).replace(/%2F/g, "/").replace(/%2C/g, ",");

export function serializeHash(params) {
  return [...params].map(([key, value]) => `${key}=${encodeValue(value)}`).join("&");
}

// map=zoom/lat/lng[/bearing/pitch]
export function parseView(text) {
  const [zoom, lat, lng, bearing = 0, pitch = 0] = (text ?? "").split("/").map(Number);
  if (![zoom, lat, lng, bearing, pitch].every(Number.isFinite)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180 || zoom < 0 || zoom > 24) return null;
  return { zoom, center: [lng, lat], bearing, pitch };
}

export function formatView({ zoom, center, bearing, pitch }) {
  const parts = [zoom.toFixed(2), center[1].toFixed(4), center[0].toFixed(4)];
  if (Math.round(bearing) !== 0 || Math.round(pitch) !== 0) {
    parts.push(Math.round(bearing), Math.round(pitch));
  }
  // Trim trailing zeros: 6.00 -> 6, 37.2000 -> 37.2
  return parts.map((p) => String(p).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "")).join("/");
}

// "1950-2020" -> [1950, 2020], within [min, max]
function parseRange(text, min, max) {
  const match = /^(\d+)-(\d+)$/.exec(text ?? "");
  if (!match) return null;
  const a = Math.min(max, Math.max(min, Number(match[1])));
  const b = Math.min(max, Math.max(min, Number(match[2])));
  return [Math.min(a, b), Math.max(a, b)];
}

// "a,b,c" -> the entries that are in `allowed`
function parseList(text, allowed, convert = (v) => v) {
  if (text == null) return null;
  const allowedSet = new Set(allowed);
  return [...new Set(text.split(",").map(convert))].filter((v) => allowedSet.has(v));
}

const sameList = (a, b) => a.length === b.length && a.every((v) => b.includes(v));
const formatRange = ([a, b]) => `${a}-${b}`;

// The URL parameters for the filters, leaving out anything at its default
export function filtersToParams(filters, defaults) {
  const params = new Map();
  const name = filters.name.trim();
  if (name) params.set("q", name);
  if (!sameList(filters.years, defaults.years)) params.set("years", formatRange(filters.years));
  if (!sameList(filters.size, defaults.size)) params.set("size", formatRange(filters.size));
  if (!sameList(filters.duration, defaults.duration)) params.set("burn", formatRange(filters.duration));
  if (filters.months.length) params.set("months", filters.months.join(","));
  if (filters.causes.length) params.set("causes", filters.causes.join(","));
  if (filters.regions.length) params.set("states", filters.regions.join(","));
  if (filters.countries.length) params.set("countries", filters.countries.join(","));
  if (!sameList(filters.kinds, defaults.kinds)) params.set("types", filters.kinds.join(","));
  if (!sameList(filters.sources, defaults.sources)) params.set("sources", filters.sources.join(","));
  return params;
}

// Filter state from URL parameters: the defaults, overridden by whatever the
// URL sets validly. `meta` (meta.json) says which places and sources exist.
export function paramsToFilters(params, defaults, meta) {
  const filters = structuredClone(defaults);
  const set = (key, value) => {
    if (value != null) filters[key] = value;
  };
  set("name", params.get("q"));
  set("years", parseRange(params.get("years"), defaults.years[0], defaults.years[1]));
  set("size", parseRange(params.get("size"), 0, SIZE_STOPS.acres.length - 1));
  set("duration", parseRange(params.get("burn"), 0, DURATION_STOPS.length - 1));
  set("months", parseList(params.get("months"), MONTHS, Number));
  set("causes", parseList(params.get("causes"), CAUSES, Number));
  set("regions", parseList(params.get("states"), meta.regions.map((r) => r.code)));
  set("countries", parseList(params.get("countries"), meta.countries.map((c) => c.code)));
  set("kinds", parseList(params.get("types"), ["wildfire", "prescribed"]));
  set("sources", parseList(params.get("sources"), meta.sources.map((s) => s.name)));
  return filters;
}

// Settings a link can carry: whether the list covers the view or everywhere,
// and 3D. Absent means "keep whatever this browser has".
export function settingsFromParams(params) {
  const settings = {};
  const list = params.get("list");
  if (list in LIST_SCOPES) settings.listScope = list;
  if (params.has("3d")) settings.terrain = params.get("3d") === "1";
  return settings;
}

export function settingsToParams(settings) {
  const params = new Map();
  if (settings.listScope !== "view") params.set("list", settings.listScope);
  if (settings.terrain) params.set("3d", "1");
  return params;
}
