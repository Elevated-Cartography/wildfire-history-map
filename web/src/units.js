// Fire sizes come from the pipeline in square meters
export const AREA_UNITS = {
  acres: { label: "Acres", symbol: "ac", squareMeters: 4046.8564224 },
  hectares: { label: "Hectares", symbol: "ha", squareMeters: 10_000 },
  km2: { label: "Square kilometers", symbol: "km²", squareMeters: 1_000_000 },
  mi2: { label: "Square miles", symbol: "mi²", squareMeters: 2_589_988.110336 },
};

// Matches MapLibre's ScaleControl units
export const DISTANCE_UNITS = {
  imperial: { label: "Miles and feet" },
  metric: { label: "Kilometers and meters" },
};

const FEET_PER_METER = 3.28084;
const METERS_PER_MILE = 1609.344;

// Fewer decimals as numbers get bigger: 2.35, 23.5, 235
function formatNumber(value) {
  const digits = value < 10 ? 2 : value < 100 ? 1 : 0;
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export function formatArea(squareMeters, unitKey) {
  if (squareMeters == null) {
    return "";
  }
  const unit = AREA_UNITS[unitKey];
  return `${formatNumber(squareMeters / unit.squareMeters)} ${unit.symbol}`;
}

export function formatDistance(meters, unitKey) {
  if (unitKey === "imperial") {
    const miles = meters / METERS_PER_MILE;
    return miles < 0.1
      ? `${Math.round(meters * FEET_PER_METER).toLocaleString()} ft`
      : `${formatNumber(miles)} mi`;
  }
  return meters < 1000 ? `${Math.round(meters)} m` : `${formatNumber(meters / 1000)} km`;
}
