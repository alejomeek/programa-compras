"""Motor de dominio del Programa de Compras Web.

Paquete importable sin Streamlit ni dependencias de UI. Contiene únicamente
lógica de lectura, validación y (a partir de la Fase 3) recomendación de compra.

Módulos:
    - ``engine.validation``: reglas transversales (EAN, comodín, fechas TBC,
      período inclusivo bloqueante, números es-CO, registro de incidencias).
    - ``engine.readers``: lectura de las tres fuentes (SDOSXSUC, INVEPTOS,
      lista de precios de proveedor).
    - ``engine.imports``: orquestación de una importación (validación fila por
      fila y mapeo a las columnas de `sales_*`/`inventory_*`/`price_list*`).
      No toca base de datos.
    - ``engine.persistence``: escritura transaccional de una importación
      preparada, sobre una conexión DB-API **inyectada**. El paquete nunca
      abre conexiones ni lee credenciales.
    - ``engine.recommendation``: pendiente de Fase 3 del runbook.

Reglas invariantes del dominio (contrato §5.1):
    - El EAN es texto exacto en toda la cadena; nunca pasa por un tipo numérico.
    - No existe redistribución, excedentes, mínimos por quiebre, transferencias
      ni "objetivo de inventario". El inventario es solo referencia.
"""

from __future__ import annotations

__all__ = ["__version__"]

#: Versión del motor. Se persiste en ``purchase_runs.engine_version`` para
#: poder reproducir una corrida con el mismo código que la generó.
__version__ = "0.1.0"
