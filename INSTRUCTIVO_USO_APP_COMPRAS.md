# Instructivo de uso - App de Compras Jugando y Educando

Este instructivo explica, paso a paso, como usar la app de compras para analizar inventario, ventas historicas, lista de precios del proveedor y generar ordenes de compra.

La app ayuda a responder tres preguntas principales:

1. Que productos cambiaron de costo frente al costo actual en TBC.
2. Que productos conviene comprar para reponer inventario por punto.
3. Que unidades se pueden redistribuir entre bodegas y tiendas antes de comprar.

## 1. Que archivos se necesitan

Para hacer un analisis completo se cargan tres archivos:

### SDOSXSUC.CSV

Este archivo sale de TBC y contiene el inventario actual por producto y por bodega.

La app usa este archivo para saber:

- SKU del producto.
- EAN o codigo de barras.
- Nombre del producto.
- PVP actual.
- Inventario actual por punto.
- Comodin del proveedor.

### INVEPTOS.XLS

Este archivo sale de TBC y contiene ventas historicas dentro de un rango de fechas.

La app usa este archivo para saber:

- Cuantas unidades vendio cada producto.
- En que puntos vendio.
- Cual es el costo actual registrado en TBC.
- Cual fue el periodo analizado, segun `FDESDE` y `FHASTA`.

### Plantilla proveedor

Este archivo contiene la lista de precios del proveedor, ya normalizada para la app.

Debe tener estas columnas:

- `EAN-13`
- `Nombre`
- `Costo proveedor`

Si no tienes la plantilla, la puedes descargar desde la app con el boton **Descargar plantilla proveedor**.

## 2. Como ejecutar el analisis

1. Abre la app de compras.
2. En la barra lateral, carga los archivos:
   - `SDOSXSUC.CSV`
   - `INVEPTOS.XLS`
   - `Plantilla proveedor`
3. En la seccion **Proveedor**, escribe:
   - **Comodin proveedor**: por ejemplo `745`.
   - **Nombre proveedor**: por ejemplo `SPEKTRA`.
4. Activa **Modo Feria** solamente si el archivo de inventario viene con Feria activa.
5. En **Reposicion**, define:
   - **Dias objetivo global**: dias de inventario que se quieren cubrir.
   - **Minimo quiebre global**: cantidad minima para puntos sin venta y sin inventario.
6. Revisa la tabla **Parametros por ubicacion**.
   - Puedes ajustar los dias objetivo por cada punto.
   - Puedes ajustar el minimo de quiebre por cada punto.
7. Haz clic en **Ejecutar analisis**.

Cuando termina el calculo, la app muestra varias pestanas y permite descargar el Excel del analisis.

## 3. Que hace la app por dentro

La app cruza tres fuentes:

- Inventario actual desde `SDOSXSUC.CSV`.
- Ventas historicas desde `INVEPTOS.XLS`.
- Costos nuevos desde la plantilla del proveedor.

Con esa informacion:

- Calcula el inventario objetivo por punto.
- Mira si hay inventario disponible para redistribuir antes de comprar.
- Calcula la compra sugerida.
- Identifica cambios de costo.
- Identifica productos nuevos.
- Identifica productos del proveedor que ya no aparecen en la lista.
- Prepara una hoja editable para generar ordenes de compra.

## 4. Como leer las pestanas principales

### Cambios de costo

Muestra productos donde el costo del proveedor es diferente al costo actual en TBC.

Sirve para revisar si hay que actualizar precios o condiciones en TBC.

Columnas importantes:

- `Costo proveedor`: costo nuevo enviado por el proveedor.
- `Costo TBC`: costo actual en TBC.
- `Diferencia costo`: costo proveedor menos costo TBC.
- `Diferencia porcentual`: cambio porcentual frente al costo TBC.

Si la diferencia es positiva, el proveedor esta mas caro que TBC.

### Compra sugerida resumida

