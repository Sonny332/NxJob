import { defineConfig } from "wxt";

export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  manifest: {
    name: "NxJob",
    description: "Lightweight job-application copilot.",
    permissions: ["activeTab", "tabs", "storage", "sidePanel"],
    host_permissions: ["http://127.0.0.1:8765/*", "http://localhost:8765/*"],
    action: {
      default_title: "NxJob"
    },
    side_panel: {
      default_path: "sidepanel.html"
    }
  }
});
