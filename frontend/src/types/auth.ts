import type { UserAccessPayload } from "@/types/access";
import type { UserRole } from "@/types/userOnboarding";

export type AuthUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  display_name: string;
  initials: string;
  role: string;
  role_label: string;
  is_staff: boolean;
  is_superuser: boolean;
  /** Absent on sessions stored before User Onboarding existed; refreshed by `getMe`. */
  can_manage_users?: boolean;
  assignable_roles?: UserRole[];
  /** Absent on sessions stored before Module Access existed; refreshed by `getMe`. */
  access?: UserAccessPayload;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access: string;
  refresh: string;
  user: AuthUser;
};

export type ForgotPasswordRequest = {
  email: string;
};

export type ForgotPasswordResponse = {
  detail: string;
};

export type ResetPasswordRequest = {
  token: string;
  password: string;
  password_confirm: string;
};
