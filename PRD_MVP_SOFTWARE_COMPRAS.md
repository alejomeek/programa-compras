# PRD MVP: Software de Compras Jugando y Educando

## 1. Contexto

Jugando y Educando comercializa y distribuye juguetería y material didáctico a través de tiendas físicas y canales digitales. Actualmente las decisiones de compra se hacen "a ojo", sin cruzar sistemáticamente inventario actual, ventas históricas y listas de precios de proveedores.

La empresa usa TBC como ERP. TBC genera archivos con inventario, ventas y costos. Los proveedores envían listas de precios en formatos no estandarizados. Para el MVP se usará una plantilla normalizada de proveedor.

El MVP se construirá en Python + Streamlit, desplegado en Streamlit Cloud, sin base de datos ni persistencia.

## 2. Objetivo del producto

Construir una app que ayude a la persona encargada de compras a decidir qué productos pedir a un proveedor y qué costos cambiaron frente al sistema TBC.

El sistema debe:

1. Cruzar inventario actual, ventas históricas y lista de precios del proveedor.
2. Detectar cambios de costo entre TBC y proveedor.
3. Detectar productos nuevos, productos no encontrados en lista del proveedor y problemas de datos.
4. Calcular necesidades de reposición por ubicación.
5. Simular redistribución interna antes de recomendar compra.
6. Exportar los resultados a Excel.

## 3. Usuario principal

Persona encargada de compras de Jugando y Educando.

El usuario entiende términos internos como SKU, EAN, PVP, CEDI, comodín, SDOSXSUC e INVEPTOS. La app debe ser clara y guiada, pero puede usar lenguaje operativo interno.

## 4. Alcance del MVP

### Incluido

- App Streamlit.
- Carga de archivos TBC y plantilla proveedor.
- Configuración manual del comodín proveedor.
- Interruptor manual de Modo Feria.
- Configuración de días objetivo por ubicación.
- Configuración de mínimo por quiebre por ubicación.
- Comparación de costos.
- Recomendación de compra por SKU y por ubicación.
- Simulación de redistribución interna.
- Tablas en pantalla.
- Exportación a Excel multihoja.
- Plantilla proveedor `.xlsx` descargable.

### Excluido

- Base de datos.
- Login o roles.
- Persistencia de configuraciones.
- Recomendación automática de PVP.
- Cálculo de margen.
- Alertas por margen mínimo.
- Múltiplos de empaque.
- Compra inicial sugerida para productos nuevos.
- Integración directa con TBC.
- Integración directa con proveedores.
- Roadmap futuro.

## 5. Archivos de entrada

### 5.1 `SDOSXSUC.CSV`

Archivo generado por TBC con inventario actual y maestro de productos.

Columnas relevantes:

- `Codpro`: SKU.
- `Nompro`: nombre del producto.
- `Valuni`: PVP actual.
- `Codean`: código de barras / EAN.
- `Codea2`: comodín interno del proveedor.
- `us01`, `us02`, etc.: inventario por ubicación.
- `Nrotab`: no relevante.

El archivo se asume con formato estable.

### 5.2 `INVEPTOS.XLS`

Archivo generado por TBC con ventas históricas en un rango de fechas.

Columnas relevantes:

- `CODPRO`: SKU.
- `COMODI`: comodín interno, equivalente a `Codea2`.
- `DETALL`: nombre del producto.
- `VALUNI`: PVP.
- `VALCOS`: costo actual en TBC.
- `CODEAN`: código de barras / EAN.
- `FDESDE`: fecha inicial del periodo.
- `FHASTA`: fecha final del periodo.
- `TISUC#`: código de ubicación.
- `SDSUC#`: inventario por ubicación.
- `UNSUC#`: unidades vendidas por ubicación.
- `VTSUC#`: ventas por ubicación.
- `SDOFIN`: inventario total.
- `UNIVTA`: unidades vendidas totales.
- `TOTVTA`: ventas totales.

Se asume una sola fila por producto. Si hay duplicados, deben ir a problemas de datos.

### 5.3 Plantilla proveedor `.xlsx`

La app debe permitir descargar una plantilla vacía con estas columnas obligatorias:

```text
EAN-13
Costo proveedor
```

La app recibirá esta plantilla ya normalizada. Se asume que todo producto listado está disponible para compra.

Se asume una sola fila por EAN. Si hay duplicados, deben ir a problemas de datos.

## 6. Identificación del proveedor