Esta es la hoja mas gerencial para decidir compra.

Muestra una fila por producto y, para cada punto:

- Stock actual.
- Venta historica.
- Compra sugerida.

La compra sugerida ya considera inventario actual, ventas historicas, dias objetivo, minimos de quiebre y redistribucion.

### Ordenes de Compra

Esta hoja sirve para preparar las cantidades finales que se quieren comprar por punto.

Tiene:

- `SKU`
- `EAN`
- `Producto`
- Una columna por punto: `Av. 19`, `Bulevar`, `Oviedo`, `Bvista`, `Calle 74`, `CEDI`

Las cantidades de esta hoja estan conectadas con **Compra sugerida resumida**. Por ejemplo, si cambias la compra sugerida de Av. 19 en **Compra sugerida resumida**, ese cambio se refleja en la columna de Av. 19 de **Ordenes de Compra**.

Para productos nuevos, la app muestra `NUEVO`. La persona de compras debe reemplazar `NUEVO` por la cantidad que quiera comprar.

### Redistribucion sugerida

Muestra movimientos recomendados entre ubicaciones antes de comprar.

Ejemplo:

- Origen: `CEDI`
- Destino: `Av. 19`
- Cantidad: `2`
- Regla aplicada: `CEDI como fuente prioritaria`

Esto significa que la app recomienda mover 2 unidades desde CEDI hacia Av. 19.

### Inventario objetivo

Muestra el objetivo de inventario por producto y punto.

Sirve para entender a que nivel de unidades quiere llegar la app segun ventas historicas, dias objetivo y reglas de quiebre.

### Revision manual

Muestra casos que necesitan criterio humano.

Normalmente son productos sin venta y sin inventario en algun punto, donde la app aplica un minimo de quiebre configurable.

### Productos nuevos

Son productos que aparecen en la lista del proveedor, pero no existen en el inventario de TBC.

Estos productos no tienen SKU en TBC todavia.

### Descontinuados / no encontrados

Son productos que existen en TBC para el comodin analizado, pero no aparecen en la lista del proveedor.

La app no sugiere compra para estos productos, pero si puede sugerir redistribucion si hay inventario disponible.

### Sin costo TBC

Son productos que estan en TBC y en la lista del proveedor, pero no aparecen en el archivo de ventas historicas con costo TBC.

### Problemas de datos

Muestra errores o inconsistencias detectadas, por ejemplo:

- EAN invalido.
- EAN duplicado.
- Costo proveedor invalido.

## 5. Como descargar y usar el Excel

Despues de ejecutar el analisis, haz clic en:

**Descargar Excel del analisis**

Ese Excel es el archivo principal de trabajo.

Se recomienda revisar en este orden:

1. **Cambios de costo**
2. **Compra sugerida resumida**
3. **Ordenes de Compra**
4. **Redistribucion sugerida**
5. **Revision manual**
6. **Productos nuevos**
7. **Problemas de datos**

## 6. Como preparar las ordenes de compra

1. Descarga el Excel del analisis.
2. Abre el Excel.
3. Ve a la hoja **Compra sugerida resumida**.
4. Revisa y ajusta las cantidades de compra sugerida si lo necesitas.
5. Ve a la hoja **Ordenes de Compra**.
6. Revisa que las cantidades esten correctas por punto.
7. Para productos nuevos, reemplaza `NUEVO` por la cantidad que se quiera comprar.
8. Si no quieres comprar un producto en un punto, deja la cantidad en `0` o vacia.
9. Guarda el archivo Excel.

## 7. Como generar los PDFs de ordenes de compra

Despues de guardar el Excel con las cantidades finales:

1. Vuelve a la app.
2. En la barra lateral, busca la seccion **Ordenes de compra**.
3. Carga el archivo en **Excel con Ordenes de Compra**.
4. Escribe el **Numero base OC**.
   - Ejemplo: `OC-001`
