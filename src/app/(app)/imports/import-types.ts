/**
 * Catalogo de tipos de importacion de la pantalla `/imports`.
 *
 * Los tres valores son EXACTAMENTE los del enum de `import_jobs.type`
 * (docs/IMPLEMENTATION_CONTRACT.md §6.3). Las extensiones aceptadas salen de
 * §3.1–3.3, verificadas contra los archivos reales:
 *   - SDOSXSUC es un CSV `;` Latin-1.
 *   - INVEPTOS es un `.xls` legado (BIFF, leido con `xlrd`).
 *   - La lista de proveedor llega como `.xlsx` (plantilla) o `.xls` (export real).
 *
 * Modulo de logica pura: sin React, sin acceso a datos. Lo consumen tanto la
 * UI como sus pruebas unitarias.
 */

export const IMPORT_TYPES = ["sdos_inventory", "inveptos_sales", "supplier_price_list"] as const;

export type ImportType = (typeof IMPORT_TYPES)[number];

export type ImportTypeDefinition = {
  value: ImportType;
  /** Etiqueta corta para el selector y la tabla. */
  label: string;
  /** Nombre del archivo de origen tal como lo exporta TBC o el proveedor. */
  sourceName: string;
  /** Que aporta esta importacion al proceso de compras. */
  description: string;
  /** Extensiones aceptadas, en minuscula y con punto. */
  extensions: readonly string[];
  /** Solo la lista de precios cuelga de un proveedor (`import_jobs.supplier_id`). */
  requiresSupplier: boolean;
};

export const IMPORT_TYPE_DEFINITIONS: readonly ImportTypeDefinition[] = [
  {
    value: "inveptos_sales",
    label: "Ventas TBC (INVEPTOS)",
    sourceName: "INVEPTOS.XLS",
    description:
      "Unidades vendidas por punto y costo TBC. Es el unico insumo de la sugerencia de compra: sin el no hay corrida.",
    extensions: [".xls"],
    requiresSupplier: false,
  },
  {
    value: "sdos_inventory",
    label: "Inventario TBC (SDOSXSUC)",
    sourceName: "SDOSXSUC.CSV",
    description:
      "Existencias por punto y catalogo de EAN. Es solo referencia: el inventario nunca resta de la cantidad sugerida.",
    extensions: [".csv"],
    requiresSupplier: false,
  },
  {
    value: "supplier_price_list",
    label: "Lista de precios de proveedor",
    sourceName: "Lista del proveedor",
    description:
      "Costos vigentes del proveedor para comparar contra el costo TBC. Requiere elegir el proveedor al que pertenece.",
    extensions: [".xlsx", ".xls"],
    requiresSupplier: true,
  },
] as const;

/** Definicion de un tipo. Lanza si el valor no pertenece al enum del contrato. */
export function importTypeDefinition(type: ImportType): ImportTypeDefinition {
  const definition = IMPORT_TYPE_DEFINITIONS.find((item) => item.value === type);
  if (!definition) {
    throw new Error(`Tipo de importacion desconocido: ${type}`);
  }
  return definition;
}

export function isImportType(value: string): value is ImportType {
  return (IMPORT_TYPES as readonly string[]).includes(value);
}

/** Etiqueta legible; nunca devuelve el valor crudo del enum (checklist §10.4). */
export function importTypeLabel(type: string): string {
  return isImportType(type) ? importTypeDefinition(type).label : "Tipo no reconocido";
}

/** Valor para el atributo `accept` de un `<input type="file">`. */
export function acceptAttribute(type: ImportType): string {
  return importTypeDefinition(type).extensions.join(",");
}
