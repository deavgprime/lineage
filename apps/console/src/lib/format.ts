export const STATUS_LABELS: Record<string, string> = {
  drafting: "Drafting",
  draft: "Ready for review",
  awaiting_mlro: "Waiting for MLRO",
  final: "Signed off",
  failed: "Failed",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

// How long ago, in the largest whole unit, for the queue.
export function age(iso: string, now: number = Date.now()): string {
  const minutes = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} h`;
  return `${Math.floor(hours / 24)} d`;
}

// UK company numbers are eight characters: digits, or two letters and six digits.
export function normaliseCompanyNumber(value: string): string | null {
  const v = value.trim().toUpperCase().replace(/\s+/g, "");
  if (/^\d{1,8}$/.test(v)) return v.padStart(8, "0");
  if (/^[A-Z]{2}\d{6}$/.test(v)) return v;
  return null;
}
