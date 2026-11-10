export type VendorUserRef = {
  id: number;
  name: string;
  email: string;
};

export type VendorRecord = {
  id: number;
  erp_vendor_id: string;
  sap_vendor_id: string;
  vendor_name: string;
  email: string;
  contact_no: string;
  gstin: string;
  location: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: VendorUserRef | null;
  updated_by: VendorUserRef | null;
};

export type VendorListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: VendorRecord[];
};

export type VendorOrderingField =
  "vendor_name" | "erp_vendor_id" | "sap_vendor_id" | "gstin" | "location" | "status";
export type VendorOrdering = VendorOrderingField | `-${VendorOrderingField}`;

export type VendorListParams = {
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
  location?: string;
  ordering?: VendorOrdering;
};

export type VendorWritePayload = {
  sap_vendor_id: string;
  vendor_name: string;
  email: string;
  contact_no: string;
  gstin: string;
  location: string;
};

export type VendorPreviewStatus = "valid" | "existing" | "duplicate" | "failed";

export type VendorPreviewRow = VendorWritePayload & {
  row: number;
  status: VendorPreviewStatus;
  reason: string;
};

export type VendorImportPreview = {
  total: number;
  valid: number;
  existing: number;
  duplicate: number;
  failed: number;
  rows: VendorPreviewRow[];
  errors: { row: number; reason: string }[];
};
