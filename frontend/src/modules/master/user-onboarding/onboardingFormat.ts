import {
  ONBOARDING_STATUS_LABELS,
  USER_ROLE_LABELS,
  type OnboardingAction,
  type UserOnboardingRecord,
  type UserRole,
} from "@/types/userOnboarding";

export type Tone = "gray" | "blue" | "amber" | "green" | "red" | "purple";

export const ACTION_LABELS: Record<OnboardingAction, string> = {
  view: "View Details",
  edit: "Edit Draft",
  send_invite: "Send Invitation",
  discard: "Discard Draft",
  resend_invite: "Resend Invitation",
  revoke: "Revoke Invitation",
  deactivate_user: "Deactivate User",
  activate_user: "Activate User",
  edit_access: "Edit Module Access",
};

export const DANGER_ACTIONS = new Set<OnboardingAction>(["discard", "revoke", "deactivate_user"]);

const ROLE_TONES: Record<UserRole, Tone> = {
  SUPERADMIN: "purple",
  ADMIN: "blue",
  USER: "gray",
};

export function roleLabel(role: UserRole) {
  return USER_ROLE_LABELS[role] ?? role;
}

export function roleTone(role: UserRole): Tone {
  return ROLE_TONES[role] ?? "gray";
}

/** Invitation badge; a failed delivery on a pending invite is shown as "Email Failed". */
export function invitationBadge(record: Pick<UserOnboardingRecord, "status" | "last_mail_status">): {
  label: string;
  tone: Tone;
} {
  if (record.status === "INVITE_PENDING" && record.last_mail_status === "FAILED") {
    return { label: "Email Failed", tone: "red" };
  }
  const label = ONBOARDING_STATUS_LABELS[record.status] ?? record.status;
  switch (record.status) {
    case "INVITE_PENDING":
      return { label, tone: "amber" };
    case "INVITED":
      return { label, tone: "blue" };
    case "ACTIVATED":
      return { label, tone: "green" };
    case "EXPIRED":
    case "REVOKED":
      return { label, tone: "red" };
    default:
      return { label, tone: "gray" };
  }
}

export function accountStatus(record: UserOnboardingRecord): { label: string; tone: Tone } {
  if (!record.user) return { label: "No account", tone: "gray" };
  if (record.user.is_active) return { label: "Active", tone: "green" };
  return record.status === "ACTIVATED"
    ? { label: "Deactivated", tone: "red" }
    : { label: "Not activated", tone: "gray" };
}

const EVENT_VALUE_LABELS: Record<string, string> = {
  ...ONBOARDING_STATUS_LABELS,
  ...USER_ROLE_LABELS,
  ACTIVE: "Active",
  INACTIVE: "Inactive",
  ON: "Granted",
  OFF: "Removed",
  IMPLICIT: "Before module access",
  PRESERVED: "Preserved",
};

export function eventValue(value: string) {
  return EVENT_VALUE_LABELS[value] ?? value;
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
