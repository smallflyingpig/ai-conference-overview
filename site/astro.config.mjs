import { defineConfig } from "astro/config";
import react from "@astrojs/react";

export default defineConfig({
  site: "https://smallflyingpig.github.io",
  base: "/ai-conference-overview",
  output: "static",
  integrations: [react()],
});
