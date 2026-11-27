import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { parse, tokenizer } from "acorn";
import { parse as parseYaml } from "yaml";

const card = new URL("../custom_components/mousetrap_manager/frontend/mousetrap-manager-card.js", import.meta.url);
const distribution = "dist/mousetrap-manager-card.js";
const source = await readFile(card, "utf8");
const compatibility = { ecmaVersion: 2018 };

test("both shipped copies of the card are identical", async () => {
  const bundledCopy = await readFile(new URL(`../${distribution}`, import.meta.url), "utf8");
  assert.equal(bundledCopy, source);
});

test("the dashboard script parses as ES2018", () => {
  parse(source, compatibility);
});

for (const [feature, example] of Object.entries({
  "nullish coalescing": "undefined ?? false",
  "optional chaining": "trap?.state",
  "public class fields": "class Trap { available = false }",
  "numeric separators": "const timeout = 10_000",
})) {
  test(`the ES2018 parser rejects ${feature}`, () => {
    assert.throws(() => parse(example, compatibility), SyntaxError);
  });
}

function usesLookbehind(pattern) {
  let insideSet = false;
  for (let i = 0; i < pattern.length; i++) {
    if (pattern[i] === "\\") {
      i++;
    } else if (pattern[i] === "[") {
      insideSet = true;
    } else if (pattern[i] === "]") {
      insideSet = false;
    } else if (!insideSet && (pattern.startsWith("(?<=", i) || pattern.startsWith("(?<!", i))) {
      return true;
    }
  }
  return false;
}

function lookbehindLocations(script) {
  const matches = [];
  for (const token of tokenizer(script, { ...compatibility, locations: true })) {
    if (token.value?.pattern && usesLookbehind(token.value.pattern)) matches.push(token.loc.start.line);
  }
  return matches;
}

test("regular expressions load on browsers without lookbehind support", () => {
  assert.deepEqual(lookbehindLocations(source), []);
  assert.deepEqual(lookbehindLocations("const before = /(?<=x)y/;\nconst after = /(?<!a)b/;"), [1, 2]);
  assert.deepEqual(lookbehindLocations(String.raw`const literal = /\(\?<=/; const set = /[(?<!=]/;`), []);
});

test("Node's syntax check accepts the card", () => {
  const outcome = spawnSync(process.execPath, ["--check", fileURLToPath(card)], { encoding: "utf8" });
  assert.equal(outcome.status, 0, outcome.stderr || String(outcome.error ?? ""));
});

test("the dashboard script uses ASCII source bytes", () => {
  const bytes = Buffer.from(source, "utf8");
  assert.equal(bytes.findIndex((byte) => byte > 127), -1, "Encode non-ASCII text with Unicode escapes");
});

test("the build workflow runs syntax checks on the distributed card", async () => {
  const { jobs } = parseYaml(await readFile(new URL("../.github/workflows/ci.yml", import.meta.url), "utf8"));
  const commands = jobs.syntax.steps.map((step) => step.run?.trim());
  assert.ok(commands.includes(`node --check ${distribution}`), "Node syntax check is missing");
  assert.ok(commands.includes(`npx --yes acorn@8 --ecma2018 --silent ${distribution}`), "ES2018 check is missing");
});

test("the CI ASCII guard accepts the card and reports an incompatible byte at its line", async (t) => {
  const { jobs } = parseYaml(await readFile(new URL("../.github/workflows/ci.yml", import.meta.url), "utf8"));
  const guard = jobs.syntax.steps.find((step) => step.name === "ASCII guard")?.run;
  assert.ok(guard, "Missing ASCII check in CI");

  const sandbox = await mkdtemp(join(tmpdir(), "mousetrap-compatibility-"));
  t.after(() => rm(sandbox, { recursive: true, force: true }));
  await mkdir(join(sandbox, "dist"));

  const file = join(sandbox, distribution);
  const check = () => spawnSync("bash", ["-e", "-c", guard], { cwd: sandbox, encoding: "utf8" });
  await writeFile(file, source);
  const pass = check();
  assert.equal(pass.status, 0, pass.stdout || pass.stderr);

  await writeFile(file, '// header\n\nconst title = "Felle på loftet";\n');
  const fail = check();
  assert.equal(fail.status, 1);
  assert.match(fail.stdout, /::error file=dist\/mousetrap-manager-card\.js,line=3::Non-ASCII character/);
});
