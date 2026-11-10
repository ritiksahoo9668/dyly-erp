import type { ImportJob } from "@/types/nameMaster";

export type MaterialTypeRecord = {
  id: number;
  material_type_code: string;
  erp_category_desc: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MaterialTypeListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: MaterialTypeRecord[];
};

export type MaterialTypeListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type MaterialTypeWritePayload = {
  material_type_code: string;
  erp_category_desc: string;
  is_active?: boolean;
};

export type MaterialTypeImportJob = ImportJob;
