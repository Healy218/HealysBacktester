import { defineConfig } from "vite";
export default defineConfig({
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "firestore", test: /node_modules\/@firebase\/firestore\// },
            { name: "firebase-auth", test: /node_modules\/@firebase\/auth\// },
            {
              name: "firebase-core",
              test: /node_modules\/(?:@firebase|firebase)\//,
            },
            {
              name: "react",
              test: /node_modules\/(?:react|react-dom|scheduler)\//,
            },
            { name: "validation", test: /node_modules\/zod\// },
          ],
        },
      },
    },
  },
  server: { host: "127.0.0.1", port: 5173, strictPort: true },
});
