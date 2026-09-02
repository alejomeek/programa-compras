/**
 * Formas de datos que consume la pantalla `/purchase-runs` (contrato §6.3,
 * §10.2, §11). DTO en camelCase, no las columnas crudas — mismo criterio que
 * `src/app/(app)/imports/types.ts`: el servidor resuelve joins y renombra,
 * los componentes son presentacionales y no saben de dónde salen los datos.
 */

import type { PurchaseRunStatus, PurchaseRunLineStatus } from "./run-status";
import type { TbcCatalogStatus } from "@/lib/purchase-runs/tbc-catalog";

export type PurchaseRunRow = {
  id: string;
  status: PurchaseRunStatus;
  supplierName: string | null;
  /** Fecha ISO `YYYY-MM-DD`, sin hora: periodo de negocio (mismo criterio que ImportJobRow). */
  periodStart: string;
  periodEnd: string;
  engineVersion: string;
  /** ISO datetime. */
  createdAt: string;
  calculatedAt: string | null;
};

export type TargetDayRow = {
  locationCode: string;
  locationName: string;
  targetDays: number;
};

export type PurchaseRunDetail = {
  id: string;
  status: PurchaseRunStatus;
  supplierId: string;
  supplierName: string | null;
  salesImportId: string;
  priceListId: string;
  inventorySnapshotId: string | null;
  periodStart: string;
  periodEnd: string;
  engineVersion: string;
  paramsHash: string;
  createdAt: string;
  calculatedAt: string | null;
  targetDays: TargetDayRow[];
};

export type PurchaseRunLineRow = {
  id: string;
  ean: string;
  productName: string | null;
  /** Presencia actual del EAN en el último catálogo SDOSXSUC activo. */
  tbcCatalogStatus: TbcCatalogStatus;
  locationCode: string;
  locationName: string;
  salesUnits: number;
  periodDays: number;
  dailySales: string;
  suggestedQuantity: number;
  finalQuantity: number;
  stockReference: number | null;
  unitCost: string | null;
  status: PurchaseRunLineStatus;
  note: string | null;
  rowVersion: number;
  updatedAt: string;
};

export type SalesImportOption = {
  id: string;
  periodStart: string;
  periodEnd: string;
  createdAt: string;
};

export type InventorySnapshotOption = {
  id: string;
  snapshotDate: string;
  createdAt: string;
};

export type PriceListOption = {
  id: string;
  version: number;
  effectiveDate: string;
  createdAt: string;
};

export type OperativeLocation = {
  code: string;
  name: string;
};

export type NewRunOptions = {
  salesImports: SalesImportOption[];
  inventorySnapshots: InventorySnapshotOption[];
  priceLists: PriceListOption[];
  operativeLocations: OperativeLocation[];
  defaultTargetDays: number;
};
