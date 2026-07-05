import { readFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const sourcePath = path.resolve(root, "apps/extension/wxt.config.ts");

const requiredHostPermissions = [
  "http://127.0.0.1:8765/*",
  "http://localhost:8765/*",
  "https://www.linkedin.com/*",
  "https://linkedin.com/*"
];
const allowedHostPermissions = new Set(requiredHostPermissions);

function argValue(name) {
  const index = process.argv.indexOf(name);
  if (index === -1) {
    return "";
  }
  return process.argv[index + 1] || "";
}

function extractStringArray(source, key) {
  const pattern = new RegExp(`${key}\\s*:\\s*\\[([\\s\\S]*?)\\]`, "m");
  const match = source.match(pattern);
  if (!match) {
    throw new Error(`Could not find ${key} in wxt.config.ts`);
  }

  return [...match[1].matchAll(/["']([^"']+)["']/g)].map((entry) => entry[1]);
}

async function main() {
  const expectedReleaseVersion = argValue("--version");
  const source = await readFile(sourcePath, "utf8");
  const sourceHosts = extractStringArray(source, "host_permissions");
  validateHostPermissions(sourceHosts, "wxt.config.ts");

  if (process.argv.includes("--check-built")) {
    const builtManifestPath = path.resolve(
      root,
      process.env.NXJOB_WXT_BUILT_MANIFEST ||
        "apps/extension/.output/chrome-mv3/manifest.json"
    );
    const manifest = JSON.parse(await readFile(builtManifestPath, "utf8"));
    const builtHosts = Array.isArray(manifest.host_permissions) ? manifest.host_permissions : [];
    validateHostPermissions(builtHosts, "Generated manifest");
    if (expectedReleaseVersion) {
      validateVersion(manifest, expectedReleaseVersion);
    }
  }

  console.log("Extension manifest host permission validation passed.");
}

function validateVersion(manifest, expectedReleaseVersion) {
  const expectedChromeVersion = chromeVersionFromRelease(expectedReleaseVersion);
  if (manifest.version !== expectedChromeVersion) {
    throw new Error(
      `Generated manifest version '${manifest.version}' does not match expected Chrome version '${expectedChromeVersion}'.`
    );
  }
  if (
    manifest.version_name !== expectedReleaseVersion &&
    (expectedReleaseVersion !== expectedChromeVersion || manifest.version_name)
  ) {
    throw new Error(
      `Generated manifest version_name '${manifest.version_name}' does not match expected release version '${expectedReleaseVersion}'.`
    );
  }
}

function chromeVersionFromRelease(releaseVersion) {
  const match = releaseVersion.match(/^(\d+\.\d+\.\d+(?:\.\d+)?)/);
  if (!match) {
    throw new Error(`Release version '${releaseVersion}' does not start with a Chrome extension compatible numeric version.`);
  }
  return match[1];
}

function validateHostPermissions(hosts, label) {
  const missing = requiredHostPermissions.filter((host) => !hosts.includes(host));
  if (missing.length > 0) {
    throw new Error(`${label} is missing required host permissions: ${missing.join(", ")}`);
  }

  const unexpected = hosts.filter((host) => !allowedHostPermissions.has(host));
  if (unexpected.length > 0) {
    throw new Error(`${label} has unexpected host permissions: ${unexpected.join(", ")}`);
  }
}

await main();
