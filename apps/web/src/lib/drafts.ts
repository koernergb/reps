// Per-browser draft persistence. Storage can be unavailable (private mode, blocked site data),
// so every access is guarded and the editor still works without it.
const PREFIX = "reps:draft:";

export function loadDraft(scope: string): string | null {
  try {
    return window.localStorage.getItem(PREFIX + scope);
  } catch {
    return null;
  }
}

export function saveDraft(scope: string, code: string): void {
  try {
    window.localStorage.setItem(PREFIX + scope, code);
  } catch {
    // Ignore: drafts are a convenience, not a durability guarantee.
  }
}

export function clearDraft(scope: string): void {
  try {
    window.localStorage.removeItem(PREFIX + scope);
  } catch {
    // Ignore.
  }
}
