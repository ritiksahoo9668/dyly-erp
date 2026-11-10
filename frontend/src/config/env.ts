const configuredUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const env = {
  apiBaseUrl: configuredUrl.replace(/\/$/, ""),
};
