/**
 * Formas de datos de `/suppliers`. DTO en camelCase, mismo criterio que
 * `imports/types.ts`. Alcance MÍNIMO a propósito (hallazgo post Fase 3: no
 * había ninguna forma de crear un proveedor desde la app — `/suppliers`
 * nunca se asignó a ningún agente en el plan original, ver contrato §4):
 * crear + listar, no edición ni versiones de lista de precios (eso sigue
 * fuera de alcance, ver docs/IMPLEMENTATION_CONTRACT.md).
 */

export type SupplierRow = {
  id: string;
  name: string;
  tbcCode: string;
  nit: string | null;
  active: boolean;
  createdAt: string;
};
