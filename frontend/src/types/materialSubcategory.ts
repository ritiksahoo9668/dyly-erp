import type { NameMasterImportPreview, NameMasterImportSummary } from "@/types/nameMaster";

export type MaterialSubcategoryCategory = {
  id: number;
  name: string;
  is_active: boolean;
};

export type MaterialSubcategoryRecord = {
  id: number;
  name: string;
  category: MaterialSubcategoryCategory;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MaterialSubcategoryListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: MaterialSubcategoryRecord[];
};

export type MaterialSubcategoryListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
  category?: number;
};

export type MaterialSubcategoryWritePayload = {
  name: string;
  category_id: number;
  is_active?: boolean;
};

export type MaterialSubcategoryImportSummary = NameMasterImportSummary;
export type MaterialSubcategoryImportPreview = NameMasterImportPreview;
