import assert from "node:assert/strict";
import { test } from "node:test";
import { launchBrowser } from "./lib.mjs";

const browserSuites = [
  ["attention", () => import("./attention.test.mjs")],
  ["dashboard", () => import("./dashboard.test.mjs")],
  ["layout", () => import("./layout.test.mjs")],
];

const filters = process.argv.slice(2);
const include = (name) => filters.length === 0 || filters.some((part) => `${name}.test.mjs`.includes(part));
const selected = browserSuites.filter(([name]) => include(name));
const withSyntax = include("syntax");

if (!withSyntax && selected.length === 0) throw new Error("No suites match the filter");
if (withSyntax) await import("./syntax.test.mjs");

if (selected.length > 0) {
  test("Home Assistant card in Chromium", async (t) => {
    const browser = await launchBrowser();
    t.after(() => browser.close());

    for (const [name, importSuite] of selected) {
      await t.test(name, { timeout: 45_000 }, async (suite) => {
        const { default: exercise } = await importSuite();
        const report = await exercise(browser);
        const failures = (report.errors ?? []).map((message) => `Browser: ${message}`);
        let passed = 0;
        for (const result of report.lines) {
          if (result.startsWith("ok ")) passed++;
          else failures.push(result);
        }

        assert.ok(report.lines.length > 0, "Suite must exercise the card");
        assert.deepEqual(failures, [], failures.join("\n"));
        suite.diagnostic(`${passed} browser assertions`);
      });
    }
  });
}
