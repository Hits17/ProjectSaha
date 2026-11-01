#!/usr/bin/env node
// Check the installed pnpm graph without treating dependencies' own dev tools
// as application requirements. Does not install or change packages.
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");

const root = path.resolve(__dirname, "..");
const apps = process.argv.slice(2);
let failures = 0;
for (const app of apps.length ? apps : ["frontend", "admin"]) {
  const directory = path.resolve(root, "apps", app);
  const appRequire = createRequire(path.join(directory, "package.json"));
  const semver = appRequire("next/dist/compiled/semver");
  const visited = new Set();
  let requirements = 0;
  let optionalMissing = 0;
  const errors = [];

  function findPackage(from, name) {
    let cursor = from;
    while (true) {
      const manifest = path.join(cursor, "node_modules", name, "package.json");
      if (fs.existsSync(manifest)) return fs.realpathSync(manifest);
      const parent = path.dirname(cursor);
      if (parent === cursor) return null;
      cursor = parent;
    }
  }

  function checkRequirement(from, owner, name, range, optional, traverse) {
    requirements++;
    const manifest = findPackage(from, name);
    if (!manifest) {
      if (optional) optionalMissing++;
      else errors.push(`${owner}: missing ${name}@${range}`);
      return;
    }
    const installed = JSON.parse(fs.readFileSync(manifest, "utf8"));
    if (!semver.validRange(range)) errors.push(`${owner}: unsupported requirement ${name}@${range}`);
    else if (!semver.satisfies(installed.version, range, { includePrerelease: true })) {
      errors.push(`${owner}: ${name}@${installed.version} does not satisfy ${range}`);
    }
    if (traverse) visit(manifest, false);
  }

  function visit(manifest, isRoot) {
    if (visited.has(manifest)) return;
    visited.add(manifest);
    const pkg = JSON.parse(fs.readFileSync(manifest, "utf8"));
    const from = path.dirname(manifest);
    const owner = `${pkg.name}@${pkg.version}`;
    if (pkg.engines?.node && !semver.satisfies(process.version, pkg.engines.node, { includePrerelease: true })) {
      errors.push(`${owner}: Node ${process.version} does not satisfy ${pkg.engines.node}`);
    }
    const dependencies = { ...pkg.dependencies, ...(isRoot ? pkg.devDependencies : {}) };
    for (const [name, range] of Object.entries(dependencies)) {
      if (!(name in (pkg.optionalDependencies || {}))) checkRequirement(from, owner, name, range, false, true);
    }
    for (const [name, range] of Object.entries(pkg.optionalDependencies || {})) {
      checkRequirement(from, owner, name, range, true, true);
    }
    for (const [name, range] of Object.entries(pkg.peerDependencies || {})) {
      checkRequirement(from, owner, name, range, !!pkg.peerDependenciesMeta?.[name]?.optional, false);
    }
  }

  visit(path.join(directory, "package.json"), true);
  console.log(`${app}: ${visited.size - 1} installed packages, ${requirements} dependency/peer requirements, ${optionalMissing} absent optional dependencies`);
  if (errors.length) {
    failures++;
    for (const error of errors) console.error(`  FAIL ${error}`);
  } else console.log(`  PASS required dependency ranges, peer ranges and Node engine constraints`);
}
process.exitCode = failures ? 1 : 0;
