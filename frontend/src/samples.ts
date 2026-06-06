// Preset demo campaigns. Images live in /public/samples (served at /samples/*).
// Sourced by the agent fleet from hotlink-friendly hosts (Unsplash/Pexels);
// target_box is a normalized [x,y,w,h] guess for the brand's intended focus
// (logo / product / CTA) — the region we score attention against.
export type Sample = {
  id: string;
  brand: string;
  campaign: string;
  img: string;
  target_box: [number, number, number, number];
  target_desc: string;
  tint: string; // accent used for the card placeholder + hover
  note?: string;
};

export const SAMPLES: Sample[] = [
  {
    id: "the-ordinary",
    brand: "The Ordinary",
    campaign: "Serum droppers — model hero",
    img: "/samples/the-ordinary.jpg",
    target_box: [0.29, 0.44, 0.3, 0.26],
    target_desc: "The two amber serum dropper bottles she's holding, lower-center.",
    tint: "#7A5C3E",
    note: "stock model shot (Pexels) standing in for a serum brand; the face is the attention thief, the product the target — the textbook redirect case (vetted: product 28%→34%, face 64%→58% on one edit).",
  },
  {
    id: "coca-cola",
    brand: "Coca-Cola",
    campaign: "Can — product hero",
    img: "/samples/coca-cola.jpg",
    target_box: [0.33, 0.28, 0.33, 0.64],
    target_desc: "The white Coca-Cola script wrapping the can, center-frame.",
    tint: "#E61A27",
  },
  {
    id: "nike",
    brand: "Nike",
    campaign: "“Just Do It” billboard, NYC",
    img: "/samples/nike.jpg",
    target_box: [0.3, 0.18, 0.45, 0.3],
    target_desc: "The swoosh + “JUST DO IT” on the building-side billboard.",
    tint: "#111111",
  },
  {
    id: "apple",
    brand: "Apple",
    campaign: "iPhone — product hero",
    img: "/samples/apple.jpg",
    target_box: [0.32, 0.2, 0.36, 0.62],
    target_desc: "The iPhone held center-frame over an open palm.",
    tint: "#1D1D1F",
  },
  {
    id: "mcdonalds",
    brand: "McDonald's",
    campaign: "Golden Arches sign",
    img: "/samples/mcdonalds.jpg",
    target_box: [0.26, 0.31, 0.52, 0.33],
    target_desc: "The Arches + red nameplate, centered on a dark ground.",
    tint: "#FFC72C",
  },
  {
    id: "red-bull",
    brand: "Red Bull",
    campaign: "Can on a creative desk",
    img: "/samples/red-bull.jpg",
    target_box: [0.34, 0.28, 0.26, 0.5],
    target_desc: "The can + twin-bull logo amid desk clutter (gadgets compete).",
    tint: "#001489",
  },
  {
    id: "spotify",
    brand: "Spotify",
    campaign: "App in hand",
    img: "/samples/spotify.jpg",
    target_box: [0.32, 0.28, 0.4, 0.5],
    target_desc: "The green Spotify UI on the phone screen, center-frame.",
    tint: "#1DB954",
  },
  {
    id: "pepsi",
    brand: "Pepsi",
    campaign: "Can on blue",
    img: "/samples/pepsi.jpg",
    target_box: [0.33, 0.3, 0.34, 0.45],
    target_desc: "The Pepsi globe on the can face, center against blue.",
    tint: "#004B93",
  },
  {
    id: "liquid-death",
    brand: "Liquid Death",
    campaign: "Tallboy can",
    img: "/samples/liquid-death.jpg",
    target_box: [0.3, 0.22, 0.36, 0.64],
    target_desc: "The can + gothic mark, upper-middle of the can body.",
    tint: "#0B0B0B",
    note: "stand-in can (no licensed Liquid Death image on free hosts)",
  },
];
