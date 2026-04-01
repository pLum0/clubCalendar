export default [
  {
    ignores: ["**/*.html"],
  },
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: "script",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        fetch: "readonly",
        alert: "readonly",
        localStorage: "readonly",
        setTimeout: "readonly",
        location: "readonly",
        URLSearchParams: "readonly",
        encodeURIComponent: "readonly",
        decodeURIComponent: "readonly",
        JSON: "readonly",
        FormData: "readonly",
        HTMLElement: "readonly",
        Event: "readonly",
      },
    },
    rules: {
      "no-undef": "off",
      "no-unused-vars": "off",
      "prefer-const": "warn",
      "no-var": "off",
    },
  },
];
