import type { EmployeeRef, EmployeeUserRef } from "@/types/employee";

const AVATAR_COLORS = ["#1d6ef5", "#7c3aed", "#0891b2", "#16a34a", "#ea580c", "#db2777"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1][0] ?? "") : "";
  return (first + last).toUpperCase();
}

export function avatarColor(seed: string) {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

export function formatMobile(value: string) {
  const indian = /^\+91(\d{10})$/.exec(value);
  if (indian) return `+91 ${indian[1].slice(0, 5)} ${indian[1].slice(5)}`;
  if (/^\d{10}$/.test(value)) return `${value.slice(0, 5)} ${value.slice(5)}`;
  return value;
}

function parseIsoDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

/** "2020-01-12" → "12 Jan 2020". */
export function formatDate(value: string) {
  const parsed = parseIsoDate(value);
  if (!parsed) return value || "—";
  return `${parsed.day} ${MONTHS[parsed.month - 1] ?? parsed.month} ${parsed.year}`;
}

export function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const time = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}, ${time}`;
}

/** Service length from Date Of Joining to today, e.g. "3 yrs 4 mos of service". */
export function formatTenure(joining: string, today = new Date()) {
  const parsed = parseIsoDate(joining);
  if (!parsed) return "";
  let months = (today.getFullYear() - parsed.year) * 12 + (today.getMonth() + 1 - parsed.month);
  if (today.getDate() < parsed.day) months -= 1;
  if (months < 0) return "Joining upcoming";
  const years = Math.floor(months / 12);
  const rest = months % 12;
  if (years === 0 && rest === 0) return "Joined this month";
  const parts = [];
  if (years) parts.push(`${years} yr${years === 1 ? "" : "s"}`);
  if (rest) parts.push(`${rest} mo${rest === 1 ? "" : "s"}`);
  return `${parts.join(" ")} of service`;
}

export function refName(ref: EmployeeRef | null) {
  if (!ref) return "";
  return ref.is_active ? ref.name : `${ref.name} (Inactive)`;
}

export function userName(user: EmployeeUserRef | null) {
  return user ? user.name : "";
}
