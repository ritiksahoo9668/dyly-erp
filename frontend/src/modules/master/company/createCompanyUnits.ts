import type { UnitRecord, UnitWritePayload } from "@/types/unit";
import { extractApiError } from "@/utils/extractApiError";

type CreateUnit = (payload: UnitWritePayload) => { unwrap: () => Promise<UnitRecord> };

/** Creates each Unit under the Company; returns a combined error message, or null when all succeed. */
export async function createCompanyUnits(
  createUnit: CreateUnit,
  companyId: number,
  names: string[],
): Promise<string | null> {
  const failures: string[] = [];
  for (const name of names) {
    try {
      await createUnit({ name, company_id: companyId, is_active: true }).unwrap();
    } catch (err) {
      failures.push(`"${name}": ${extractApiError(err)}`);
    }
  }
  if (!failures.length) return null;
  return `These units could not be added: ${failures.join("; ")}`;
}
