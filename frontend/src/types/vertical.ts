import type { NameMasterImportPreview, NameMasterImportSummary } from "@/types/nameMaster";

export type VerticalDepartment = {
  id: number;
  name: string;
  is_active: boolean;
};

export type VerticalRecord = {
  id: number;
  name: string;
  department: VerticalDepartment;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type VerticalListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: VerticalRecord[];
};

export type VerticalListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
  department?: number;
};

export type VerticalWritePayload = {
  name: string;
  department_id: number;
  is_active?: boolean;
};

export type VerticalImportSummary = NameMasterImportSummary;
export type VerticalImportPreview = NameMasterImportPreview;
