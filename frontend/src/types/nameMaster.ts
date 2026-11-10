export type NameMasterRecord = {
  id: number;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type NameMasterListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: NameMasterRecord[];
};

export type NameMasterListParams = {
  /** Read from the open reference lookup (dropdowns) instead of the permissioned list. */
  lookup?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

export type NameMasterWritePayload = {
  name: string;
  is_active?: boolean;
};

export type NameMasterImportError = {
  row: number;
  reason: string;
};

export type NameMasterImportSummary = {
  total: number;
  created: number;
  skipped: number;
  failed: number;
  errors: NameMasterImportError[];
};

export type NameMasterPreviewRowStatus = "valid" | "existing" | "duplicate" | "failed";

export type NameMasterPreviewRow = {
  row: number;
  name: string;
  department?: string;
  status: NameMasterPreviewRowStatus;
  reason: string;
};

export type NameMasterValidRow = {
  name: string;
  department_id?: number;
};

export type NameMasterImportPreview = {
  total: number;
  valid: number;
  existing: number;
  duplicate: number;
  failed: number;
  rows: NameMasterPreviewRow[];
  valid_rows: NameMasterValidRow[];
  errors: NameMasterImportError[];
};

export type ImportJobStatus =
  | "PENDING"
  | "VALIDATING"
  | "PROCESSING"
  | "COMPLETED"
  | "COMPLETED_WITH_ERRORS"
  | "FAILED";

export type ImportJob = {
  id: number;
  master_type: string;
  status: ImportJobStatus;
  original_filename: string;
  total_rows: number;
  processed_rows: number;
  created_rows: number;
  skipped_rows: number;
  failed_rows: number;
  warning_rows?: number;
  progress_percentage: number;
  progress_label: string;
  detail: string;
  has_error_file: boolean;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type NameMasterResource =
  | "divisions"
  | "departments"
  | "designations"
  | "facilities"
  | "companies"
  | "material-categories"
  | "weighbridges";