El usuario ingresa manualmente el comodín del proveedor, por ejemplo:

```text
745
```

El sistema debe extraer el comodín desde `Codea2` y `COMODI` tomando los tres primeros dígitos después del punto.

Ejemplo:

```text
.745LAS900203 -> 745
.745LAS900201 -> 745
```

Si `Codea2` o `COMODI` está vacío, no tiene punto, o tiene menos de tres dígitos después del punto:

- marcar como problema de datos;
- excluir del filtro del proveedor.

Si el comodín ingresado no existe en `SDOSXSUC`, el análisis debe bloquearse.

Si el comodín existe en `SDOSXSUC` pero no aparece en `INVEPTOS`, el análisis debe continuar con advertencia.

## 7. Llave de cruce

La llave principal entre archivos es el EAN / código de barras.

Mapeo:

- `SDOSXSUC.Codean`
- `INVEPTOS.CODEAN`
- `Plantilla proveedor.EAN-13`

Los EAN deben tratarse como texto exacto.

Reglas:

- preservar ceros a la izquierda;
- no convertir a número;
- no limpiar automáticamente;
- si viene con espacios, `.0`, guiones o caracteres no numéricos, enviar a problemas de datos;
- no exigir longitud exacta de 13 dígitos.

Si un producto del comodín tiene `Codean` vacío o inválido en TBC:

- va a problemas de datos;
- queda fuera del cruce con proveedor;
- no se evalúa como cambio de costo;
- no se marca como descontinuado/no encontrado.

## 8. Ubicaciones

### 8.1 Códigos de ubicación

En `INVEPTOS`, las columnas `TISUC#` definen a qué ubicación corresponden `SDSUC#`, `UNSUC#` y `VTSUC#`.

| Código | Ubicación |
|---:|---|
| 10000 | Av. 19 |
| 10010 | Bulevar |
| 10500 | Calle 74 |
| 10510 | Bvista |
| 10600 | Feria |
| 10800 | Oviedo |
| 20010 | CEDI |
| 20020 | Full MercadoLibre |
| 20030 | Bodega Bqlla |

### 8.2 Mapeo `SDOSXSUC` sin Modo Feria

| Columna | Ubicación |
|---|---|
| `us01` | Av. 19 |
| `us02` | Bulevar |
| `us03` | Calle 74 |
| `us04` | Bvista |
| `us05` | Oviedo |
| `us06` | CEDI |
| `us07` | Sin uso |
| `us08` | Full MercadoLibre |
| `us09` | Bodega Bqlla |

### 8.3 Mapeo `SDOSXSUC` con Modo Feria

| Columna | Ubicación |
|---|---|
| `us01` | Av. 19 |
| `us02` | Bulevar |
| `us03` | Calle 74 |
| `us04` | Bvista |
| `us05` | Feria |
| `us06` | Oviedo |
| `us07` | CEDI |
| `us08` | Full MercadoLibre |
| `us09` | Bodega Bqlla |

`us08` y `us09` pueden aparecer tanto en modo normal como en modo Feria. Si no existen, se tratan como inventario `0`.

## 9. Comportamiento por ubicación

### Ubicaciones operativas con reposición

- Av. 19
- Bulevar
- Calle 74
- Bvista
- Oviedo
- CEDI

### Full MercadoLibre

- Sus ventas sí afectan la demanda.
- Sus ventas se cargan al CEDI.
- Su inventario no cuenta como disponible.
- No recibe stock.
- No envía stock.
- Se muestra como referencia.

### Feria

- Se ignora en cálculos.
- No aporta demanda.
- No aporta inventario disponible.
- No recibe stock.
- No envía stock.
- Se muestra como referencia.

### Bodega Bqlla

- Nunca vende.
- No tiene demanda propia.
- No es destino de reposición.
- Todo su inventario puede usarse para abastecer Bvista y Calle 74.
- Es fuente prioritaria para Barranquilla antes que CEDI.

## 10. Configuración del análisis

El usuario debe configurar:

1. Archivo `SDOSXSUC.CSV`.
2. Archivo `INVEPTOS.XLS`.
3. Plantilla proveedor `.xlsx`.
4. Comodín proveedor.
5. Nombre proveedor opcional.
6. Modo Feria activado/desactivado.
7. Días objetivo global.
8. Días objetivo por ubicación.
9. Mínimo por quiebre por ubicación.

El global prellena los días objetivo por ubicación, pero el usuario puede ajustar cada una.

Ubicaciones configurables:

