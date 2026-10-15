import { describe, expect, test } from "vitest";
import {
  filtersToParams,
  formatView,
  paramsToFilters,
  parseHash,
  parseView,
  serializeHash,
} from "./urlState.js";

const META = {
  regions: [{ code: "US-CA" }, { code: "US-NV" }, { code: "MX-BCN" }],
  countries: [{ code: "US" }, { code: "MX" }],
  sources: [{ name: "calfire" }, { name: "nifc-history" }, { name: "wfigs-perimeters" }],
};

const DEFAULTS = {
  name: "",
  years: [1900, 2026],
  size: [0, 7],
  duration: [0, 8],
  countries: [],
  regions: [],
  months: [],
  causes: [],
  kinds: ["wildfire"],
  sources: ["calfire", "nifc-history", "wfigs-perimeters"],
};

// What a link round trip does to a filter state
const viaUrl = (filters) => {
  const hash = serializeHash(filtersToParams(filters, DEFAULTS));
  return { hash, filters: paramsToFilters(parseHash(`#${hash}`), DEFAULTS, META) };
};

describe("filters in the URL", () => {
  test("defaults make an empty hash", () => {
    expect(viaUrl(DEFAULTS).hash).toBe("");
  });

  test("everything survives a round trip", () => {
    const filters = {
      name: "Creek & Co, 50%",
      years: [1950, 1959],
      size: [3, 7],
      duration: [1, 4],
      countries: ["US"],
      regions: ["US-CA", "MX-BCN"],
      months: [7, 8],
      causes: [1, 11],
      kinds: ["wildfire", "prescribed"],
      sources: ["calfire"],
    };
    const { hash, filters: back } = viaUrl(filters);
    expect(back).toEqual(filters);
    // Readable: commas aren't escaped
    expect(hash).toContain("states=US-CA,MX-BCN");
  });

  test("hand-edited and stale links are cleaned up", () => {
    const params = parseHash(
      "#years=2030-1800&size=9-2&months=7,13,x&causes=1,99&states=US-CA,US-ZZ&types=wildfire,bogus&sources=gone&q=%E0%A4",
    );
    const filters = paramsToFilters(params, DEFAULTS, META);
    expect(filters.years).toEqual([1900, 2026]); // clamped and reordered
    expect(filters.size).toEqual([2, 7]);
    expect(filters.months).toEqual([7]);
    expect(filters.causes).toEqual([1]);
    expect(filters.regions).toEqual(["US-CA"]);
    expect(filters.kinds).toEqual(["wildfire"]);
    expect(filters.sources).toEqual([]);
    expect(filters.name).toBe(""); // the mangled escape is skipped
  });
});

describe("map view in the URL", () => {
  test("round trip", () => {
    const view = { zoom: 9.5, center: [-119.3, 37.2], bearing: 20, pitch: 60 };
    expect(formatView(view)).toBe("9.5/37.2/-119.3/20/60");
    expect(parseView("9.5/37.2/-119.3/20/60")).toEqual(view);
  });

  test("flat views leave out bearing and pitch", () => {
    expect(formatView({ zoom: 6, center: [-119, 37], bearing: 0, pitch: 0 })).toBe("6/37/-119");
    expect(parseView("6/37/-119")).toEqual({ zoom: 6, center: [-119, 37], bearing: 0, pitch: 0 });
  });

  test("garbage is ignored", () => {
    for (const bad of [undefined, "", "abc", "6/37", "6/100/-119", "6/37/-200", "99/37/-119"]) {
      expect(parseView(bad)).toBeNull();
    }
  });
});
