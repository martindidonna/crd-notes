import type { Config } from "tailwindcss";

export default {
  content: ["./frontend/index.html", "./frontend/src/**/*.{svelte,ts}"],
  theme: {
    extend: {}
  },
  plugins: []
} satisfies Config;
