const FALLBACK = "Something went wrong. Please try again.";

function firstString(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (Array.isArray(value) && typeof value[0] === "string" && value[0].trim()) {
    return value[0];
  }
  return null;
}

function firstFieldMessage(detail: unknown): string | null {
  if (!detail || typeof detail !== "object") return null;
  for (const value of Object.values(detail as Record<string, unknown>)) {
    const message = firstString(value);
    if (message) return message;
  }
  return null;
}

/**
 * Parse DYLY ERP API error payloads, including the wrapped shape:
 * `{ error: { status_code, detail: string | { field: string[] } } }`
 */
export function extractApiError(error: unknown): string {
  if (!error || typeof error !== "object" || !("data" in error)) {
    return FALLBACK;
  }
  const data = (error as { data?: Record<string, unknown> }).data;
  if (!data) return FALLBACK;

  const topDetail = firstString(data.detail);
  if (topDetail) return topDetail;

  const topField = firstFieldMessage(data);
  if (topField) return topField;

  const nested = data.error as { detail?: unknown } | undefined;
  if (nested) {
    const nestedDetail = firstString(nested.detail);
    if (nestedDetail) return nestedDetail;
    const nestedField = firstFieldMessage(nested.detail);
    if (nestedField) return nestedField;
  }

  return FALLBACK;
}
