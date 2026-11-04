export type Category =
  | "basic"
  | "blood"
  | "allergies"
  | "medications"
  | "conditions"
  | "surgeries"
  | "prescriptions"
  | "lab_reports"
  | "health_assessments"
  | "documents";

export const CATEGORIES: { key: Category; label: string }[] = [
  { key: "basic", label: "Basic information" },
  { key: "blood", label: "Blood group" },
  { key: "allergies", label: "Allergies" },
  { key: "medications", label: "Medications" },
  { key: "conditions", label: "Medical conditions" },
  { key: "surgeries", label: "Surgeries" },
  { key: "prescriptions", label: "Prescriptions" },
  { key: "lab_reports", label: "Lab reports" },
  { key: "health_assessments", label: "Health assessments" },
  { key: "documents", label: "Other medical documents" },
];

export const categoryLabel = (key: string) =>
  CATEGORIES.find((c) => c.key === key)?.label ?? key;

export const DURATIONS = [
  { label: "1 hour", hours: 1 },
  { label: "24 hours", hours: 24 },
  { label: "7 days", hours: 24 * 7 },
  { label: "30 days", hours: 24 * 30 },
];

export const PURPOSES = [
  "Consultation",
  "Diagnosis",
  "Treatment",
  "Second opinion",
  "Other",
];

export const DOC_TYPES = [
  { key: "prescription", label: "Prescription" },
  { key: "lab_report", label: "Lab report" },
  { key: "discharge_summary", label: "Discharge summary" },
  { key: "imaging_report", label: "Imaging report" },
  { key: "other", label: "Other" },
];

export const BLOOD_GROUPS = ["A", "B", "AB", "O"];
export const SEVERITIES = ["mild", "moderate", "severe"];

export function haversineKm(
  a: { lat: number; lon: number },
  b: { lat: number; lon: number },
) {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const la1 = (a.lat * Math.PI) / 180;
  const la2 = (b.lat * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(la1) * Math.cos(la2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { dateStyle: "medium" });
}
