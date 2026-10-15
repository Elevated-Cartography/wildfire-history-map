// The map filters with a MapLibre expression and the fire list with a
// JavaScript predicate. Run both over the same fires for lots of filter
// states and check they agree.
import { featureFilter } from "@maplibre/maplibre-gl-style-spec";
import { existsSync, readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import {
  DURATION_STOPS,
  SIZE_STOPS,
  buildFilterExpression,
  buildFilterPredicate,
} from "./filterLogic.js";

const SOURCES = ["calfire", "nifc-history", "wfigs-perimeters"];
const DATA_DIR = new URL("../public/data/", import.meta.url);

// fires.json is named with the build version; meta.json says which it is
function firesJsonPath() {
  const meta = new URL("meta.json", DATA_DIR);
  if (!existsSync(meta)) return null;
  const path = new URL(JSON.parse(readFileSync(meta, "utf8")).fire_list ?? "fires.json", DATA_DIR);
  return existsSync(path) ? path : null;
}

// Hand-written fires covering the awkward cases: missing properties,
// multi-state fires, codes that contain other codes
const EDGE_CASES = [
  { id: 1, year: 2020, fire_name: "Camp", size: 620_000_000, kind: "wildfire", source: "calfire", states: "|US-CA|", countries: "|US|", cause: 11, month: 11, duration_days: 17 },
  { id: 2, fire_name: "No year", size: 5_000, kind: "wildfire", source: "nifc-history" },
  { id: 3, year: 1999, fire_name: "", size: 0, kind: "prescribed", source: "nifc-history", states: "|US-NV|US-CA|" },
  { id: 4, year: 2021, fire_name: "BAJA", size: 1e9, kind: "wildfire", source: "wfigs-perimeters", states: "|MX-BCN|", countries: "|MX|", duration_days: 0.5, month: 7 },
  { id: 5, year: 2010, size: 40_000, kind: "wildfire", source: "calfire", cause: 14, duration_days: 400 },
];

function loadFires() {
  const fires = [...EDGE_CASES];
  const firesJson = firesJsonPath();
  if (firesJson) {
    // A sample of the real data too, if it's been built
    const { count, columns } = JSON.parse(readFileSync(firesJson, "utf8"));
    const step = Math.max(1, Math.floor(count / 3000));
    for (let i = 0; i < count; i += step) {
      const props = {};
      for (const [name, values] of Object.entries(columns)) {
        if (name !== "bbox" && values[i] != null) props[name] = values[i];
      }
      fires.push(props);
    }
  }
  return fires;
}

function toColumns(fires) {
  const names = new Set(fires.flatMap((f) => Object.keys(f)));
  return Object.fromEntries([...names].map((name) => [name, fires.map((f) => f[name] ?? null)]));
}

// A deterministic random number generator, so failures are reproducible
function rng(seed) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 2 ** 32;
    return seed / 2 ** 32;
  };
}

function randomState(random) {
  const pick = (list, chance) => list.filter(() => random() < chance);
  const range = (length) => {
    const a = Math.floor(random() * length);
    const b = Math.floor(random() * length);
    return random() < 0.5 ? [0, length - 1] : [Math.min(a, b), Math.max(a, b)];
  };
  const year = () => 1900 + Math.floor(random() * 127);
  const [y1, y2] = [year(), year()];
  return {
    name: random() < 0.2 ? ["camp", "fire", "complex", " Baja ", "zzz"][Math.floor(random() * 5)] : "",
    years: random() < 0.5 ? [1900, 2026] : [Math.min(y1, y2), Math.max(y1, y2)],
    size: range(SIZE_STOPS.acres.length),
    duration: range(DURATION_STOPS.length),
    countries: random() < 0.2 ? pick(["US", "MX", "CA"], 0.5) : [],
    regions: random() < 0.3 ? pick(["US-CA", "US-NV", "US-OR", "MX-BCN", "US-ID"], 0.4) : [],
    months: random() < 0.2 ? pick([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 0.3) : [],
    causes: random() < 0.2 ? pick([1, 2, 7, 9, 11, 14, 20], 0.4) : [],
    kinds: random() < 0.7 ? ["wildfire"] : pick(["wildfire", "prescribed"], 0.6),
    sources: random() < 0.7 ? SOURCES : pick(SOURCES, 0.6),
  };
}

describe("map filter and list filter agree", () => {
  const fires = loadFires();
  const columns = toColumns(fires);
  const random = rng(42);

  for (const areaUnit of Object.keys(SIZE_STOPS)) {
    test(`${areaUnit}: ${fires.length} fires x 150 random filter states`, () => {
      for (let n = 0; n < 150; n++) {
        const state = randomState(random);
        const expression = buildFilterExpression(state, areaUnit);
        const mapFilter = featureFilter(expression, "filter");
        const predicate = buildFilterPredicate(state, areaUnit);
        for (let i = 0; i < fires.length; i++) {
          const onMap = mapFilter.filter({ zoom: 10 }, { type: 3, properties: fires[i] });
          const inList = predicate(columns, i);
          if (onMap !== inList) {
            expect.fail(
              `Fire ${JSON.stringify(fires[i])}\nstate ${JSON.stringify(state)}\nmap: ${onMap}, list: ${inList}`,
            );
          }
        }
      }
    });
  }
});
