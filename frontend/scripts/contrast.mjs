// WCAG contrast check for the design tokens in src/app/globals.css.
// Usage: node scripts/contrast.mjs   (exits 1 if any required pair fails)
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

function block(selector) {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`missing ${selector}`);
  const end = css.indexOf("}", start);
  const vars = {};
  for (const m of css.slice(start, end).matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) vars[m[1]] = m[2].trim();
  return vars;
}

function parse(value) {
  value = value.trim();
  let m = value.match(/^#([0-9a-f]{6})$/i);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)).concat(1);
  m = value.match(/^rgb\((\d+)\s+(\d+)\s+(\d+)(?:\s*\/\s*([\d.]+))?\)$/);
  if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
  throw new Error(`cannot parse colour ${value}`);
}

const over = (fg, bg) => [0, 1, 2].map((i) => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat(1);
const lum = ([r, g, b]) =>
  [r, g, b]
    .map((c) => c / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i], 0);
const ratio = (a, b) => {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};

const themes = { light: block(":root"), dark: block(':root[data-theme="dark"]') };
const STATUS = ["critical", "high", "medium", "low", "info", "success"];
let failed = 0;

for (const [name, t] of Object.entries(themes)) {
  const c = (k) => {
    if (!(k in t)) throw new Error(`${name}: missing --${k}`);
    return parse(t[k]);
  };
  const surface = c("surface");
  const solid = (k) => over(c(k), surface);
  const pairs = [];
  for (const bg of ["canvas", "surface", "surface-2", "surface-3"]) {
    pairs.push(["ink", bg, 4.5], ["ink-2", bg, 4.5], ["ink-3", bg, 4.5]);
  }
  pairs.push(["accent", "surface", 4.5], ["accent", "canvas", 4.5], ["accent", "accent-soft", 4.5]);
  pairs.push(["on-accent", "accent", 4.5], ["on-accent", "accent-hover", 4.5]);
  pairs.push(["focus", "canvas", 3], ["focus", "surface", 3]);
  for (const s of STATUS) {
    pairs.push([`${s}-fg`, `${s}-bg`, 4.5], [`${s}-fg`, "surface", 4.5], [`${s}-fg`, "canvas", 4.5]);
  }
  console.log(`\n${name}`);
  // Solid fills are dots and bars that always sit next to an icon and a word (principle 3),
  // so they are reported for information and do not fail the check.
  for (const s of STATUS) console.log(`  info ${`${s}-solid`.padEnd(12)} on surface      ${ratio(solid(`${s}-solid`), surface).toFixed(2)}`);
  for (const [fg, bg, min] of pairs) {
    const r = ratio(solid(fg), solid(bg));
    const ok = r >= min;
    if (!ok) failed++;
    console.log(`${ok ? "  ok " : "FAIL "} ${fg.padEnd(12)} on ${bg.padEnd(12)} ${r.toFixed(2)} (min ${min})`);
  }
}
console.log(failed ? `\n${failed} pair(s) fail` : "\nAll pairs pass");
process.exit(failed ? 1 : 0);
