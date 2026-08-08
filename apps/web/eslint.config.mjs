import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { process: "readonly", console: "readonly" },
    },
    rules: {
      "@typescript-eslint/consistent-type-imports": "error",
      "no-restricted-globals": [
        "error",
        { name: "localStorage", message: "Use lib/session.ts." },
      ],
    },
  },
);
