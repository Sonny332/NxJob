import { defineConfig } from "wxt";

const releaseVersion = process.env.NXJOB_EXTENSION_VERSION;
const releaseVersionName = process.env.NXJOB_RELEASE_VERSION;

export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  outDir: process.env.NXJOB_WXT_OUT_DIR,
  manifest: {
    name: "NxJob",
    description: "Lightweight job-application copilot.",
    ...(releaseVersion ? { version: releaseVersion } : {}),
    ...(releaseVersionName ? { version_name: releaseVersionName } : {}),
    icons: {
      "16": "assets/icons/nxjob-16.png",
      "32": "assets/icons/nxjob-32.png",
      "48": "assets/icons/nxjob-48.png",
      "128": "assets/icons/nxjob-128.png"
    },
    permissions: ["activeTab", "tabs", "storage", "sidePanel", "scripting"],
    host_permissions: [
      "http://127.0.0.1:8765/*",
      "http://localhost:8765/*",
      "https://www.linkedin.com/*",
      "https://linkedin.com/*"
    ],
    action: {
      default_title: "NxJob",
      default_icon: {
        "16": "assets/icons/nxjob-16.png",
        "32": "assets/icons/nxjob-32.png"
      }
    },
    side_panel: {
      default_path: "sidepanel.html"
    }
  }
});
