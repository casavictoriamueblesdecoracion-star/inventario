import streamlit as st
import pandas as pd
import altair as alt
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import hmac
import uuid

# =============================================================================
# CONFIGURACIÓN DE TU NEGOCIO  ←  MODIFICA ESTOS VALORES
# =============================================================================
# Estos son los únicos valores que debes cambiar para personalizar la app
# para tu empresa. Léelos con cuidado.

# Nombre que aparecerá en la pestaña del navegador y como título principal.
NOMBRE_APP = "Inventario casa victoria" 

# Emoji que aparecerá como icono en la pestaña del navegador.
ICONO_APP = "🌟"

# Nombre EXACTO de la hoja de cálculo en Google Sheets que vas a usar como
# base de datos. Debe coincidir letra por letra con el archivo en tu Drive.
NOMBRE_HOJA_CALCULO = "BaseDeDatos_Negocio"

# URL pública del logo de tu empresa. Si no quieres logo, deja la cadena vacía: "".
# Para obtener una URL: sube el logo a la carpeta "assets/" del repositorio,
# haz commit y push, y luego usa la URL "raw" de GitHub. Por ejemplo:
#   https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/assets/logo.jpeg
LOGO_URL = ""

# Zona horaria de tu negocio. Se usa para la fecha y hora de cada registro
# (el servidor de Streamlit Cloud trabaja en hora UTC).
ZONA_HORARIA = "America/Bogota"

# Unidades de medida en las que vendes. Cada producto lleva la suya en la columna
# "Unidad" de la pestaña Productos; si esa celda está vacía se asume la primera.
UNIDADES = ["Unidad", "Metro", "Lámina"]

# Unidades que admiten cantidades con decimales (por ejemplo 2,5 metros).
# Las demás solo aceptan cantidades enteras.
UNIDADES_CON_DECIMALES = ["Metro"]

# Un producto se marca con "stock bajo" cuando le queda esta cantidad o menos.
# Para un mínimo distinto por producto, agrega la columna "StockMinimo" en Productos.
STOCK_BAJO = 3

# Clave que se pide al abrir la app, guardada como huella SHA-256 (no en texto)
# porque este archivo vive en GitHub. Para cambiarla sin tocar el código, agrega
# en los Secrets de Streamlit Cloud una línea:  clave_acceso = "tu_nueva_clave"
CLAVE_HASH ="b9af0038d4b32a24482078819f5f9ba74533d9a4e1416655ed17cc52f2a1d268"

# =============================================================================
# A PARTIR DE AQUÍ NO NECESITAS MODIFICAR NADA (a menos que quieras adaptar
# la lógica del negocio, agregar campos, etc.)
# =============================================================================

# Si no hay LOGO_URL, se usa el archivo logo.png que está junto a app.py.
LOGO_LOCAL = Path(__file__).parent / "logo.png"
LOGO = LOGO_URL or (str(LOGO_LOCAL) if LOGO_LOCAL.exists() else "")

# Colores de las gráficas (ventas / gastos).
COLOR_VENTAS = "#C2692B"
COLOR_GASTOS = "#2A78B5"

st.set_page_config(
    page_title=NOMBRE_APP,
    page_icon=LOGO or ICONO_APP,
    layout="wide"
)

# Recorta el logo en círculo para que no se vea su fondo cuadrado.
st.markdown('<style>[data-testid="stImage"] img {border-radius: 50%;}</style>', unsafe_allow_html=True)

# --- ACCESO CON CLAVE ---
# Nada de la app (ni los datos de Google Sheets) se carga hasta ingresar la clave.
def clave_correcta(clave):
    """Valida la clave contra Secrets o, si no hay, contra CLAVE_HASH."""
    try:
        clave_secreta = st.secrets.get("clave_acceso")
    except Exception:
        clave_secreta = None
    if clave_secreta:
        return hmac.compare_digest(clave.encode(), str(clave_secreta).encode())
    return hmac.compare_digest(hashlib.sha256(clave.encode()).hexdigest(), CLAVE_HASH)

if not st.session_state.get('autenticado', False):
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        if LOGO:
            _, col_logo, _ = st.columns([1, 2, 1])
            col_logo.image(LOGO, width="stretch")
        st.title(NOMBRE_APP)
        with st.form("acceso_form"):
            clave_ingresada = st.text_input("Clave de acceso", type="password")
            if st.form_submit_button("Entrar", type="primary", width="stretch"):
                if clave_correcta(clave_ingresada):
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Clave incorrecta.")
    st.stop()

# --- LOGO EN LA BARRA LATERAL ---
if LOGO:
    _, col_logo, _ = st.sidebar.columns([1, 4, 1])
    col_logo.image(LOGO, width="stretch")
st.sidebar.subheader("Menú")


# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def connect_to_gsheets():
    """Conecta a Google Sheets y devuelve los objetos de las hojas."""
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    try:
        # Modo local: usa el archivo credentials.json en la raíz del proyecto.
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    except FileNotFoundError:
        # Modo desplegado en Streamlit Cloud: lee desde st.secrets.
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)

    client = gspread.authorize(creds)

    try:
        spreadsheet = client.open(NOMBRE_HOJA_CALCULO)
        return {
            "ventas": spreadsheet.worksheet("Ventas"),
            "compras": spreadsheet.worksheet("Compras"),
            "inventario": spreadsheet.worksheet("Inventario"),
            "productos": spreadsheet.worksheet("Productos"),
            "clientes": spreadsheet.worksheet("Clientes"),
            "proveedores": spreadsheet.worksheet("Proveedores"),
            "pagos": spreadsheet.worksheet("Pagos"),
            "obsequios": spreadsheet.worksheet("Obsequios")
        }
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"🚨 No se encontró la hoja de cálculo '{NOMBRE_HOJA_CALCULO}'. Asegúrate de que exista y esté compartida con la cuenta de servicio.")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error("🚨 Falta una o más hojas requeridas (Ventas, Compras, Inventario, Productos, Clientes, Proveedores, Pagos, Obsequios). Por favor, créalas.")
        st.stop()

