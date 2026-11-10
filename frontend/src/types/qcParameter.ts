export type QcParameterUserRef = {
  id: number;
  name: string;
  email: string;
};

export type QcParameterRecord = {
  id: number;
  name: string;
  short_name: string;
  unit: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: QcParameterUserRef | null;
  updated_by: QcParameterUserRef | null;
};

export type QcParameterListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: QcParameterRecord[];
};

export type QcParameterListParams = {
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type QcParameterWritePayload = {
  name: string;
  short_name: string;
  unit: string;
};

export type QcParameterPreviewStatus = "valid" | "existing" | "duplicate" | "failed";

export type QcParameterPreviewRow = {
  row: number;
  name: string;
  short_name: string;
  unit: string;
  status: QcParameterPreviewStatus;
  reason: string;
};

export type QcParameterImportPreview = {
  total: number;
  valid: number;
  existing: number;
  duplicate: number;
  failed: number;
  rows: QcParameterPreviewRow[];
  errors: { row: number; reason: string }[];
};