5. Selecciona la **Fecha de emision**.
6. La app mostrara un resumen por punto:
   - Numero de lineas.
   - Total de unidades.
   - Valor total.
7. Haz clic en **Descargar ordenes de compra (PDF)**.

La app descarga un archivo `.zip` con un PDF por punto.

Ejemplo:

- `OC-001-AV19.pdf`
- `OC-001-BUL.pdf`
- `OC-001-OVI.pdf`
- `OC-001-BVI.pdf`
- `OC-001-C74.pdf`
- `OC-001-CEDI.pdf`

Solo se generan PDFs para puntos que tengan cantidades mayores a 0.

## 8. Reglas importantes de inventario y redistribucion

La app primero intenta cubrir necesidades con redistribucion antes de comprar.

Reglas principales:

- CEDI puede enviar a cualquier ciudad.
- Bodega Bqlla puede enviar a Bvista y Calle 74.
- Para Barranquilla, si Bodega Bqlla tiene inventario, se usa primero antes que CEDI.
- Full MercadoLibre se muestra como referencia, pero no se toca su inventario.
- Feria se muestra como referencia cuando esta activa, pero no envia inventario.
- Los productos descontinuados no se compran, pero si pueden redistribuirse.

## 9. Que revisar antes de tomar decisiones

Antes de enviar una orden de compra al proveedor, se recomienda revisar:

- Que el comodin del proveedor sea correcto.
- Que el modo Feria este bien configurado.
- Que el rango de fechas de `INVEPTOS.XLS` sea el periodo deseado.
- Que la plantilla proveedor tenga costos actualizados.
- Que no haya problemas criticos en **Problemas de datos**.
- Que los productos nuevos tengan cantidades definidas en **Ordenes de Compra**.
- Que las cantidades finales tengan sentido para cada punto.

## 10. Errores comunes

### La app dice que faltan columnas

Revisa que el archivo cargado sea el correcto y que no se haya modificado su estructura.

### La plantilla proveedor no carga

Verifica que tenga las columnas:

- `EAN-13`
- `Nombre`
- `Costo proveedor`

### No se generan PDFs

Esto pasa si la hoja **Ordenes de Compra** no tiene cantidades mayores a 0.

### Un producto nuevo no aparece con SKU

Es normal. Si es nuevo, todavia no existe en TBC y por eso no tiene SKU.

### Un producto descontinuado no aparece para compra

Es correcto. Los productos que no aparecen en la lista del proveedor no se compran, pero si pueden aparecer en redistribucion.

## 11. Glosario rapido

- **SKU**: codigo interno del producto en TBC.
- **EAN**: codigo de barras del producto.
- **PVP**: precio de venta al publico.
- **CEDI**: centro de distribucion.
- **Comodin**: codigo interno que identifica el proveedor.
- **Stock actual**: inventario disponible actualmente.
- **Venta**: unidades vendidas en el periodo del archivo `INVEPTOS.XLS`.
- **Compra sugerida**: unidades que la app recomienda comprar despues de considerar inventario, ventas y redistribucion.
- **Redistribucion**: movimiento sugerido de inventario entre ubicaciones.
- **Producto nuevo**: producto que esta en la lista del proveedor, pero no existe en TBC.
- **Descontinuado / no encontrado**: producto que existe en TBC, pero no aparece en la lista del proveedor.

## 12. Recomendacion de uso

Para una compra normal, el flujo recomendado es:

1. Descargar archivos de TBC.
2. Preparar plantilla proveedor.
3. Cargar archivos en la app.
4. Ejecutar analisis.
5. Revisar cambios de costo.
6. Revisar compra sugerida resumida.
7. Ajustar cantidades finales.
8. Revisar redistribuciones sugeridas.
9. Guardar el Excel.
10. Subir el Excel final a la app.
11. Descargar PDFs de ordenes de compra.
12. Enviar las ordenes al proveedor.

