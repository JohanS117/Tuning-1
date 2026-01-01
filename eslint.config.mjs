import js from "@eslint/js";
import globals from "globals";
/*
Ejecutar el programa → "npm run lint"
*/
export default [
    {
        files: ["**/*.{js,mjs,cjs}"],
        languageOptions: {
            globals: {
                ...globals.browser,
                Spotify: "readonly"  // Agrega Spotify como variable global
            },
            ecmaVersion: 2021,
            sourceType: "module"
        },
        rules: {
            ...js.configs.recommended.rules,
            "no-console": "warn",  // Regla de no-console como advertencia
            "no-undef": "error"    // Regla de no-undef como error
        }
    }
];
