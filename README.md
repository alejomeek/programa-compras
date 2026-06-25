# Programa de Compras

App Streamlit para analizar compras de Jugando y Educando a partir de:

- `SDOSXSUC.CSV`
- `INVEPTOS.XLS`
- plantilla proveedor con `EAN-13` y `Costo proveedor`

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
