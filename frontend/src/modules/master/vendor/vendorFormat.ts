const SUFFIXES = new Set(["pvt", "private", "ltd", "limited", "llp", "&", "and", "co", "inc"]);

/** Two-letter tile label from the meaningful words of a vendor name (skips "Pvt", "Ltd", "&"). */
export function vendorInitials(name: string) {
  const words = name
    .replace(/[^\p{L}\p{N}&\s]/gu, " ")
    .split(/\s+/)
    .filter((word) => word && !SUFFIXES.has(word.toLowerCase()));
  if (words.length === 0) return "?";
  const first = words[0][0] ?? "";
  const second = words.length > 1 ? (words[1][0] ?? "") : (words[0][1] ?? "");
  return (first + second).toUpperCase();
}

export function telHref(contact: string) {
  return `tel:${contact.replace(/[^\d+]/g, "")}`;
}
