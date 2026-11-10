export type UnitCompany = {
  id: number;
  name: string;
  is_active: boolean;
};

export type UnitRecord = {
  id: number;
  name: string;
  company: UnitCompany;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type UnitListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: UnitRecord[];
};

export type UnitListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
  company?: number;
};

export type UnitWritePayload = {
  name: string;
  company_id: number;
  is_active?: boolean;
};
