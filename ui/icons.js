// Platform marks, drawn here as simple shapes so the panel needs no picture
// from anywhere else. Colours are each platform's own.

const SHAPES = {
  youtube: '<rect x="1" y="4" width="22" height="16" rx="5" fill="#ff0033"/><path d="M10 8.5v7l6-3.5z" fill="#fff"/>',
  twitch: '<path d="M4 2 2.5 6v14h5v3h3l3-3h4l4.5-4.5V2z" fill="#9146ff"/><path d="M6 4h13.5v10L17 16.5h-4l-3 3v-3H6z" fill="#fff"/><path d="M11 7h2v5h-2zm5 0h2v5h-2z" fill="#9146ff"/>',
  facebook: '<circle cx="12" cy="12" r="11" fill="#1877f2"/><path d="M13.4 23v-8h2.7l.4-3.2h-3.1V9.8c0-.9.3-1.5 1.6-1.5h1.6V5.4a22 22 0 0 0-2.4-.1c-2.4 0-4 1.4-4 4.1v2.4H7.6V15h2.6v8z" fill="#fff"/>',
  webhook: '<circle cx="12" cy="12" r="11" fill="#10b981"/><path d="M7 13.5a3 3 0 1 0 4.2 2.8h5.3M12 6.2a3 3 0 0 0-1.6 5.5l-2.6 4.6M17 16.3a3 3 0 1 0-2.5-4.9L12 6.8" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round"/>',
  x: '<rect x="1" y="1" width="22" height="22" rx="5" fill="#0f1419"/><path d="M6 6h3.2l3.1 4.3L16 6h2l-4.8 5.5L18.6 18h-3.2l-3.3-4.6L8 18H6l5.2-5.9z" fill="#fff"/>',
  practice: '<circle cx="12" cy="12" r="11" fill="#f59e0b"/><path d="M8 7h5.5a3 3 0 0 1 0 6H10v4H8z" fill="#fff"/><path d="M10 9v2h3.4a1 1 0 0 0 0-2z" fill="#f59e0b"/>',
};

export const COLOURS = {
  youtube: "#ff0033", twitch: "#9146ff", facebook: "#1877f2", webhook: "#10b981", x: "#71767b",
  practice: "#f59e0b",
};

export function icon(platform, cls = "") {
  const shape = SHAPES[platform] || SHAPES.webhook;
  return `<svg class="${cls}" viewBox="0 0 24 24" aria-label="${platform}">${shape}</svg>`;
}
