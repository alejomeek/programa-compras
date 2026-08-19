/**
 * Aviso a mostrar tras crear una importación cuando el procesamiento
 * automático no arrancó.
 *
 * `POST /api/imports` (contrato §8/§11) crea `files`+`import_jobs` y luego
 * dispara `POST /api/imports_process`; si ese segundo paso no responde 2xx
 * (función no desplegada, `INTERNAL_API_SECRET` sin configurar, error 500
 * del lado de la función), la importación igual queda creada — nunca se
 * pierde el registro por un problema del otro componente — pero se queda
 * "En cola" sin que nadie la procese hasta un reintento. Eso no puede
 * quedar en silencio para quien acaba de subir el archivo (hotfix de
 * producción, ver docs/IMPLEMENTATION_CONTRACT.md §15).
 */
export function processingWarning(response: {
  processingTriggered: boolean;
  processingError?: string | null;
}): string | null {
  if (response.processingTriggered) {
    return null;
  }
  return (
    response.processingError ??
    "El archivo se subió pero el procesamiento automático no se pudo iniciar. " +
      "Actualiza la lista más tarde o avisa al equipo técnico."
  );
}
