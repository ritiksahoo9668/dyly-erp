import type { AccessAssignment } from "@/types/access";
import type { EmployeeRef, EmployeeUserRef } from "@/types/employee";

export type UserRole = "SUPERADMIN" | "ADMIN" | "USER";

export const USER_ROLE_LABELS: Record<UserRole, string> = {
  SUPERADMIN: "Superadmin",
  ADMIN: "Admin",
  USER: "User",
};

export const USER_ROLES: UserRole[] = ["SUPERADMIN", "ADMIN", "USER"];

export type OnboardingStatus =
  | "DRAFT"
  | "INVITE_PENDING"
  | "INVITED"
  | "ACTIVATED"
  | "EXPIRED"
  | "REVOKED";

export const ONBOARDING_STATUS_LABELS: Record<OnboardingStatus, string> = {
  DRAFT: "Draft",
  INVITE_PENDING: "Invite Pending",
  INVITED: "Invited",
  ACTIVATED: "Activated",
  EXPIRED: "Expired",
  REVOKED: "Revoked",
};

export const ONBOARDING_STATUSES = Object.keys(ONBOARDING_STATUS_LABELS) as OnboardingStatus[];

export type MailStatus = "" | "QUEUED" | "SENT" | "FAILED";

export type OnboardingAction =
  | "view"
  | "edit"
  | "send_invite"
  | "discard"
  | "resend_invite"
  | "revoke"
  | "deactivate_user"
  | "activate_user"
  | "edit_access";

export type ErpUserAction = "change_role" | "edit_access" | "deactivate" | "activate";

export type OnboardingEmployee = {
  id: number;
  employee_code: string;
  full_name: string;
  department: EmployeeRef | null;
  designation: EmployeeRef | null;
  company: EmployeeRef | null;
  unit: EmployeeRef | null;
  company_email: string;
  personal_email: string;
  is_active: boolean;
};

export type UserOnboardingRecord = {
  id: number;
  onboarding_code: string;
  employee: OnboardingEmployee;
  login_email: string;
  role: UserRole;
  role_label: string;
  status: OnboardingStatus;
  status_label: string;
  last_mail_status: MailStatus;
  user: { id: number; is_active: boolean; last_login: string | null } | null;
  invite_sent_at: string | null;
  last_invite_sent_at: string | null;
  invite_expires_at: string | null;
  activated_at: string | null;
  revoked_at: string | null;
  invite_send_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: EmployeeUserRef | null;
  updated_by: EmployeeUserRef | null;
  allowed_actions: OnboardingAction[];
};

export type UserAccessEventRecord = {
  id: number;
  event: string;
  event_label: string;
  actor: EmployeeUserRef | null;
  /** Module access key for access changes, e.g. "PROCUREMENT.RFQ.CREATE". */
  permission: string;
  from_value: string;
  to_value: string;
  created_at: string;
};

export type UserOnboardingDetail = UserOnboardingRecord & {
  access: AccessAssignment;
  events: UserAccessEventRecord[];
};

export type UserOnboardingListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: UserOnboardingRecord[];
};

export type UserOnboardingListParams = {
  search?: string;
  page?: number;
  page_size?: number;
  status?: OnboardingStatus;
  role?: UserRole;
  department?: number;
  company?: number;
  unit?: number;
};

export type UserOnboardingStats = {
  total_users: number;
  active_users: number;
  pending_invitations: number;
  expired_invitations: number;
};

export type UserOnboardingWritePayload = {
  employee_id: number;
  login_email: string;
  role: UserRole;
  send_invite?: boolean;
  access?: AccessAssignment;
};

export type ErpUserRecord = {
  id: number;
  email: string;
  display_name: string;
  role: UserRole;
  role_label: string;
  is_active: boolean;
  last_login: string | null;
  date_joined: string;
  employee: {
    id: number;
    employee_code: string;
    full_name: string;
    department: EmployeeRef | null;
  } | null;
  onboarding: {
    id: number;
    onboarding_code: string;
    status: OnboardingStatus;
    status_label: string;
  } | null;
  allowed_actions: ErpUserAction[];
};

export type ErpUserListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ErpUserRecord[];
};

export type ErpUserListParams = {
  search?: string;
  page?: number;
  page_size?: number;
  role?: UserRole;
  is_active?: boolean;
};

export type ActivationValidateResponse = {
  status: "valid";
  employee_name: string;
  login_email: string;
  expires_at: string | null;
};

export type ActivateAccountRequest = {
  token: string;
  password: string;
  password_confirm: string;
};
