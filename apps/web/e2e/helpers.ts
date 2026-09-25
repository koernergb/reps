import { expect, type Page } from "@playwright/test";

export const REFERENCE_PAIR_SUM = [
  "def pair_sum_indices(nums, target):",
  "    seen = {}",
  "    for index, value in enumerate(nums):",
  "        if target - value in seen:",
  "            return [seen[target - value], index]",
  "        seen[value] = index",
  "",
].join("\n");

// Monaco auto-indents typed text, so tests set the model value directly; the textarea
// fallback (offline) is filled normally.
export async function setEditorCode(page: Page, code: string) {
  const fallback = page.locator("textarea[aria-label^='Python solution']");
  // Wait until the editor has mounted and subscribed to changes, not merely until Monaco loaded.
  await page.waitForFunction(
    () => document.querySelector("[data-editor-ready='true']") || document.querySelector("textarea[aria-label^='Python solution']"),
    undefined,
    { timeout: 30_000 },
  );
  if (await fallback.count()) {
    await fallback.fill(code);
    return;
  }
  await page.evaluate((value) => {
    const monaco = (window as unknown as { monaco: { editor: { getModels: () => Array<{ setValue: (v: string) => void }> } } }).monaco;
    monaco.editor.getModels()[0].setValue(value);
  }, code);
}

export async function sendMessage(page: Page, text: string) {
  const box = page.getByLabel("Message the interviewer");
  await box.fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
  // The composer disappears when the interviewer ends the interview.
  await expect(async () => {
    if (await box.count()) await expect(box).toHaveValue("", { timeout: 500 });
  }).toPass({ timeout: 20_000 });
}

export const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";

export async function abandonActiveDrill(request: import("@playwright/test").APIRequestContext) {
  const active = await (await request.get(`${API_URL}/v1/drills/active`)).json();
  if (active?.id) await request.post(`${API_URL}/v1/drills/${active.id}/actions`, { data: { action: "abandon" } });
}
