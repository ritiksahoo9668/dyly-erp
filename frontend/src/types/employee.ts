export type EmployeeGender = "Male" | "Female" | "Other" | "Prefer Not to Say";

export const EMPLOYEE_GENDERS: EmployeeGender[] = ["Male", "Female", "Other", "Prefer Not to Say"];

export type EmployeeRef = {
  id: number;
  name: string;
  is_active: boolean;
};

export type EmployeeUserRef = {
  id: number;
  name: string;
  email: string;
};

export type EmployeeListRecord = {
  id: number;
  employee_code: string;
  full_name: string;
  department: EmployeeRef;
  designation: EmployeeRef;
  company: EmployeeRef;
  division: EmployeeRef | null;
  facility: EmployeeRef | null;
  mobile_number: string;
  personal_email: string;
  company_email: string;
  date_of_joining: string;
  gender: EmployeeGender;
  is_active: boolean;
  updated_at: string;
};

export type EmployeeRecord = EmployeeListRecord & {
  location: string;
  vertical: EmployeeRef | null;
  created_at: string;
  created_by: EmployeeUserRef | null;
  updated_by: EmployeeUserRef | null;
};

export type EmployeeListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: EmployeeListRecord[];
};

export type EmployeeOrdering =
  | "employee_code"
  | "-employee_code"
  | "full_name"
  | "-full_name"
  | "department"
  | "-department"
  | "designation"
  | "-designation"
  | "company"
  | "-company"
  | "division"
  | "-division"
  | "status"
  | "-status"
  | "date_of_joining"
  | "-date_of_joining"
  | "updated_at"
  | "-updated_at";

export type EmployeeStats = {
  total: number;
  active: number;
  departments: number;
};

export type EmployeeListParams = {
  search?: string;
  page?: number;
  page_size?: number;
  ordering?: EmployeeOrdering;
  is_active?: boolean;
  department?: number;
  vertical?: number;
  designation?: number;
  company?: number;
  division?: number;
  facility?: number;
  gender?: EmployeeGender;
};

export type EmployeeWritePayload = {
  full_name: string;
  gender: EmployeeGender | "";
  mobile_number: string;
  personal_email: string;
  date_of_joining: string;
  location: string;
  department_id: number | null;
  vertical_id: number | null;
  designation_id: number | null;
  company_id: number | null;
  division_id: number | null;
  facility_id: number | null;
  company_email: string;
  is_active?: boolean;
  confirm_possible_duplicate?: boolean;
};

export type EmployeePreviewRowStatus = "valid" | "existing" | "possible_duplicate" | "failed";

export type EmployeePreviewRow = {
  row: number;
  full_name: string;
  mobile_number: string;
  status: EmployeePreviewRowStatus;
  reason: string;
};

export type EmployeeImportPreview = {
  total: number;
  valid: number;
  possible_duplicates: number;
  existing: number;
  failed: number;
  rows: EmployeePreviewRow[];
  errors: { row: number; reason: string }[];
};
