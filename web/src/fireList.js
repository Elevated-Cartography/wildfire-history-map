// fires.json from `surtr build`: every fire's properties (the same ones the
// tiles have) plus its bounding box, one array per property. Fires are
// referred to by their index into those arrays.

export async function loadFireList(url) {
  const response = await fetch(url);
  const { count, columns } = await response.json();
  const indexById = new Map();
  columns.id.forEach((id, i) => indexById.set(id, i));
  // `key` is the stable ID used in links (`id` changes with every data build)
  const indexByKey = new Map();
  columns.key.forEach((key, i) => indexByKey.set(key, i));
  // For searching by name
  const lowerNames = columns.fire_name.map((name) => (name ?? "").toLowerCase());
  return { count, columns, indexById, indexByKey, lowerNames };
}

// [west, south, east, north] boxes overlap
export function bboxesOverlap(a, b) {
  return a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];
}
