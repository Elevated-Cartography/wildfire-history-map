import { execSync } from "node:child_process";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// The project's GitHub page, for the About dialog: from GitHub Actions'
// GITHUB_REPOSITORY when deploying, otherwise the origin remote
function repoUrl() {
  let repo = process.env.GITHUB_REPOSITORY;
  if (!repo) {
    try {
      const origin = execSync("git remote get-url origin", { encoding: "utf8" }).trim();
      repo = /github\.com[:/](.+?)(\.git)?$/.exec(origin)?.[1];
    } catch {
      // Not a git checkout, or no origin: no link
    }
  }
  return repo ? `https://github.com/${repo}` : null;
}

export default defineConfig({
  plugins: [vue()],
  define: {
    __REPO_URL__: JSON.stringify(repoUrl()),
  },
  // Relative URLs so the built site works at any path, e.g. GitHub Pages'
  // https://<user>.github.io/surtr/
  base: "./",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    // MapLibre alone is ~1MB, there's no getting under the default 500kB
    chunkSizeWarningLimit: 2000,
  },
});
