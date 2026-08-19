import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Pruebas unitarias de logica pura de la capa web.
 *
 * En la Fase 1 solo hay dos modulos con logica testeable sin backend: las
 * reglas de rol y la construccion del menu. Los componentes de React y los
 * flujos de Auth se prueban cuando exista un proyecto de Supabase real; no se
 * mockea un backend falso para simular sesiones.
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
