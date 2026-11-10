import type { ImportJob } from "@/types/nameMaster";

export type MaterialGroupRecord = {
  id: number;
  sap_material_group_code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MaterialGroupListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: MaterialGroupRecord[];
};

export type MaterialGroupListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type MaterialGroupWritePayload = {
  sap_material_group_code: string;
  name: string;
  is_active?: boolean;
};

export type MaterialGroupImportJob = ImportJob;
