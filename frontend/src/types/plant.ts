import type { ImportJob } from "@/types/nameMaster";

export type PlantRecord = {
  id: number;
  sap_plant_code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type PlantListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: PlantRecord[];
};

export type PlantListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type PlantWritePayload = {
  sap_plant_code: string;
  name: string;
  is_active?: boolean;
};

export type PlantImportJob = ImportJob;
