import { useMemo } from "react";
import {
  useGetCompaniesQuery,
  useGetDepartmentsQuery,
  useGetDesignationsQuery,
  useGetDivisionsQuery,
  useGetFacilitiesQuery,
  useGetVerticalsQuery,
} from "@/app/store/api";
import type { SearchableSelectOption } from "@/components/common/SearchableSelect";

const LOOKUP_PAGE_SIZE = 500;

type Named = { id: number; name: string; is_active: boolean };

/**
 * Options for a Master dropdown. Inactive records are hidden unless currently selected,
 * so editing an Employee linked to a deactivated Master still shows its value.
 */
export function toOptions(
  records: Named[] | undefined,
  { activeOnly = true, keep }: { activeOnly?: boolean; keep?: number | "" } = {},
): SearchableSelectOption[] {
  return (records ?? [])
    .filter((record) => !activeOnly || record.is_active || record.id === keep)
    .map((record) => ({
      value: record.id,
      label: record.name,
      hint: record.is_active ? undefined : "Inactive",
    }));
}

/** Masters without a parent (loaded once and shared by filters and the form). */
export function useEmployeeMasters() {
  const params = { lookup: true, page_size: LOOKUP_PAGE_SIZE };
  const departments = useGetDepartmentsQuery(params).data?.results;
  const designations = useGetDesignationsQuery(params).data?.results;
  const companies = useGetCompaniesQuery(params).data?.results;
  const divisions = useGetDivisionsQuery(params).data?.results;
  const facilities = useGetFacilitiesQuery(params).data?.results;
  return useMemo(
    () => ({ departments, designations, companies, divisions, facilities }),
    [departments, designations, companies, divisions, facilities],
  );
}

/** Verticals of one Department (Vertical Master is owned by Department). */
export function useDepartmentVerticals(departmentId: number | "") {
  const { data, isFetching } = useGetVerticalsQuery(
    {
      lookup: true,
      department: departmentId === "" ? undefined : departmentId,
      page_size: LOOKUP_PAGE_SIZE,
    },
    { skip: departmentId === "" },
  );
  return { verticals: departmentId === "" ? [] : (data?.results ?? []), isFetching };
}
