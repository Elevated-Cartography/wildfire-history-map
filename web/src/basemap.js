// Basemaps from OpenFreeMap: free, no API key or sign-up.
// See https://openfreemap.org/quick_start/
const OPENFREEMAP = "https://tiles.openfreemap.org/styles";

// Plain black background, for working without a network connection
const OFFLINE_STYLE = {
  version: 8,
  name: "Empty",
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: {
        "background-color": "rgb(0,0,0)",
      },
    },
  ],
};

export const BASEMAPS = {
  positron: { label: "Light", style: `${OPENFREEMAP}/positron` },
  liberty: { label: "Streets", style: `${OPENFREEMAP}/liberty` },
  bright: { label: "Bright", style: `${OPENFREEMAP}/bright` },
  dark: { label: "Dark", style: `${OPENFREEMAP}/dark` },
  fiord: { label: "Fiord", style: `${OPENFREEMAP}/fiord` },
  none: { label: "None (works offline)", style: OFFLINE_STYLE },
};

// Run `VITE_OFFLINE=1 npm run dev` to default to the offline style
export const DEFAULT_BASEMAP = import.meta.env.VITE_OFFLINE ? "none" : "positron";