- Av. 19
- Bulevar
- Calle 74
- Bvista
- Oviedo
- CEDI

Full MercadoLibre usa los días objetivo del CEDI, porque su demanda se carga al CEDI.

El mínimo por quiebre también aplica al CEDI.

## 11. Cálculo de periodo histórico

El periodo se toma de `FDESDE` y `FHASTA`.

```text
dias_periodo = FHASTA - FDESDE + 1
```

Ejemplo:

```text
1 de enero a 30 de enero = 30 días
```

La venta diaria se calcula como:

```text
venta_diaria = unidades_vendidas / dias_periodo
```

## 12. Cálculo de necesidad

Para cada SKU y ubicación operativa:

### Caso 1: ventas mayores a cero

```text
objetivo_bruto = venta_diaria * dias_objetivo_ubicacion
objetivo_redondeado = ceil(objetivo_bruto)
necesidad = max(0, objetivo_redondeado - inventario_actual)
```

### Caso 2: ventas cero e inventario mayor a cero

```text
necesidad = 0
```

Interpretación: había inventario pero no rotó.

### Caso 3: ventas cero e inventario cero

```text
necesidad = minimo_quiebre_ubicacion
estado = revision_manual / posible quiebre
```

Interpretación: no se puede concluir que no haya demanda, porque pudo haber quiebre de inventario.

Estos casos:

- deben marcarse para revisión manual;
- sí afectan la compra sugerida total;
- sí pueden cubrirse primero con redistribución interna.

## 13. Cálculo especial del CEDI

Para CEDI:

```text
ventas_CEDI_ajustadas = ventas_CEDI + ventas_Full_MercadoLibre
```

El inventario de CEDI es solo el inventario físico de CEDI.

El inventario de Full MercadoLibre no se suma al inventario disponible.

## 14. Excedentes

Para ubicaciones con objetivo propio:

```text
excedente = max(0, inventario_actual - objetivo_redondeado)
```

Para Bodega Bqlla:

```text
excedente = inventario_actual
```

Full MercadoLibre y Feria nunca tienen excedente redistribuible.

## 15. Redistribución interna

Antes de recomendar compra, el sistema debe simular redistribución interna.

### Priorización de receptores

Cuando varias tiendas necesitan unidades del mismo SKU:

1. Mayor necesidad calculada.
2. Empate por orden fijo:
   - Av. 19
   - Bulevar
   - Oviedo
   - Bvista
   - Calle 74

### Priorización de fuentes

Cuando varias fuentes locales pueden enviar:

1. Ubicación con mayor excedente.

### Reglas por ciudad

#### Bogotá

Para Av. 19 y Bulevar:

1. CEDI primero, usando solo su excedente.
2. Luego excedentes entre Av. 19 y Bulevar.
3. Luego compra al proveedor.

#### Medellín

Para Oviedo:

1. CEDI primero, usando solo su excedente.
2. Luego compra al proveedor.

#### Barranquilla

Para Bvista y Calle 74:

1. Bodega Bqlla primero.
2. Luego CEDI, usando solo su excedente.
3. Luego excedentes entre Bvista y Calle 74.
4. Luego compra al proveedor.

## 16. Compra sugerida

Después de simular redistribución:

```text
compra_sugerida_ubicacion = necesidad_restante_ubicacion
compra_sugerida_total_SKU = suma de compra_sugerida_ubicacion
```

La compra se maneja en unidades exactas enteras, redondeadas hacia arriba desde la necesidad por ubicación.

No se aplican múltiplos de empaque.

La compra sugerida aplica solo a productos que:

- pertenecen al proveedor según comodín;
- existen en TBC;
- tienen EAN válido;
- existen en la lista proveedor;
- tienen necesidad después de redistribución.

Los productos nuevos se listan, pero no tienen compra inicial sugerida.

## 17. Cambios de costo

El costo actual de TBC se toma de:

```text
INVEPTOS.VALCOS
```

El costo proveedor se toma de:

```text
Plantilla proveedor.Costo proveedor
```

La comparación se hace por EAN.

La app debe mostrar todos los productos donde:

```text
VALCOS != Costo proveedor
```

No debe aplicar tolerancia mínima.

Debe mostrar:

- SKU
- EAN
- Nombre producto
- PVP actual
- Costo TBC
- Costo proveedor
- Diferencia absoluta
- Diferencia porcentual

No debe calcular margen ni sugerir PVP.

## 18. Pestañas / salidas en Streamlit