sheets = connect_to_gsheets()

def leer_registros(sheet_name):
    """Lee una hoja con los valores sin formato, para que los números (incluidos
    los decimales) lleguen como número sin importar la configuración regional."""
    return sheets[sheet_name].get_all_records(value_render_option="UNFORMATTED_VALUE")

# --- CARGA DE DATOS MAESTROS ---
@st.cache_data(ttl=300)
def load_master_data():
    """Carga los datos de las hojas de gestión y los procesa."""
    productos_df = pd.DataFrame(leer_registros("productos"))
    clientes_df = pd.DataFrame(leer_registros("clientes"))
    proveedores_df = pd.DataFrame(leer_registros("proveedores"))

    # Si una hoja solo tiene el encabezado, se garantiza que la columna exista.
    if 'NombreCliente' not in clientes_df.columns:
        clientes_df = pd.DataFrame(columns=['NombreCliente'])
    if 'NombreProveedor' not in proveedores_df.columns:
        proveedores_df = pd.DataFrame(columns=['NombreProveedor'])

    productos_dict, unidades_dict, minimos_dict = {}, {}, {}
    if not productos_df.empty:
        productos_df['NombreProducto'] = productos_df['NombreProducto'].astype(str).str.strip()
        if 'StockMinimo' in productos_df.columns:
            productos_df['StockMinimo'] = pd.to_numeric(productos_df['StockMinimo'], errors='coerce')
        for _, row in productos_df.iterrows():
            tallas = [t.strip() for t in str(row['TallasDisponibles']).split(',')]
            productos_dict[row['NombreProducto']] = tallas
            # Columnas opcionales: Unidad y StockMinimo.
            unidad = str(row.get('Unidad', '')).strip()
            if unidad:
                unidades_dict[row['NombreProducto']] = unidad
            minimo = pd.to_numeric(row.get('StockMinimo', ''), errors='coerce')
            if pd.notna(minimo):
                minimos_dict[row['NombreProducto']] = float(minimo)

    return productos_df, productos_dict, clientes_df, proveedores_df, unidades_dict, minimos_dict

productos_df, PRODUCTOS, clientes_df, proveedores_df, UNIDAD_PRODUCTO, MINIMO_PRODUCTO = load_master_data()

# --- FUNCIONES AUXILIARES ---
def ahora():
    """Fecha y hora actual en la zona horaria del negocio."""
    return datetime.now(ZoneInfo(ZONA_HORARIA)).strftime("%Y-%m-%d %H:%M:%S")

def avisar(mensaje):
    """Guarda un mensaje de éxito para mostrarlo después de recargar la página."""
    st.session_state.aviso = mensaje

def fmt_dinero(valor):
    """Formatea un valor como pesos: $ 64.000"""
    try:
        return f"$ {float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return valor

def tabla(df, dinero=(), cantidad=('Cantidad',), contenedor=st):
    """Muestra una tabla sin índice, con dinero y cantidades formateados.
    La columna interna 'Talla' se muestra como 'Categoría'."""
    df = df.rename(columns={'Talla': 'Categoría', 'TallasDisponibles': 'Categoría'})
    formatos = {c: fmt_dinero for c in dinero if c in df.columns}
    formatos.update({c: fmt_cantidad for c in cantidad if c in df.columns})
    datos = df.style.format(formatos) if formatos and not df.empty else df
    contenedor.dataframe(datos, width="stretch", hide_index=True)

def unidad_de(producto):
    """Unidad de medida del producto (Metro, Lámina, Unidad...)."""
    return UNIDAD_PRODUCTO.get(producto, UNIDADES[0])

def plural(unidad):
    """metro -> metros, lámina -> láminas, unidad -> unidades."""
    unidad = unidad.lower()
    return unidad + ("s" if unidad[-1:] in "aeiouáéíóú" else "es")

def fmt_cantidad(valor):
    """Muestra una cantidad sin ceros de más: 4 -> 4, 2.5 -> 2,5"""
    try:
        return f"{float(valor):.2f}".rstrip("0").rstrip(".").replace(".", ",")
    except (TypeError, ValueError):
        return valor

def campo_cantidad(contenedor, producto):
    """Campo de cantidad según la unidad del producto: con decimales o entero."""
    unidad = unidad_de(producto)
    etiqueta = f"Cantidad ({plural(unidad)})"
    if unidad in UNIDADES_CON_DECIMALES:
        return contenedor.number_input(etiqueta, min_value=0.01, value=1.0, step=0.5, format="%.2f")
    return contenedor.number_input(etiqueta, min_value=1, step=1)

def estado_stock(cantidad, minimo=None):
    """Etiqueta visual del nivel de existencias."""
    if cantidad <= 0:
        return "🔴 Agotado"
    if cantidad <= (STOCK_BAJO if minimo is None else minimo):
        return "🟡 Bajo"
    return "🟢 Disponible"

def suma(df, columna):
    """Suma una columna numérica; devuelve 0 si la columna no existe."""
    if columna not in df.columns:
        return 0
    return pd.to_numeric(df[columna], errors='coerce').fillna(0).sum()

def get_data(sheet_name):
    """Obtiene datos de una hoja y los devuelve como DataFrame."""
    records = leer_registros(sheet_name)
    if not records:
        try:
            headers = sheets[sheet_name].row_values(1)
            return pd.DataFrame(columns=headers)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame(records)

