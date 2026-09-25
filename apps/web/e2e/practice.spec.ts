import { expect, test } from "@playwright/test";

import { abandonActiveDrill, setEditorCode } from "./helpers";

test("problem drafts persist across reloads and runs show visible detail", async ({ page }) => {
  await page.goto("/problems/balanced-delimiters");
  await expect(page.getByRole("heading", { name: "Balanced Delimiters" })).toBeVisible();
  const code = "def balanced_delimiters(text):\n    return text == ''\n";
  await setEditorCode(page, code);
  await page.getByRole("button", { name: /^Run$/ }).click();
  await expect(page.getByText(/Test 1: (Wrong answer|Passed)/)).toBeVisible({ timeout: 60_000 });
  await page.reload();
  await page.waitForSelector("[data-editor-ready='true']", { timeout: 30_000 });
  await page.waitForFunction(() => {
    const monaco = (window as unknown as { monaco?: { editor: { getModels: () => Array<{ getValue: () => string }> } } }).monaco;
    return monaco?.editor.getModels()[0]?.getValue().includes("return text == ''");
  }, undefined, { timeout: 30_000 });
  await page.screenshot({ path: "e2e/screenshots/workspace.png" });
});

test("a drill runs items and records results", async ({ page, request }) => {
  await abandonActiveDrill(request);
  await page.goto("/drills");
  await page.getByRole("button", { name: /^5 min/ }).click();
  await expect(page.getByRole("list", { name: "Drill items" })).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/drill.png" });
  await page.getByRole("button", { name: "Start next item" }).click();
  const answer = page.getByLabel("Your answer");
  if (await answer.isVisible().catch(() => false)) {
    await answer.fill("Use a lookup structure so repeated checks are constant time.");
    await page.getByRole("button", { name: /Check answer/ }).click();
    await expect(page.getByText(/Graded by/)).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByLabel("Done").first()).toBeVisible();
  }
});

test("dashboard and progress render learner state", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: /Start a 10-minute drill/ })).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/dashboard.png", fullPage: true });
  await page.goto("/history");
  await expect(page.getByRole("heading", { name: "Skills and history" })).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/progress.png", fullPage: true });
  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "Reviews" })).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/reviews.png", fullPage: true });
});
