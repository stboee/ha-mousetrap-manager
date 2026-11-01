import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

export const root = fileURLToPath(new URL("..", import.meta.url));
export const cardPath = root + "custom_components/mousetrap_manager/frontend/mousetrap-manager-card.js";
const server = createServer(async (req,res) => {
  let path = new URL(req.url, "http://localhost").pathname;
  if (path === "/favicon.ico") { res.writeHead(204).end(); return; }
  if (path.startsWith("/mousetrap_manager/images/")) path = "/custom_components/mousetrap_manager/frontend/images/" + path.split("/").pop();
  const full = resolve(root, "." + path);
  if (!full.startsWith(resolve(root) + "/")) { res.writeHead(403).end(); return; }
  try {
    const body = await readFile(full);
    res.setHeader("Content-Type", full.endsWith(".svg") ? "image/svg+xml" : full.endsWith(".js") ? "text/javascript" : "text/html");
    res.end(body);
  } catch (_) { res.writeHead(404).end(); }
});
await new Promise((r) => server.listen(0,"127.0.0.1",r));
server.unref();
export const fixtureUrl = `http://127.0.0.1:${server.address().port}/tests/fixture.html`;
export const demoUrl = `http://127.0.0.1:${server.address().port}/demo/index.html`;

/** Installed Google Chrome (or CHROME_PATH); falls back to Playwright's own Chromium if present. */
export async function launch() {
  const opts = process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH, args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"] } : { channel: "chrome" };
  try {
    return await chromium.launch(opts);
  } catch (e) {
    return chromium.launch();
  }
}

/** A page with console errors and uncaught exceptions collected into page.errors. */
export async function openPage(browser, url, options = {}) {
  const page = await browser.newPage(options);
  page.errors = [];
  page.on("pageerror", (e) => page.errors.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() === "error") page.errors.push("console.error: " + m.text());
  });
  if (url) await page.goto(url);
  return page;
}