def actualizar_inventario():
    """Recalcula y actualiza el inventario considerando ventas y obsequios."""
    compras_df = get_data("compras")
    ventas_df = get_data("ventas")
    obsequios_df = get_data("obsequios")

    if not compras_df.empty:
        compras_df['Cantidad'] = pd.to_numeric(compras_df['Cantidad'], errors='coerce').fillna(0)
        compras_df['SKU'] = compras_df['Producto'].astype(str) + " - " + compras_df['Talla'].astype(str)
        stock_comprado = compras_df.groupby('SKU')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Unidades Compradas'})
    else:
        stock_comprado = pd.DataFrame(columns=['SKU', 'Unidades Compradas'])

    salidas_list = []
    if not ventas_df.empty:
        ventas_df['Cantidad'] = pd.to_numeric(ventas_df['Cantidad'], errors='coerce').fillna(0)
        ventas_df['SKU'] = ventas_df['Producto'].astype(str) + " - " + ventas_df['Talla'].astype(str)
        salidas_list.append(ventas_df[['SKU', 'Cantidad']])

    if not obsequios_df.empty:
        obsequios_df['Cantidad'] = pd.to_numeric(obsequios_df['Cantidad'], errors='coerce').fillna(0)
        obsequios_df['SKU'] = obsequios_df['Producto'].astype(str) + " - " + obsequios_df['Talla'].astype(str)
        salidas_list.append(obsequios_df[['SKU', 'Cantidad']])

    if salidas_list:
        df_salidas = pd.concat(salidas_list)
        stock_saliente = df_salidas.groupby('SKU')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Unidades Salientes'})
    else:
        stock_saliente = pd.DataFrame(columns=['SKU', 'Unidades Salientes'])

    inventario_df = pd.merge(stock_comprado, stock_saliente, on='SKU', how='outer').fillna(0)

    inventario_df['Unidades Compradas'] = pd.to_numeric(inventario_df['Unidades Compradas'], errors='coerce').fillna(0)
    inventario_df['Unidades Salientes'] = pd.to_numeric(inventario_df['Unidades Salientes'], errors='coerce').fillna(0)

    # Se separa por el último " - " para tolerar nombres de producto que lo contengan.
    partes_sku = inventario_df['SKU'].astype(str).str.rsplit(' - ', n=1)
    inventario_df['Producto'] = partes_sku.str[0]
    inventario_df['Talla'] = partes_sku.str[1]
    inventario_df['Stock Actual'] = inventario_df['Unidades Compradas'] - inventario_df['Unidades Salientes']
    # Evita restos de coma flotante (0.30000000004) al trabajar con metros.
    for col in ['Unidades Compradas', 'Unidades Salientes', 'Stock Actual']:
        inventario_df[col] = inventario_df[col].round(2)
    inventario_df['Fecha Actualizacion'] = ahora()

    column_order = ["SKU", "Producto", "Talla", "Unidades Compradas", "Unidades Salientes", "Stock Actual", "Fecha Actualizacion"]
    inventario_df = inventario_df.rename(columns={'Unidades Salientes': 'Unidades Vendidas'})

    sheets["inventario"].clear()
    sheets["inventario"].update([inventario_df.columns.values.tolist()] + inventario_df.values.tolist())
    return inventario_df

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if 'compra_actual' not in st.session_state:
    st.session_state.compra_actual = []
if 'venta_actual' not in st.session_state:
    st.session_state.venta_actual = []

# --- INTERFAZ DE LA APLICACIÓN ---
st.title(NOMBRE_APP)

if 'aviso' in st.session_state:
    st.success(st.session_state.pop('aviso'))
    st.balloons()

