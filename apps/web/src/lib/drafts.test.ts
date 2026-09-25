import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { clearDraft, loadDraft, saveDraft } from "./drafts";

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => void values.delete(key),
    setItem: (key, value) => void values.set(key, String(value)),
  };
}

function install(storage: Storage) {
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
}

describe("drafts", () => {
  beforeEach(() => install(memoryStorage()));
  afterEach(() => install(memoryStorage()));

  it("round-trips a draft per scope", () => {
    saveDraft("practice:a", "code a");
    saveDraft("practice:b", "code b");
    expect(loadDraft("practice:a")).toBe("code a");
    clearDraft("practice:a");
    expect(loadDraft("practice:a")).toBeNull();
    expect(loadDraft("practice:b")).toBe("code b");
  });

  it("tolerates unavailable storage", () => {
    const blocked = memoryStorage();
    blocked.getItem = () => {
      throw new Error("blocked");
    };
    blocked.setItem = () => {
      throw new Error("blocked");
    };
    install(blocked);
    expect(() => saveDraft("x", "y")).not.toThrow();
    expect(loadDraft("x")).toBeNull();
  });
});
