import type { ImportJob } from "@/types/nameMaster";

export type StockYardRecord = {
  id: number;
  name: string;
  storage_code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type StockYardListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: StockYardRecord[];
};

export type StockYardListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type StockYardWritePayload = {
  name: string;
  storage_code: string;
  is_active?: boolean;
};

export type StockYardImportJob = ImportJob;