opcion = st.sidebar.radio(
    "Selecciona una opción:",
    ["📈 Ver Inventario", "💰 Registrar Venta", "🛒 Registrar Compra", "🎁 Registrar Obsequio", "📊 Finanzas", "🧾 Cuentas por Cobrar", "⚙️ Gestión"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🔒 Cerrar sesión"):
    st.session_state.autenticado = False
    st.rerun()

# --- PESTAÑA DE GESTIÓN ---
if opcion == "⚙️ Gestión":
    st.header("Gestión de Datos Maestros")
    st.info("Aquí puedes añadir nuevos productos, clientes y proveedores a tus listas.")
    tab1, tab2, tab3 = st.tabs(["🛍️ Productos", "👥 Clientes", "🚚 Proveedores"])

    with tab1:
        st.subheader("Añadir Nuevo Producto")
        with st.form("nuevo_producto_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del Nuevo Producto")
            tallas = st.text_input("Categoría (ej: TELA, ESPUMA, MADERA)", help="Si el producto tiene varias presentaciones, sepáralas con coma.")
            unidad = st.selectbox("Unidad de medida", options=UNIDADES)
            precio = st.number_input("Precio de Venta por unidad de medida", min_value=0.0, format="%.2f")
            costo = st.number_input("Costo de Compra por unidad de medida", min_value=0.0, format="%.2f")
            if st.form_submit_button("Añadir Producto", type="primary"):
                nombre, tallas = nombre.strip(), tallas.strip()
                if nombre and tallas:
                    # La fila se arma según los encabezados reales de la hoja.
                    valores = {'NombreProducto': nombre, 'TallasDisponibles': tallas, 'PrecioVentaDefecto': precio, 'CostoCompraDefecto': costo, 'Unidad': unidad}
                    encabezados = sheets["productos"].row_values(1)
                    sheets["productos"].append_row([valores.get(h, "") for h in encabezados])
                    if 'Unidad' in encabezados:
                        avisar(f"¡Producto '{nombre}' añadido!")
                    else:
                        avisar(f"Producto '{nombre}' añadido, pero sin unidad: falta la columna 'Unidad' en la pestaña Productos.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("Nombre y Categoría son campos obligatorios.")
        if 'Unidad' not in productos_df.columns:
            st.warning("La pestaña Productos no tiene la columna 'Unidad'. Agrégala en Google Sheets para manejar metros y láminas; mientras tanto todo se cuenta en unidades enteras.")
        st.subheader("Lista de Productos Actual")
        tabla(productos_df, dinero=['PrecioVentaDefecto', 'CostoCompraDefecto'], cantidad=['StockMinimo'])

    with tab2:
        st.subheader("Añadir Nuevo Cliente")
        with st.form("nuevo_cliente_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del Nuevo Cliente")
            if st.form_submit_button("Añadir Cliente", type="primary"):
                nombre = nombre.strip()
                if nombre:
                    sheets["clientes"].append_row([nombre])
                    avisar(f"¡Cliente '{nombre}' añadido!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("El nombre del cliente no puede estar vacío.")
        st.subheader("Lista de Clientes Actual")
        tabla(clientes_df)

    with tab3:
        st.subheader("Añadir Nuevo Proveedor")
        with st.form("nuevo_proveedor_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del Nuevo Proveedor")
            if st.form_submit_button("Añadir Proveedor", type="primary"):
                nombre = nombre.strip()
                if nombre:
                    sheets["proveedores"].append_row([nombre])
                    avisar(f"¡Proveedor '{nombre}' añadido!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("El nombre del proveedor no puede estar vacío.")
        st.subheader("Lista de Proveedores Actual")
        tabla(proveedores_df)

# --- PESTAÑA DE VENTAS ---
elif opcion == "💰 Registrar Venta":
    st.header("Registrar Venta")

    with st.container(border=True):
        st.subheader("Paso 1: Elige el Cliente")
        col1, col2 = st.columns([2, 2])
        with col1:
            lista_clientes = [""] + clientes_df['NombreCliente'].tolist()
            cliente_existente = st.selectbox("Selecciona un Cliente Existente", options=lista_clientes, help="Elige un cliente de tu lista.")
        with col2:
            cliente_nuevo = st.text_input("O añade un Cliente Nuevo aquí", help="Si el cliente no existe, escríbelo aquí.").strip()

    cliente_final = cliente_nuevo if cliente_nuevo else cliente_existente

    if cliente_final:
        st.success(f"Cliente seleccionado: **{cliente_final}**")
        st.markdown("---")
        st.subheader("Paso 2: Añade Productos a la Venta")

        producto_vendido = st.selectbox("Selecciona un producto", options=[""] + list(PRODUCTOS.keys()), key="venta_prod_selector", label_visibility="collapsed")

        if producto_vendido:
            with st.form("item_venta_form", clear_on_submit=True):
                st.write(f"**Añadiendo:** {producto_vendido}")
                precio_defecto = float(productos_df[productos_df['NombreProducto'] == producto_vendido]['PrecioVentaDefecto'].iloc[0])

                c1, c2, c3 = st.columns(3)
                talla_vendida = c1.selectbox("Categoría", options=PRODUCTOS.get(producto_vendido, []))
                cantidad_vendida = campo_cantidad(c2, producto_vendido)
                precio_unitario = c3.number_input(f"Precio por {unidad_de(producto_vendido).lower()} ($)", min_value=0.0, value=precio_defecto, format="%.2f", key=f"precio_venta_{producto_vendido}")

                if st.form_submit_button("➕ Añadir Producto"):
                    item = {"Producto": producto_vendido, "Talla": talla_vendida, "Cantidad": cantidad_vendida, "Unidad": unidad_de(producto_vendido), "Precio Unitario": precio_unitario, "Total Venta": round(cantidad_vendida * precio_unitario, 2)}
                    st.session_state.venta_actual.append(item)
                    st.rerun()

        if st.session_state.venta_actual:
            st.markdown("---")
            st.subheader("Venta Actual")
            tabla(pd.DataFrame(st.session_state.venta_actual), dinero=['Precio Unitario', 'Total Venta'])

            with st.form("eliminar_item_venta_form"):
                indices_a_eliminar = st.multiselect("Selecciona productos para eliminar", options=range(len(st.session_state.venta_actual)), format_func=lambda i: f"{st.session_state.venta_actual[i]['Producto']} ({fmt_cantidad(st.session_state.venta_actual[i]['Cantidad'])} {st.session_state.venta_actual[i]['Unidad'].lower()})")
                if st.form_submit_button("🗑️ Eliminar Seleccionados"):
                    st.session_state.venta_actual = [item for i, item in enumerate(st.session_state.venta_actual) if i not in indices_a_eliminar]
                    st.rerun()

            if st.session_state.venta_actual:
                st.markdown("---")
                st.subheader(f"Paso 3: Finalizar Venta para {cliente_final}")
                total_venta_actual = pd.DataFrame(st.session_state.venta_actual)["Total Venta"].sum()
                st.metric("Total de la venta", fmt_dinero(total_venta_actual), border=True)

                estado_pago = st.selectbox("Estado del Pago", ["Pagado", "Abono", "Debe"], key="estado_pago_selector")

                with st.form("finalizar_venta_form"):
                    monto_abono_inicial = 0
                    if estado_pago == "Abono":
                        monto_abono_inicial = st.number_input("Monto del Abono Inicial ($)", min_value=0.01, max_value=max(float(total_venta_actual), 0.01), format="%.2f")

                    if st.form_submit_button("✅ Registrar Venta Completa", type="primary"):
                        if estado_pago == "Abono" and monto_abono_inicial <= 0:
                            st.error("Para un 'Abono', el monto debe ser mayor a cero.")
                        else:
                            if cliente_nuevo and cliente_nuevo not in clientes_df['NombreCliente'].tolist():
                                sheets["clientes"].append_row([cliente_nuevo])
                                st.success(f"¡Nuevo cliente '{cliente_nuevo}' añadido a la base de datos!")
                                st.cache_data.clear()

                            with st.spinner("Registrando venta y pago inicial..."):
                                id_venta = f"VENTA-{uuid.uuid4().hex[:8].upper()}"
                                fecha_venta = ahora()

                                if estado_pago == "Pagado":
                                    id_pago = f"PAGO-{uuid.uuid4().hex[:8].upper()}"
                                    sheets["pagos"].append_row([id_pago, id_venta, fecha_venta, total_venta_actual])
                                elif estado_pago == "Abono":
                                    id_pago = f"PAGO-{uuid.uuid4().hex[:8].upper()}"
                                    sheets["pagos"].append_row([id_pago, id_venta, fecha_venta, monto_abono_inicial])

                                filas_venta = [[id_venta, fecha_venta, item["Producto"], item["Talla"], cliente_final, item["Cantidad"], item["Precio Unitario"], item["Total Venta"], estado_pago] for item in st.session_state.venta_actual]
                                sheets["ventas"].append_rows(filas_venta)

                                avisar(f"¡Venta {id_venta} registrada!")
                                st.session_state.venta_actual = []
                                actualizar_inventario()
                                st.rerun()
    else:
        st.warning("Por favor, selecciona o añade un cliente para continuar.")

# --- PESTAÑA DE COMPRAS ---
elif opcion == "🛒 Registrar Compra":
    st.header("Registrar Compra")

    with st.container(border=True):
        st.subheader("Paso 1: Elige el Proveedor")
        col1, col2 = st.columns([2, 2])
        with col1:
            lista_proveedores = [""] + proveedores_df['NombreProveedor'].tolist()
            proveedor_existente = st.selectbox("Selecciona un Proveedor Existente", options=lista_proveedores)
        with col2:
            proveedor_nuevo = st.text_input("O añade un Proveedor Nuevo aquí").strip()

    proveedor_final = proveedor_nuevo if proveedor_nuevo else proveedor_existente

    if proveedor_final:
        st.success(f"Proveedor seleccionado: **{proveedor_final}**")
        st.markdown("---")
        st.subheader("Paso 2: Añade Productos a la Orden")

        producto_comprado = st.selectbox("Selecciona un producto", options=[""] + list(PRODUCTOS.keys()), key="compra_prod_selector", label_visibility="collapsed")

        if producto_comprado:
            with st.form("item_compra_form", clear_on_submit=True):
                st.write(f"**Añadiendo:** {producto_comprado}")
                costo_defecto = float(productos_df[productos_df['NombreProducto'] == producto_comprado]['CostoCompraDefecto'].iloc[0])

                c1, c2, c3 = st.columns(3)
                talla_comprada = c1.selectbox("Categoría", options=PRODUCTOS.get(producto_comprado, []))
                cantidad_comprada = campo_cantidad(c2, producto_comprado)
                costo_unitario = c3.number_input(f"Costo por {unidad_de(producto_comprado).lower()} ($)", min_value=0.0, value=costo_defecto, format="%.2f", key=f"costo_compra_{producto_comprado}")

                if st.form_submit_button("➕ Añadir Producto"):
                    item = {"Producto": producto_comprado, "Talla": talla_comprada, "Cantidad": cantidad_comprada, "Unidad": unidad_de(producto_comprado), "Costo Total": round(cantidad_comprada * costo_unitario, 2)}
                    st.session_state.compra_actual.append(item)
                    st.rerun()

        if st.session_state.compra_actual:
            st.markdown("---")
            st.subheader("Orden de Compra Actual")
            tabla(pd.DataFrame(st.session_state.compra_actual), dinero=['Costo Total'])
            st.metric("Total de la compra", fmt_dinero(sum(item["Costo Total"] for item in st.session_state.compra_actual)), border=True)

            with st.form("eliminar_item_compra_form"):
                indices_a_eliminar = st.multiselect("Selecciona productos para eliminar", options=range(len(st.session_state.compra_actual)), format_func=lambda i: f"{st.session_state.compra_actual[i]['Producto']} ({fmt_cantidad(st.session_state.compra_actual[i]['Cantidad'])} {st.session_state.compra_actual[i]['Unidad'].lower()})")
                if st.form_submit_button("🗑️ Eliminar Seleccionados"):
                    st.session_state.compra_actual = [item for i, item in enumerate(st.session_state.compra_actual) if i not in indices_a_eliminar]
                    st.rerun()

            if st.session_state.compra_actual:
                st.markdown("---")
                st.subheader(f"Paso 3: Finalizar Compra de {proveedor_final}")
                with st.form("finalizar_compra_form"):
                    costo_envio = st.number_input("Costo Total del Envío ($)", min_value=0.0, format="%.2f")
                    if st.form_submit_button("✅ Registrar Compra Completa", type="primary"):
                        if proveedor_nuevo and proveedor_nuevo not in proveedores_df['NombreProveedor'].tolist():
                            sheets["proveedores"].append_row([proveedor_nuevo])
                            st.success(f"¡Nuevo proveedor '{proveedor_nuevo}' añadido a la base de datos!")
                            st.cache_data.clear()

                        with st.spinner("Registrando compra..."):
                            id_compra = f"COMPRA-{uuid.uuid4().hex[:8].upper()}"
                            fecha_compra = ahora()
                            filas_para_añadir = [[id_compra, fecha_compra, item["Producto"], item["Talla"], proveedor_final, item["Cantidad"], item["Costo Total"], costo_envio] for item in st.session_state.compra_actual]
                            sheets["compras"].append_rows(filas_para_añadir)
                            avisar(f"¡Compra {id_compra} registrada!")
                            st.session_state.compra_actual = []
                            actualizar_inventario()
                            st.rerun()
    else:
        st.warning("Por favor, selecciona o añade un proveedor para continuar.")

# --- PESTAÑA DE OBSEQUIOS ---
elif opcion == "🎁 Registrar Obsequio":
    st.header("Registrar Obsequio")
    st.warning("Esta acción disminuirá tu inventario y se registrará como un costo (no un ingreso).")

    producto_obsequiado = st.selectbox("Producto a Obsequiar", options=list(PRODUCTOS.keys()))

    with st.form("obsequio_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        talla_obsequiada = c1.selectbox("Categoría", options=PRODUCTOS.get(producto_obsequiado, []))
        cantidad_obsequiada = campo_cantidad(c2, producto_obsequiado)
        motivo = c3.text_input("Motivo / Cliente")

        if st.form_submit_button("🎁 Registrar Obsequio", type="primary"):
            if producto_obsequiado and motivo:
                with st.spinner("Registrando obsequio..."):
                    costo_unitario = float(productos_df[productos_df['NombreProducto'] == producto_obsequiado]['CostoCompraDefecto'].iloc[0])
                    costo_total_obsequio = round(costo_unitario * cantidad_obsequiada, 2)

                    id_obsequio = f"OBSEQUIO-{uuid.uuid4().hex[:8].upper()}"
                    fecha_obsequio = ahora()

                    fila = [id_obsequio, fecha_obsequio, producto_obsequiado, talla_obsequiada, cantidad_obsequiada, motivo, costo_total_obsequio]
                    sheets["obsequios"].append_row(fila)

                    st.success("¡Obsequio registrado correctamente!")
                    st.balloons()
                    actualizar_inventario()
                    st.cache_data.clear()
            else:
                st.error("Por favor, completa todos los campos.")

# --- PESTAÑA DE CUENTAS POR COBRAR ---
elif opcion == "🧾 Cuentas por Cobrar":
    st.header("Cuentas por Cobrar")

    ventas_df = get_data("ventas")
    pagos_df = get_data("pagos")

    if not ventas_df.empty:
        ventas_df['Total Venta'] = pd.to_numeric(ventas_df['Total Venta'], errors='coerce').fillna(0)
        ventas_pendientes = ventas_df[ventas_df['Estado Pago'].isin(['Debe', 'Abono'])]

        if not ventas_pendientes.empty:
            if not pagos_df.empty:
                pagos_df['Monto Pagado'] = pd.to_numeric(pagos_df['Monto Pagado'], errors='coerce').fillna(0)
                total_pagado_por_venta = pagos_df.groupby('ID Venta')['Monto Pagado'].sum().reset_index()
            else:
                total_pagado_por_venta = pd.DataFrame(columns=['ID Venta', 'Monto Pagado'])

            total_venta = ventas_pendientes.groupby('ID Venta').agg(
                Cliente=('Cliente', 'first'),
                Total_Venta=('Total Venta', 'sum')
            ).reset_index()

            resumen_deudas = pd.merge(total_venta, total_pagado_por_venta, on='ID Venta', how='left').fillna(0)
            resumen_deudas['Saldo Pendiente'] = resumen_deudas['Total_Venta'] - resumen_deudas['Monto Pagado']

            resumen_deudas = resumen_deudas[resumen_deudas['Saldo Pendiente'] > 0.01]
            if resumen_deudas.empty:
                st.success("🎉 ¡Felicidades! No tienes ninguna cuenta por cobrar pendiente.")
                st.stop()

            d1, d2 = st.columns(2)
            d1.metric("Total por cobrar", fmt_dinero(resumen_deudas['Saldo Pendiente'].sum()), border=True)
            d2.metric("Ventas con saldo pendiente", len(resumen_deudas), border=True)

            st.subheader("Resumen de Deudas")
            tabla(resumen_deudas.rename(columns={'Total_Venta': 'Total Venta'}), dinero=['Total Venta', 'Monto Pagado', 'Saldo Pendiente'])

            st.markdown("---")
            st.subheader("Registrar Abono o Pago Final")
            with st.form("registrar_abono_form"):
                id_venta_pago = st.selectbox("Selecciona el ID de la Venta", options=resumen_deudas['ID Venta'].unique())
                monto_pago = st.number_input("Monto del Pago ($)", min_value=0.01, format="%.2f")

                if st.form_submit_button("Registrar Pago", type="primary"):
                    saldo_actual = resumen_deudas[resumen_deudas['ID Venta'] == id_venta_pago]['Saldo Pendiente'].iloc[0]
                    if monto_pago > saldo_actual + 0.01:
                        st.error(f"El pago ({fmt_dinero(monto_pago)}) supera el saldo pendiente de la venta ({fmt_dinero(saldo_actual)}).")
                    elif id_venta_pago and monto_pago > 0:
                        with st.spinner("Registrando pago..."):
                            id_pago = f"PAGO-{uuid.uuid4().hex[:8].upper()}"
                            fecha_pago = ahora()
                            sheets["pagos"].append_row([id_pago, id_venta_pago, fecha_pago, monto_pago])

                            venta_info = resumen_deudas[resumen_deudas['ID Venta'] == id_venta_pago].iloc[0]
                            nuevo_saldo = venta_info['Saldo Pendiente'] - monto_pago

                            if nuevo_saldo <= 0.01:
                                cell_list = sheets["ventas"].findall(id_venta_pago)
                                estado_col_index = sheets["ventas"].row_values(1).index('Estado Pago') + 1
                                for cell in cell_list:
                                    sheets["ventas"].update_cell(cell.row, estado_col_index, "Pagado")
                                avisar(f"¡Pago registrado y Venta {id_venta_pago} marcada como 'Pagado'!")
                            else:
                                avisar(f"¡Abono de {fmt_dinero(monto_pago)} registrado para la venta {id_venta_pago}!")

                            st.cache_data.clear()
                            st.rerun()
        else:
            st.success("🎉 ¡Felicidades! No tienes ninguna cuenta por cobrar pendiente.")
    else:
        st.info("No hay datos de ventas para analizar.")

# --- PESTAÑA DE FINANZAS ---
elif opcion == "📊 Finanzas":
    st.header("Análisis Financiero")

    ventas_df_full = get_data("ventas")
    compras_df_full = get_data("compras")
    pagos_df_full = get_data("pagos")
    obsequios_df_full = get_data("obsequios")

    if ventas_df_full.empty and compras_df_full.empty:
        st.info("No hay datos de ventas o compras para analizar.")
    else:
        if not ventas_df_full.empty:
            ventas_df_full['Fecha'] = pd.to_datetime(ventas_df_full['Fecha'], errors='coerce')
            ventas_df_full['Mes'] = ventas_df_full['Fecha'].dt.to_period('M').astype(str)
            ventas_df_full['Total Venta'] = pd.to_numeric(ventas_df_full['Total Venta'], errors='coerce').fillna(0)
        if not compras_df_full.empty:
            compras_df_full['Fecha'] = pd.to_datetime(compras_df_full['Fecha'], errors='coerce')
            compras_df_full['Mes'] = compras_df_full['Fecha'].dt.to_period('M').astype(str)
            compras_df_full['Costo Total'] = pd.to_numeric(compras_df_full['Costo Total'], errors='coerce').fillna(0)
            compras_df_full['Costo Envio'] = pd.to_numeric(compras_df_full['Costo Envio'], errors='coerce').fillna(0)
        if not pagos_df_full.empty:
            pagos_df_full['Fecha Pago'] = pd.to_datetime(pagos_df_full['Fecha Pago'], errors='coerce')
            pagos_df_full['Mes'] = pagos_df_full['Fecha Pago'].dt.to_period('M').astype(str)
            pagos_df_full['Monto Pagado'] = pd.to_numeric(pagos_df_full['Monto Pagado'], errors='coerce').fillna(0)
        if not obsequios_df_full.empty:
            obsequios_df_full['Fecha'] = pd.to_datetime(obsequios_df_full['Fecha'], errors='coerce')
            obsequios_df_full['Mes'] = obsequios_df_full['Fecha'].dt.to_period('M').astype(str)
            obsequios_df_full['Costo Total'] = pd.to_numeric(obsequios_df_full['Costo Total'], errors='coerce').fillna(0)

        meses = pd.concat([df['Mes'] for df in (ventas_df_full, compras_df_full) if 'Mes' in df.columns])
        meses_disponibles = sorted((m for m in meses.dropna().unique() if m != 'NaT'), reverse=True)
        if not meses_disponibles:
             st.warning("No hay datos con fechas válidas para generar el reporte.")
             st.stop()

        mes_seleccionado = st.selectbox("Selecciona un Mes para Analizar", options=["Todos"] + meses_disponibles)

        def filtrar_mes(df):
            # Una hoja vacía no tiene columna 'Mes': se devuelve tal cual (conserva sus encabezados).
            if mes_seleccionado == "Todos" or 'Mes' not in df.columns:
                return df
            return df[df['Mes'] == mes_seleccionado]

        ventas_filtradas = filtrar_mes(ventas_df_full)
        compras_filtradas = filtrar_mes(compras_df_full)
        pagos_filtrados = filtrar_mes(pagos_df_full)
        obsequios_filtrados = filtrar_mes(obsequios_df_full)

        ingresos_de_pagos = suma(pagos_filtrados, 'Monto Pagado')
        ingresos_legacy = 0
        ventas_pagadas_periodo = ventas_filtradas[ventas_filtradas['Estado Pago'] == 'Pagado']
        if not ventas_pagadas_periodo.empty:
            id_ventas_con_pago = pagos_df_full['ID Venta'].unique()
            ventas_legacy_pagadas = ventas_pagadas_periodo[~ventas_pagadas_periodo['ID Venta'].isin(id_ventas_con_pago)]
            ingresos_legacy = ventas_legacy_pagadas.groupby('ID Venta')['Total Venta'].sum().sum()
        total_ingresos_reales = ingresos_de_pagos + ingresos_legacy

        total_costo_producto = suma(compras_filtradas, 'Costo Total')
        total_costo_envio = compras_filtradas.drop_duplicates(subset=['ID Compra'])['Costo Envio'].sum() if not compras_filtradas.empty else 0
        total_costo_obsequios = suma(obsequios_filtrados, 'Costo Total')
        total_gastos = total_costo_producto + total_costo_envio + total_costo_obsequios

        ganancia_real = total_ingresos_reales - total_gastos

        total_ventas_brutas = suma(ventas_df_full, 'Total Venta')
        total_pagado_historico = suma(pagos_df_full, 'Monto Pagado')
        total_por_cobrar = total_ventas_brutas - total_pagado_historico

        st.markdown("---")
        st.subheader(f"Resumen Financiero para: {mes_seleccionado}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Ingresos Reales (Recibido)", fmt_dinero(total_ingresos_reales), border=True)
        col2.metric("💸 Gastos Totales", fmt_dinero(total_gastos), border=True)
        col3.metric("📈 Ganancia Real", fmt_dinero(ganancia_real), border=True)
        col4.metric("🧾 Cuentas por Cobrar (Total)", fmt_dinero(total_por_cobrar), border=True)

        # --- Gráficas ---
        por_mes = {}
        def acumular(df, columna, concepto):
            if 'Mes' in df.columns and columna in df.columns:
                for mes, valor in df.groupby('Mes')[columna].sum().items():
                    if mes != 'NaT':
                        por_mes[(mes, concepto)] = por_mes.get((mes, concepto), 0) + valor
        acumular(ventas_df_full, 'Total Venta', 'Ventas')
        acumular(compras_df_full, 'Costo Total', 'Gastos')
        if not compras_df_full.empty:
            acumular(compras_df_full.drop_duplicates(subset=['ID Compra']), 'Costo Envio', 'Gastos')
        acumular(obsequios_df_full, 'Costo Total', 'Gastos')
        meses_df = pd.DataFrame([{'Mes': m, 'Concepto': c, 'Valor': v} for (m, c), v in sorted(por_mes.items())])

        top_df = pd.DataFrame()
        if not ventas_filtradas.empty:
            top_df = (ventas_filtradas.groupby('Producto')['Total Venta'].sum()
                      .sort_values(ascending=False).head(10).reset_index())

        g1, g2 = st.columns(2)
        with g1.container(border=True):
            st.markdown("**Ventas y gastos por mes**")
            if meses_df.empty:
                st.caption("Aún no hay movimientos para graficar.")
            else:
                st.altair_chart(
                    alt.Chart(meses_df).mark_bar(cornerRadiusEnd=4).encode(
                        x=alt.X('Mes:N', title=None, axis=alt.Axis(labelAngle=0)),
                        xOffset=alt.XOffset('Concepto:N', sort=['Ventas', 'Gastos']),
                        y=alt.Y('Valor:Q', title=None, axis=alt.Axis(format='~s')),
                        color=alt.Color('Concepto:N', title=None, sort=['Ventas', 'Gastos'],
                                        scale=alt.Scale(domain=['Ventas', 'Gastos'], range=[COLOR_VENTAS, COLOR_GASTOS]),
                                        legend=alt.Legend(orient='top')),
                        tooltip=[alt.Tooltip('Mes:N'), alt.Tooltip('Concepto:N'), alt.Tooltip('Valor:Q', format=',.0f')],
                    ).properties(height=300),
                    width="stretch",
                )
        with g2.container(border=True):
            st.markdown(f"**Productos más vendidos ({mes_seleccionado})**")
            if top_df.empty:
                st.caption("No hay ventas en este periodo.")
            else:
                st.altair_chart(
                    alt.Chart(top_df).mark_bar(cornerRadiusEnd=4, color=COLOR_VENTAS).encode(
                        x=alt.X('Total Venta:Q', title=None, axis=alt.Axis(format='~s')),
                        y=alt.Y('Producto:N', title=None, sort='-x', axis=alt.Axis(labelLimit=220)),
                        tooltip=[alt.Tooltip('Producto:N'), alt.Tooltip('Total Venta:Q', format=',.0f')],
                    ).properties(height=300),
                    width="stretch",
                )

        st.markdown("---")
        st.subheader("Análisis de Inventario Actual")

        inventario_df = get_data("inventario")
        if not inventario_df.empty and not productos_df.empty:
            inventario_df['Stock Actual'] = pd.to_numeric(inventario_df['Stock Actual'], errors='coerce').fillna(0)

            info_productos = productos_df[['NombreProducto', 'CostoCompraDefecto', 'PrecioVentaDefecto']]
            info_productos['CostoCompraDefecto'] = pd.to_numeric(info_productos['CostoCompraDefecto'], errors='coerce').fillna(0)
            info_productos['PrecioVentaDefecto'] = pd.to_numeric(info_productos['PrecioVentaDefecto'], errors='coerce').fillna(0)

            analisis_inv_df = pd.merge(
                inventario_df[inventario_df['Stock Actual'] > 0],
                info_productos,
                left_on='Producto',
                right_on='NombreProducto',
                how='left'
            )

            analisis_inv_df['Valor_Costo'] = analisis_inv_df['Stock Actual'] * analisis_inv_df['CostoCompraDefecto']
            analisis_inv_df['Valor_Venta'] = analisis_inv_df['Stock Actual'] * analisis_inv_df['PrecioVentaDefecto']

            valor_total_costo = analisis_inv_df['Valor_Costo'].sum()
            valor_total_venta = analisis_inv_df['Valor_Venta'].sum()
            ganancia_potencial = valor_total_venta - valor_total_costo

            col_inv1, col_inv2 = st.columns(2)
            col_inv1.metric("📦 Valor del Inventario (a costo)", fmt_dinero(valor_total_costo), border=True)
            col_inv2.metric("💵 Ganancia Potencial del Stock", fmt_dinero(ganancia_potencial), border=True)
        else:
            st.info("No hay datos de inventario o productos para realizar el análisis.")

        st.markdown("---")
        st.subheader(f"Detalle de Movimientos para: {mes_seleccionado}")

        exp_ventas = st.expander("Ver detalle de todas las ventas")
        tabla(ventas_filtradas, dinero=['Precio Unitario', 'Total Venta'], contenedor=exp_ventas)

        exp_compras = st.expander("Ver detalle de compras")
        tabla(compras_filtradas, dinero=['Costo Total', 'Costo Envio'], contenedor=exp_compras)

        exp_obsequios = st.expander("Ver detalle de obsequios (costo)")
        tabla(obsequios_filtrados, dinero=['Costo Total'], contenedor=exp_obsequios)

# --- PESTAÑA DE INVENTARIO ---
elif opcion == "📈 Ver Inventario":
    st.header("Inventario")
    if st.button("🔄 Refrescar Inventario"):
        with st.spinner("Actualizando..."):
            actualizar_inventario()
            st.cache_data.clear()

    inventario_df = get_data("inventario")
    if not inventario_df.empty:
        for col in ['Unidades Compradas', 'Unidades Vendidas', 'Stock Actual']:
            if col in inventario_df.columns:
                inventario_df[col] = pd.to_numeric(inventario_df[col], errors='coerce').fillna(0)
        inventario_df['Unidad'] = inventario_df['Producto'].map(unidad_de)
        inventario_df['Estado'] = [estado_stock(cantidad, MINIMO_PRODUCTO.get(producto)) for cantidad, producto in zip(inventario_df['Stock Actual'], inventario_df['Producto'])]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Referencias", len(inventario_df), border=True)
        m2.metric("🟢 Disponibles", int((inventario_df['Estado'] == "🟢 Disponible").sum()), border=True)
        m3.metric("🟡 Stock bajo", int((inventario_df['Estado'] == "🟡 Bajo").sum()), border=True)
        m4.metric("🔴 Agotados", int((inventario_df['Estado'] == "🔴 Agotado").sum()), border=True)

        f1, f2, f3 = st.columns([3, 2, 2])
        busqueda = f1.text_input("Buscar producto", placeholder="Escribe parte del nombre...")
        categorias = f2.multiselect("Categoría", options=sorted(inventario_df['Talla'].astype(str).unique()))
        estados = f3.multiselect("Estado", options=["🟢 Disponible", "🟡 Bajo", "🔴 Agotado"])

        vista = inventario_df
        if busqueda.strip():
            vista = vista[vista['Producto'].astype(str).str.contains(busqueda.strip(), case=False, regex=False)]
        if categorias:
            vista = vista[vista['Talla'].astype(str).isin(categorias)]
        if estados:
            vista = vista[vista['Estado'].isin(estados)]

        columnas = [c for c in ['Producto', 'Talla', 'Estado', 'Stock Actual', 'Unidad', 'Unidades Compradas', 'Unidades Vendidas', 'Fecha Actualizacion'] if c in vista.columns]
        numericas = [c for c in ['Stock Actual', 'Unidades Compradas', 'Unidades Vendidas'] if c in columnas]
        st.dataframe(
            vista[columnas].sort_values('Producto').style.format({c: fmt_cantidad for c in numericas}),
            width="stretch",
            hide_index=True,
            column_config={
                'Talla': st.column_config.Column("Categoría"),
                'Stock Actual': st.column_config.Column("Stock"),
                'Unidades Compradas': st.column_config.Column("Comprado"),
                'Unidades Vendidas': st.column_config.Column("Vendido"),
                'Fecha Actualizacion': st.column_config.Column("Actualizado"),
            },
        )
        st.caption(f"Mostrando {len(vista)} de {len(inventario_df)} referencias.")
    else:
        st.info("No hay datos de inventario. Registra compras para empezar.")
