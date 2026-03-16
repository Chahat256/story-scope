import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelationshipType(type: string): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export function getConfidenceColor(confidence: string): string {
  if (confidence.includes("high") || confidence.includes("strongly")) {
    return "text-emerald-700 bg-emerald-50 border-emerald-200";
  }
  if (confidence.includes("moderate")) {
    return "text-amber-700 bg-amber-50 border-amber-200";
  }
  return "text-slate-600 bg-slate-50 border-slate-200";
}

export function getPrevalenceColor(prevalence: string): string {
  if (prevalence === "central") return "text-violet-700 bg-violet-50 border-violet-200";
  if (prevalence === "significant") return "text-blue-700 bg-blue-50 border-blue-200";
  return "text-slate-600 bg-slate-50 border-slate-200";
}

export function getRoleColor(role: string): string {
  if (role === "protagonist") return "text-indigo-700 bg-indigo-50 border-indigo-200";
  if (role === "antagonist") return "text-red-700 bg-red-50 border-red-200";
  if (role === "deuteragonist") return "text-violet-700 bg-violet-50 border-violet-200";
  return "text-slate-600 bg-slate-50 border-slate-200";
}
