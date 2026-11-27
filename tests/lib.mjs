import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const origin = "http://mousetrap-manager.test";
const integration = "custom_components/mousetrap_manager";
const resource = `${integration}/frontend/mousetrap-manager-card.js`;
const localFile = (suffix) => fileURLToPath(new URL(`../${suffix}`, import.meta.url));

export const cardPath = localFile(resource);
export const fixtureUrl = `${origin}/tests/fixture.html`;
export const demoUrl = `${origin}/demo/index.html`;
export const attentionDemoUrl = `${origin}/demo/attention.html`;

const documents = new Set(["/tests/fixture.html", "/demo/index.html", "/demo/attention.html"]);
const imageRoute = /^\/mousetrap_manager\/images\/([a-z0-9-]+\.svg)$/;

async function respondWithFixture(route) {
  const url = new URL(route.request().url());
  if (url.origin !== origin) {
    await route.abort();
    return;
  }
  if (url.pathname === "/favicon.ico") {
    await route.fulfill({ status: 204, body: "" });
    return;
  }
  if (documents.has(url.pathname)) {
    await route.fulfill({ path: localFile(url.pathname.slice(1)), contentType: "text/html; charset=utf-8" });
    return;
  }
  if (url.pathname === "/mousetrap_manager/mousetrap-manager-card.js" || url.pathname === `/${resource}`) {
    await route.fulfill({ path: cardPath, contentType: "text/javascript; charset=utf-8" });
    return;
  }
  const illustration = imageRoute.exec(url.pathname)?.[1];
  if (illustration) {
    await route.fulfill({
      path: localFile(`${integration}/frontend/images/${illustration}`),
      contentType: "image/svg+xml",
    });
    return;
  }
  await route.fulfill({ status: 404, body: "No matching test fixture" });
}

export async function launchBrowser() {
  const executablePath = process.env.CHROME_PATH;
  if (executablePath) {
    return chromium.launch({ executablePath, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
  }
  try {
    return await chromium.launch();
  } catch (bundledError) {
    try {
      return await chromium.launch({ channel: "chrome" });
    } catch (installedError) {
      throw new AggregateError([bundledError, installedError], "Install Chromium for Playwright or set CHROME_PATH");
    }
  }
}

export async function openPage(browser, url, options) {
  const tab = await browser.newPage(options);
  const errors = [];
  tab.errors = errors;
  tab.on("console", (event) => {
    if (event.type() === "error") errors.push(event.text());
  });
  tab.on("pageerror", (exception) => errors.push(exception.message));
  await tab.route("**/*", respondWithFixture);
  await tab.goto(url);
  return tab;
}
