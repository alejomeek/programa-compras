/**
 * Validacion en cliente del archivo elegido, ANTES de pedir una URL firmada.
 *
 * No sustituye la validacion del servidor (el parseo real y el sha256 viven
 * alla, contrato §8): existe para no gastar una subida completa en un archivo
 * con la extension equivocada y para dar un mensaje accionable en el momento,
 * junto al campo (checklist §10.4: causa + accion concreta, nunca un codigo).
 *
 * Modulo de logica pura: recibe `{ name, size }`, no un `File` del navegador,
 * para poder probarse en Node sin DOM.
 */

import { importTypeDefinition, type ImportType } from "./import-types";

/** 25 MB. El SDOSXSUC real de referencia pesa ~2,8 MB; el margen es amplio a proposito. */
export const MAX_IMPORT_FILE_BYTES = 25 * 1024 * 1024;

export type FileCandidate = {
  name: string;
  size: number;
};

export type FileValidationResult = { ok: true } | { ok: false; message: string };

const BYTE_UNITS = ["B", "KB", "MB", "GB"] as const;

/**
 * Tamano legible en formato es-CO (coma decimal). Implementado a mano en vez
 * de con `Intl` para que el texto sea identico en el servidor, en el navegador
 * y en las pruebas, sin depender del ICU disponible.
 */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }

  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < BYTE_UNITS.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const rendered =
    unitIndex === 0 ? String(Math.round(value)) : value.toFixed(1).replace(/[.,]0$/, "");
  return `${rendered.replace(".", ",")} ${BYTE_UNITS[unitIndex]}`;
}

/**
 * Extension en minuscula y con punto (`".xlsx"`), o cadena vacia si no tiene.
 * Un nombre oculto sin extension (`.gitignore`) no cuenta como extension.
 */
export function fileExtension(fileName: string): string {
  const trimmed = fileName.trim();
  const lastDot = trimmed.lastIndexOf(".");
  if (lastDot <= 0 || lastDot === trimmed.length - 1) {
    return "";
  }
  return trimmed.slice(lastDot).toLowerCase();
}

/** Lista de extensiones en prosa: `.xlsx o .xls`. */
function listExtensions(extensions: readonly string[]): string {
  if (extensions.length === 1) {
    return extensions[0];
  }
  return `${extensions.slice(0, -1).join(", ")} o ${extensions[extensions.length - 1]}`;
}

export function validateImportFile(
  file: FileCandidate,
  type: ImportType,
  options: { maxBytes?: number } = {},
): FileValidationResult {
  const maxBytes = options.maxBytes ?? MAX_IMPORT_FILE_BYTES;
  const definition = importTypeDefinition(type);
  const name = file.name.trim();

  if (name.length === 0) {
    return {
      ok: false,
      message: "El archivo no tiene nombre. Vuelve a elegirlo desde tu equipo.",
    };
  }

  const extension = fileExtension(name);
  const esperado = listExtensions(definition.extensions);

  if (extension === "") {
    return {
      ok: false,
      message: `«${name}» no tiene extensión. Para ${definition.label} se espera ${esperado}; renombra el archivo o vuelve a exportarlo desde el origen.`,
    };
  }

  if (!definition.extensions.includes(extension)) {
    return {
      ok: false,
      message: `«${name}» es un archivo ${extension}. Para ${definition.label} se espera ${esperado}; elige el archivo correcto o cambia el tipo de importación.`,
    };
  }

  if (!Number.isFinite(file.size) || file.size <= 0) {
    return {
      ok: false,
      message: `«${name}» está vacío (0 bytes). Vuelve a exportarlo desde el origen y cárgalo de nuevo.`,
    };
  }

  if (file.size > maxBytes) {
    return {
      ok: false,
      message: `«${name}» pesa ${formatBytes(file.size)} y el máximo permitido es ${formatBytes(maxBytes)}. Exporta un período más corto o divide el archivo.`,
    };
  }

  return { ok: true };
}
