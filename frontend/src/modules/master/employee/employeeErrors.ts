import { extractApiError } from "@/utils/extractApiError";

export type EmployeeApiErrors = {
  message: string;
  fields: Record<string, string>;
  possibleDuplicate: boolean;
};

function firstText(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  return null;
}

/** Splits a DRF error payload into per-field messages (keys are API field names). */
export function parseEmployeeErrors(error: unknown): EmployeeApiErrors {
  const data = (error as { data?: { error?: { detail?: unknown } } } | null)?.data;
  const detail = data?.error?.detail;
  const fields: Record<string, string> = {};
  let possibleDuplicate = false;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    for (const [key, value] of Object.entries(detail as Record<string, unknown>)) {
      if (key === "possible_duplicate") {
        possibleDuplicate = true;
        continue;
      }
      const text = firstText(value);
      if (text) fields[key] = text;
    }
  }
  const message =
    fields.non_field_errors ??
    fields.detail ??
    (Object.keys(fields).length ? "" : extractApiError(error));
  return { message, fields, possibleDuplicate };
}
