# Programa de Compras

App Streamlit para analizar compras de Jugando y Educando a partir de:

- `SDOSXSUC.CSV`
- `INVEPTOS.XLS`
- plantilla proveedor con `EAN-13`, `Nombre` y `Costo proveedor`

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Desplegar en Streamlit Cloud

1. Subir este repo a GitHub.
2. Entrar a Streamlit Cloud.
3. Crear una app nueva apuntando a:
   - Repository: este repo
   - Branch: `main`
   - Main file path: `app.py`

La app no requiere secrets ni base de datos.

## Instructivo para usuarios

Ver [INSTRUCTIVO_USO_APP_COMPRAS.md](INSTRUCTIVO_USO_APP_COMPRAS.md) para una guia amigable de uso, explicacion de archivos, lectura de resultados y generacion de ordenes de compra.
