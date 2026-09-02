/**
 * Formateadores puros compartidos por Server y Client Components. No deben
 * vivir en `orders-view.tsx`, que es cliente por la selección para el ZIP.
 */
export function formatCop(value: string) {
  const amount = Number(value);
  return Number.isFinite(amount) ? `$ ${amount.toLocaleString("es-CO", { maximumFractionDigits: 0 })}` : "—";
}

export function formatOrderDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeZone: "America/Bogota",
  }).format(date);
}
