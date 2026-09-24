import { expect, test } from "@playwright/test";

import { REFERENCE_PAIR_SUM, sendMessage, setEditorCode } from "./helpers";

test("practice interview from start to report, surviving a reload", async ({ page }) => {
  await page.goto("/interviews/new?problem=pair-sum-indices");
  await expect(page.getByRole("radio", { name: /Practice/ })).toHaveAttribute("aria-checked", "true");
  await page.getByRole("button", { name: "Start practice interview" }).click();
  await expect(page).toHaveURL(/\/interviews\/[0-9a-f-]+$/);
  await expect(page.getByText(/Today we'll work on Pair Sum Indices/)).toBeVisible();

  await sendMessage(page, "Can the same element be used twice?");
  await expect(page.getByText(/two indices must be different/)).toBeVisible();

  await page.reload();
  await expect(page.getByText(/two indices must be different/)).toBeVisible();

  await page.getByRole("button", { name: /Discuss my approach/ }).click();
  await expect(page.locator("[aria-current=step]")).toHaveText("Approach");
  await page.getByRole("button", { name: /ready to code/ }).click();
  await expect(page.locator("[aria-current=step]")).toHaveText("Implement");

  await setEditorCode(page, REFERENCE_PAIR_SUM);
  await page.getByRole("button", { name: /^Run$/ }).click();
  await expect(page.getByText(/Run: All tests passed/)).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: /^Submit$/ }).click();
  await expect(page.getByText(/Hidden tests: \d+ \/ \d+ passed/)).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("[aria-current=step]")).toHaveText("Complexity");

  await sendMessage(page, "O(n) time and O(n) space.");
  await expect(page.locator("[aria-current=step]")).toHaveText("Follow-up");
  await sendMessage(page, "With sorted input I'd use two pointers for O(1) space.");
  await page.getByRole("link", { name: /report/i }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Solved independently");
  await expect(page.getByText(/Facts/)).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/report.png", fullPage: true });
});

test("a mock interview shows its time contract and a single hint", async ({ page }) => {
  await page.goto("/interviews/new?problem=find-sorted-value&mode=mock");
  await page.getByRole("button", { name: "Start mock interview" }).click();
  await expect(page.getByRole("timer")).toBeVisible();
  await expect(page.getByText(/You have \d+ minutes/)).toBeVisible();
  await page.getByRole("button", { name: /Hint \(1 left\)/ }).click();
  await page.getByRole("button", { name: "Get a hint" }).click();
  await expect(page.getByText("Hint (level 1)")).toBeVisible();
  await expect(page.getByRole("button", { name: /Hint \(none left\)/ })).toBeDisabled();
  await page.screenshot({ path: "e2e/screenshots/mock-interview.png" });
});