La app debe mostrar al menos estas pestañas:

1. **Resumen**
   - proveedor / comodín;
   - modo Feria;
   - rango de fechas detectado;
   - días del periodo;
   - productos analizados;
   - productos con compra sugerida;
   - productos con revisión manual;
   - cambios de costo;
   - productos nuevos;
   - productos descontinuados/no encontrados;
   - problemas de datos.

2. **Compra sugerida**
   - SKU;
   - EAN;
   - producto;
   - PVP actual;
   - costo proveedor;
   - compra total sugerida;
   - desglose por ubicación después de redistribución;
   - inventario actual por ubicación;
   - ventas históricas por ubicación;
   - necesidad inicial por ubicación;
   - redistribución recibida por ubicación;
   - compra final por ubicación;
   - flags de revisión manual.

3. **Redistribución sugerida**
   - SKU;
   - EAN;
   - producto;
   - origen;
   - destino;
   - cantidad;
   - regla aplicada.

4. **Revisión manual / posibles quiebres**
   - SKU;
   - EAN;
   - producto;
   - ubicación;
   - ventas en periodo;
   - inventario actual;
   - mínimo aplicado;
   - motivo.

5. **Cambios de costo**

6. **Productos nuevos**
   - productos en lista proveedor que no existen en TBC por EAN.

7. **Productos descontinuados / no encontrados en lista del proveedor**
   - productos en `SDOSXSUC` con comodín proveedor que no aparecen en la lista proveedor.

8. **Sin costo TBC / no encontrado en ventas históricas**
   - productos del proveedor presentes en `SDOSXSUC`, pero sin registro usable en `INVEPTOS`.

9. **Problemas de datos**
   - EAN inválido;
   - comodín inválido;
   - duplicados;
   - columnas faltantes;
   - filas fuera de cruce por datos incompletos.

## 19. Filtros

La app debe incluir filtros principales:

- Buscar por SKU, EAN o nombre.
- Mostrar solo compra sugerida > 0.
- Mostrar solo revisión manual.
- Filtrar por tienda con compra sugerida > 0.
- Filtrar por productos con cambio de costo.
- Filtrar por productos nuevos.
- Filtrar por productos descontinuados/no encontrados.
- Filtrar por problemas de datos.

## 20. Exportación Excel

La app debe permitir descargar un Excel con varias hojas:

- `Resumen`
- `Compra sugerida`
- `Redistribución sugerida`
- `Revisión manual`
- `Cambios de costo`
- `Productos nuevos`
- `Descontinuados no encontrados`
- `Sin costo TBC`
- `Problemas de datos`

El Excel debe contener los mismos resultados principales visibles en Streamlit.

## 21. Validaciones y errores

El análisis debe bloquearse si:

- no se carga `SDOSXSUC`;
- no se carga plantilla proveedor;
- falta una columna obligatoria crítica;
- el comodín ingresado no aparece en `SDOSXSUC`;
- la plantilla proveedor no tiene `EAN-13` o `Costo proveedor`.

El análisis debe continuar con advertencia si:

- el comodín no aparece en `INVEPTOS`;
- faltan columnas opcionales de ubicaciones como `us08` o `us09`;
- hay productos sin costo TBC.

Los problemas de datos deben mostrarse en una pestaña separada, no ocultarse.

## 22. Requisitos técnicos

- Lenguaje: Python.
- Framework: Streamlit.
- Deploy objetivo: Streamlit Cloud.
- Procesamiento en memoria.
- Sin base de datos.
- Sin persistencia entre sesiones.
- Librerías sugeridas:
  - `pandas`
  - `openpyxl`
  - lector compatible con `.xls`, según disponibilidad
  - `xlsxwriter` u `openpyxl` para exportación

## 23. Criterios de éxito del MVP

El MVP se considera exitoso si permite a compras:

1. Cargar los tres archivos requeridos.
2. Filtrar correctamente productos por comodín.
3. Cruzar productos por EAN exacto.
4. Identificar cambios de costo entre TBC y proveedor.
5. Ver productos nuevos del proveedor.
6. Ver productos de TBC no encontrados en la lista del proveedor.
7. Calcular necesidades por ubicación usando días objetivo configurables.
8. Detectar posibles quiebres con ventas cero e inventario cero.
9. Simular redistribución interna según reglas de ciudad.
10. Obtener compra sugerida final por SKU y ubicación.
11. Descargar un Excel operativo con los resultados.
