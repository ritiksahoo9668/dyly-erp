import type { ImportJob } from "@/types/nameMaster";

export type MaterialRef = {
  id: number;
  name: string;
  code?: string;
  symbol?: string;
};

export type MaterialImageSource = "NONE" | "UPLOAD" | "URL";

export type MaterialImageFields = {
  /** Legacy alias of image_url (read-only). */
  item_image: string;
  image_source: MaterialImageSource;
  /** Resolved active image: uploaded file → image URL → null (placeholder). */
  display_image: string | null;
  /** Card-sized image: upload thumbnail → image URL → null. */
  display_thumb: string | null;
};

export type MaterialListRecord = MaterialImageFields & {
  id: number;
  sap_code: string;
  item_name: string;
  material_category: MaterialRef | null;
  material_subcategory: MaterialRef | null;
  uom: MaterialRef | null;
  material_type: MaterialRef | null;
  material_group: MaterialRef | null;
  plant: MaterialRef | null;
  department: MaterialRef | null;
  price: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MaterialRecord = MaterialImageFields & {
  id: number;
  item_name: string;
  item_description: string;
  descriptive_spec: string;
  technical_spec: string;
  document_type: string;
  store_code: string;
  division: MaterialRef | null;
  material_category: MaterialRef | null;
  material_subcategory: MaterialRef | null;
  uom: MaterialRef | null;
  stock_yard: MaterialRef | null;
  department: MaterialRef | null;
  hsn_sac_code: string;
  gst_percent: string;
  price: string;
  sap_code: string;
  plant: MaterialRef | null;
  material_group: MaterialRef | null;
  material_type: MaterialRef | null;
  purchasing_group: MaterialRef | null;
  image_url: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  updated_by: number | null;
};

export type MaterialListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: MaterialListRecord[];
};

export type MaterialListParams = {
  search?: string;
  page?: number;
  page_size?: number;
  is_active?: boolean;
  ordering?: string;
  material_category?: number;
  material_subcategory?: number;
  uom?: number;
  material_type?: number;
  material_group?: number;
  purchasing_group?: number;
  plant?: number;
  stock_yard?: number;
  department?: number;
  division?: number;
};

export type MaterialWritePayload = {
  item_name: string;
  item_description: string;
  descriptive_spec: string;
  technical_spec?: string;
  document_type: string;
  store_code: string;
  division_id?: number | null;
  material_category_id: number;
  material_subcategory_id: number;
  uom_id: number;
  stock_yard_id: number;
  department_id: number;
  hsn_sac_code: string;
  gst_percent: string;
  price: string;
  sap_code: string;
  plant_id: number;
  material_group_id: number;
  material_type_id: number;
  purchasing_group_id: number;
  is_active?: boolean;
};

export type MaterialImportPreview = {
  total: number;
  valid: number;
  existing: number;
  duplicate: number;
  failed: number;
  warnings?: number;
  warning_rows?: Array<{ row: number; reason: string }>;
  rows: Array<{
    row: number;
    sap_code: string;
    item_name: string;
    status: string;
    reason: string;
  }>;
  errors: Array<{ row: number; reason: string }>;
  missing_masters_summary: string[];
};

export type MaterialImportJob = ImportJob;
