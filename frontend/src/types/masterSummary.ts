import type { ImportJobStatus } from "@/types/nameMaster";

export type MasterCount = {
  total: number;
  active: number;
};

export type MasterRecentImport = {
  id: number;
  master_type: string;
  master_label: string;
  status: ImportJobStatus;
  original_filename: string;
  total_rows: number;
  created_rows: number;
  skipped_rows: number;
  failed_rows: number;
  uploaded_by: string | null;
  created_at: string;
};

export type MasterSummary = {
  masters: Record<string, MasterCount>;
  recent_imports: MasterRecentImport[];
};
