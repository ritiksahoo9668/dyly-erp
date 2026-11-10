import type { ImportJob } from "@/types/nameMaster";

export type UomRecord = {
  id: number;
  name: string;
  symbol: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type UomListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: UomRecord[];
};

export type UomListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type UomWritePayload = {
  name: string;
  symbol: string;
  is_active?: boolean;
};

export type UomImportJob = ImportJob;
