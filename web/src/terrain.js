// Elevation tiles from Mapterhorn (https://mapterhorn.com): global, free, no
// API key. The TileJSON brings its own attribution, which MapLibre shows.
export const TERRAIN_TILEJSON = "https://tiles.mapterhorn.com/tilejson.json";
// Mapterhorn covers the whole world to z12, and only some regions beyond that.
// The TileJSON doesn't say so, so without this MapLibre asks for z13+ tiles
// that 404 outside those regions. Past z12 the tiles get stretched instead.
export const TERRAIN_MAX_ZOOM = 12;

// How much to stretch elevations. At true scale, mountains look surprisingly
// flat from the zoom levels most fires are seen at.
export const TERRAIN_EXAGGERATIONS = {
  1: "1× (true scale)",
  1.5: "1.5×",
  2: "2×",
  3: "3×",
};

// How far the map tilts when 3D is switched on, and the most you can tilt it
export const TERRAIN_PITCH = 60;
export const TERRAIN_MAX_PITCH = 75;
