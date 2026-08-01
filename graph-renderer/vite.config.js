import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  build: {
    emptyOutDir: false,
    lib: {
      entry: fileURLToPath(new URL("main.js", import.meta.url)),
      formats: ["es"],
      fileName: () => "graph.js"
    },
    rollupOptions: {
      output: {
        entryFileNames: "graph.js"
      }
    }
  }
});
