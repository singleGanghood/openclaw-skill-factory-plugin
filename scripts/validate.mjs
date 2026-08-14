#!/usr/bin/env node
// Lightweight, dependency-free validator for the Skill Factory OpenClaw plugin.
// Checks: manifest required fields (id + configSchema), skills dir resolution,
// and each bundled SKILL.md frontmatter (name kebab-case + non-empty description).
// Usage: node scripts/validate.mjs

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];
const warnings = [];

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

// 1. Manifest
const manifestPath = path.join(root, "openclaw.plugin.json");
if (!fs.existsSync(manifestPath)) {
  errors.push("missing openclaw.plugin.json");
} else {
  const m = readJson(manifestPath);
  if (!m.id || typeof m.id !== "string") errors.push("manifest.id is required (string)");
  if (!m.configSchema || typeof m.configSchema !== "object")
    errors.push("manifest.configSchema is required (object)");
  const skillDirs = Array.isArray(m.skills) ? m.skills : [];
  if (skillDirs.length === 0) warnings.push("manifest.skills is empty");
  for (const rel of skillDirs) {
    const abs = path.resolve(root, rel);
    if (!abs.startsWith(root)) errors.push(`skills entry escapes plugin root: ${rel}`);
    if (!fs.existsSync(abs)) errors.push(`skills dir not found: ${rel}`);
  }
}

// 2. Each bundled skill
const skillsRoot = path.join(root, "skills");
const kebab = /^[a-z0-9]+(-[a-z0-9]+)*$/;
if (fs.existsSync(skillsRoot)) {
  for (const entry of fs.readdirSync(skillsRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const skillMd = path.join(skillsRoot, entry.name, "SKILL.md");
    if (!fs.existsSync(skillMd)) {
      errors.push(`${entry.name}: missing SKILL.md`);
      continue;
    }
    const text = fs.readFileSync(skillMd, "utf8");
    const fm = text.match(/^---\n([\s\S]*?)\n---/);
    if (!fm) {
      errors.push(`${entry.name}: missing/invalid YAML frontmatter`);
      continue;
    }
    const body = fm[1];
    const nameMatch = body.match(/^name:\s*(.+)$/m);
    const name = nameMatch ? nameMatch[1].trim() : "";
    if (!name) errors.push(`${entry.name}: frontmatter missing name`);
    else if (!kebab.test(name)) errors.push(`${entry.name}: name "${name}" is not kebab-case`);
    else if (name !== entry.name) warnings.push(`${entry.name}: dir name != skill name "${name}"`);
    if (!/^description:/m.test(body)) errors.push(`${entry.name}: frontmatter missing description`);
  }
} else {
  errors.push("missing skills/ directory");
}

// 3. skill-factory-eval 关键脚本必须存在（全自动闭环 + 可视化 + 判定协议）
const evalScripts = [
  "static_trigger_score.py",
  "gen_eval_set.py",
  "split_eval.py",
  "aggregate_eval.py",
  "grader_adapter.py",
  "run_eval_loop.py",
  "generate_report.py",
];
const evalScriptDir = path.join(skillsRoot, "skill-factory-eval", "scripts");
for (const s of evalScripts) {
  const abs = path.join(evalScriptDir, s);
  if (!fs.existsSync(abs)) errors.push(`skill-factory-eval: missing script ${s}`);
}
const harnessRef = path.join(skillsRoot, "skill-factory-eval", "references", "eval-harness-protocol.md");
if (!fs.existsSync(harnessRef))
  warnings.push("skill-factory-eval: missing references/eval-harness-protocol.md");

// Report
for (const w of warnings) console.warn(`WARN  ${w}`);
if (errors.length) {
  for (const e of errors) console.error(`ERROR ${e}`);
  console.error(`\n${errors.length} error(s) found.`);
  process.exit(1);
}
console.log("OK: plugin manifest and bundled skills are valid.");
