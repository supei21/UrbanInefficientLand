import eslint from "@eslint/js";
import prettier from "@vue/eslint-config-prettier/skip-formatting";
import { withVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";
import vue from "eslint-plugin-vue";

export default withVueTs(
  eslint.configs.recommended,
  ...vue.configs["flat/recommended"],
  vueTsConfigs.recommended,
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  prettier,
);
