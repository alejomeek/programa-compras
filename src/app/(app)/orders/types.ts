export type PurchaseOrderStatus = "draft" | "issued" | "cancelled";

export type PurchaseOrderRow = {
  id: string;
  orderNumber: string | null;
  status: PurchaseOrderStatus;
  supplierName: string;
  locationCode: string;
  locationName: string;
  totalUnits: number;
  subtotal: string;
  createdAt: string;
  issuedAt: string | null;
  cancelledAt: string | null;
};

export type PurchaseOrderItemRow = {
  id: string;
  ean: string;
  productName: string;
  tbcSku: string | null;
  unitCost: string;
  quantity: number;
  lineTotal: string;
};

export type PurchaseOrderDetail = PurchaseOrderRow & {
  supplierId: string;
  locationId: string;
  purchaseRunId: string | null;
  notes: string;
  pdfFileId: string | null;
  cancelledBy: string | null;
  cancelReason: string | null;
  items: PurchaseOrderItemRow[];
};
