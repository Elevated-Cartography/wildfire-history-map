// Turns the filter state into the two things that apply it: a MapLibre filter
// expression for the map, and a JavaScript predicate over fires.json for the
// fire list. They have to agree, so they live side by side, and
// filterLogic.test.js checks them against each other. No Vue in here, so the
// test can run in plain Node.
import { AREA_UNITS } from "./units.js";

export const MIN_YEAR = 1900;

// Size and burn time sliders move between these stops (fires range from a
// fraction of an acre to over a million, so the steps grow by 10x). The last
// stop means "no limit".
export const SIZE_STOPS = {
  acres: [0, 1, 10, 100, 1_000, 10_000, 100_000, Infinity],
  hectares: [0, 1, 10, 100, 1_000, 10_000, 100_000, Infinity],
  km2: [0, 0.01, 0.1, 1, 10, 100, 1_000, Infinity],
  mi2: [0, 0.01, 0.1, 1, 10, 100, 1_000, Infinity],
};
export const DURATION_STOPS = [
  { days: 0, label: "0" },
  { days: 1, label: "1 day" },
  { days: 2, label: "2 days" },
  { days: 7, label: "1 week" },
  { days: 14, label: "2 weeks" },
  { days: 30, label: "1 month" },
  { days: 90, label: "3 months" },
  { days: 180, label: "6 months" },
  { days: Infinity, label: "any" },
];

// The size and burn time ranges a filter state asks for, in the data's units
// (square meters, days). 0 and Infinity at the ends mean no limit.
function ranges(state, areaUnit) {
  const sizeStops = SIZE_STOPS[areaUnit];
  const squareMeters = AREA_UNITS[areaUnit].squareMeters;
  return {
    size: [sizeStops[state.size[0]] * squareMeters, sizeStops[state.size[1]] * squareMeters],
    duration: [DURATION_STOPS[state.duration[0]].days, DURATION_STOPS[state.duration[1]].days],
  };
}

// --- MapLibre expression ----------------------------------------------------

// Range filter on a numeric property. Features without the property count as
// -1, so they drop out whenever the range is narrowed at all.
function rangeExpression(property, [min, max]) {
  const value = ["number", ["get", property], -1];
  const conditions = [];
  if (min > 0) conditions.push([">=", value, min]);
  if (max !== Infinity) conditions.push(["<=", value, max]);
  if (min === 0 && max !== Infinity) conditions.push([">=", value, 0]);
  return conditions;
}

// Matches when a "|A|B|"-packed property (see delimited() in build.py)
// contains any of the codes
function containsAnyExpression(property, codes) {
  const haystack = ["coalesce", ["get", property], ""];
  return ["any", ...codes.map((code) => ["in", `|${code}|`, haystack])];
}

export function buildFilterExpression(state, areaUnit) {
  const { size, duration } = ranges(state, areaUnit);
  // Fires with no known year come through as 0, so they're always filtered out
  const year = ["number", ["get", "year"], 0];
  const expression = [
    "all",
    [">=", year, state.years[0]],
    ["<=", year, state.years[1]],
    ...rangeExpression("size", size),
    ...rangeExpression("duration_days", duration),
    ["in", ["get", "kind"], ["literal", [...state.kinds]]],
    ["in", ["get", "source"], ["literal", [...state.sources]]],
  ];

  const name = state.name.trim().toLowerCase();
  if (name) {
    expression.push(["in", name, ["downcase", ["coalesce", ["get", "fire_name"], ""]]]);
  }
  if (state.countries.length > 0) {
    expression.push(containsAnyExpression("countries", state.countries));
  }
  if (state.regions.length > 0) {
    expression.push(containsAnyExpression("states", state.regions));
  }
  if (state.months.length > 0) {
    expression.push(["in", ["number", ["get", "month"], 0], ["literal", [...state.months]]]);
  }
  if (state.causes.length > 0) {
    expression.push(["in", ["get", "cause"], ["literal", [...state.causes]]]);
  }
  return expression;
}

// --- JavaScript predicate ---------------------------------------------------

const numberOr = (value, fallback) => (typeof value === "number" ? value : fallback);

function rangeCheck(property, [min, max]) {
  if (min === 0 && max === Infinity) return null;
  return (columns, i) => {
    // Missing values are -1, so they fail the minimum (which is at least 0)
    const value = numberOr(columns[property][i], -1);
    return value >= min && value <= max;
  };
}

function containsAnyCheck(property, codes) {
  const needles = codes.map((code) => `|${code}|`);
  return (columns, i) => {
    const haystack = columns[property][i] ?? "";
    return needles.some((needle) => haystack.includes(needle));
  };
}

// Returns (columns, i) => whether fire i in fires.json's columns matches
export function buildFilterPredicate(state, areaUnit) {
  const { size, duration } = ranges(state, areaUnit);
  const [minYear, maxYear] = state.years;
  const kinds = new Set(state.kinds);
  const sources = new Set(state.sources);
  const checks = [
    (columns, i) => {
      const year = numberOr(columns.year[i], 0);
      return year >= minYear && year <= maxYear;
    },
    rangeCheck("size", size),
    rangeCheck("duration_days", duration),
    (columns, i) => kinds.has(columns.kind[i]),
    (columns, i) => sources.has(columns.source[i]),
  ];

  const name = state.name.trim().toLowerCase();
  if (name) {
    checks.push((columns, i) => (columns.fire_name[i] ?? "").toLowerCase().includes(name));
  }
  if (state.countries.length > 0) {
    checks.push(containsAnyCheck("countries", state.countries));
  }
  if (state.regions.length > 0) {
    checks.push(containsAnyCheck("states", state.regions));
  }
  if (state.months.length > 0) {
    const months = new Set(state.months);
    checks.push((columns, i) => months.has(numberOr(columns.month[i], 0)));
  }
  if (state.causes.length > 0) {
    const causes = new Set(state.causes);
    checks.push((columns, i) => causes.has(columns.cause[i]));
  }

  const active = checks.filter(Boolean);
  return (columns, i) => active.every((check) => check(columns, i));
}
