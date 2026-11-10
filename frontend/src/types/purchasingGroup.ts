import type { ImportJob } from "@/types/nameMaster";

export type PurchasingGroupRecord = {
  id: number;
  sap_purchase_group_code: string;
  name: string;
  remarks: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type PurchasingGroupListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: PurchasingGroupRecord[];
};

export type PurchasingGroupListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type PurchasingGroupWritePayload = {
  sap_purchase_group_code: string;
  name: string;
  remarks?: string;
  is_active?: boolean;
};

export type PurchasingGroupImportJob = ImportJob;
