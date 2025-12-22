import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  const ms = (date.getMilliseconds() / 1000).toFixed(2).slice(1);
  const base = date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  return `${base}${ms}`;
}

export function formatDateTimeShort(dateString: string): string {
  const date = new Date(dateString);
  const ms = (date.getMilliseconds() / 1000).toFixed(2).slice(1);
  const base = date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  return `${base}${ms}`;
}
