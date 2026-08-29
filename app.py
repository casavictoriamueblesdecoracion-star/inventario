import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import uuid

# =============================================================================
# CONFIGURACIÓN DE TU NEGOCIO  ←  MODIFICA ESTOS VALORES
# =============================================================================
# Estos son los únicos valores que debes cambiar para personalizar la app
# para tu empresa. Léelos con cuidado.

# Nombre que aparecerá en la pestaña del navegador y como título principal.
NOMBRE_APP = "MI EMPRESA" 

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

# =============================================================================
# A PARTIR DE AQUÍ NO NECESITAS MODIFICAR NADA (a menos que quieras adaptar
# la lógica del negocio, agregar campos, etc.)
# =============================================================================

st.set_page_config(
    page_title=NOMBRE_APP,
    page_icon=ICONO_APP,
    layout="wide"
)

# --- LOGO EN LA BARRA LATERAL ---
if LOGO_URL:
    st.sidebar.image(LOGO_URL, use_container_width=True)
st.sidebar.title("Menú de Navegación")


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

# --- CARGA DE DATOS MAESTROS ---
@st.cache_data(ttl=300)
def load_master_data():
    """Carga los datos de las hojas de gestión y los procesa."""
    productos_df = pd.DataFrame(sheets["productos"].get_all_records())
    clientes_df = pd.DataFrame(sheets["clientes"].get_all_records())
    proveedores_df = pd.DataFrame(sheets["proveedores"].get_all_records())

    productos_dict = {}
    if not productos_df.empty:
        for _, row in productos_df.iterrows():
            tallas = [t.strip() for t in str(row['TallasDisponibles']).split(',')]
            productos_dict[row['NombreProducto']] = tallas

    return productos_df, productos_dict, clientes_df, proveedores_df

productos_df, PRODUCTOS, clientes_df, proveedores_df = load_master_data()

# --- FUNCIONES AUXILIARES ---
def get_data(sheet_name):
    """Obtiene datos de una hoja y los devuelve como DataFrame."""
    records = sheets[sheet_name].get_all_records()
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

    inventario_df[['Producto', 'Talla']] = inventario_df['SKU'].str.split(' - ', expand=True)
    inventario_df['Stock Actual'] = inventario_df['Unidades Compradas'] - inventario_df['Unidades Salientes']
    inventario_df['Fecha Actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
st.title(f"{ICONO_APP} {NOMBRE_APP}")

opcion = st.sidebar.radio(
    "Selecciona una opción:",
    ["📈 Ver Inventario", "💰 Registrar Venta", "🛒 Registrar Compra", "🎁 Registrar Obsequio", "📊 Finanzas", "🧾 Cuentas por Cobrar", "⚙️ Gestión"]
)

# --- PESTAÑA DE GESTIÓN ---
if opcion == "⚙️ Gestión":
    st.header("Gestión de Datos Maestros")
    st.info("Aquí puedes añadir nuevos productos, clientes y proveedores a tus listas.")
    tab1, tab2, tab3 = st.tabs(["🛍️ Productos", "👥 Clientes", "🚚 Proveedores"])

    with tab1:
        st.subheader("Añadir Nuevo Producto")
        with st.form("nuevo_producto_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del Nuevo Producto")
            tallas = st.text_input("Tallas Disponibles (separadas por coma, ej: S,M,L)")
            precio = st.number_input("Precio de Venta por Defecto", min_value=0.0, format="%.2f")
            costo = st.number_input("Costo de Compra por Defecto", min_value=0.0, format="%.2f")
            if st.form_submit_button("Añadir Producto"):
                if nombre and tallas:
                    sheets["productos"].append_row([nombre, tallas, precio, costo])
                    st.success(f"¡Producto '{nombre}' añadido!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("Nombre y Tallas son campos obligatorios.")
        st.subheader("Lista de Productos Actual")
        st.dataframe(productos_df, use_container_width=True)

    with tab2:
        st.subheader("Añadir Nuevo Cliente")
        with st.form("nuevo_cliente_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del Nuevo Cliente")
            if st.form_submit_button("Añadir Cliente"):
                if nombre:
                    sheets["clientes"].append_row([nombre])
                    st.success(f"¡Cliente '{nombre}' añadido!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("El nombre del cliente no puede estar vacío.")
        st.subheader("Lista de Clientes Actual")
        st.dataframe(clientes_df, use_container_width=True)

    with tab3:
        st.subheader("Añadir Nuevo Proveedor")
        with st.form("nuevo_proveedor_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del Nuevo Proveedor")
            if st.form_submit_button("Añadir Proveedor"):
                if nombre:
                    sheets["proveedores"].append_row([nombre])
                    st.success(f"¡Proveedor '{nombre}' añadido!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("El nombre del proveedor no puede estar vacío.")
        st.subheader("Lista de Proveedores Actual")
        st.dataframe(proveedores_df, use_container_width=True)

# --- PESTAÑA DE VENTAS ---
elif opcion == "💰 Registrar Venta":
    st.header("Formulario de Registro de Ventas")

    st.subheader("Paso 1: Elige el Cliente")
    col1, col2 = st.columns([2, 2])
    with col1:
        lista_clientes = [""] + clientes_df['NombreCliente'].tolist()
        cliente_existente = st.selectbox("Selecciona un Cliente Existente", options=lista_clientes, help="Elige un cliente de tu lista.")
    with col2:
        cliente_nuevo = st.text_input("O añade un Cliente Nuevo aquí", help="Si el cliente no existe, escríbelo aquí.")

    cliente_final = cliente_nuevo.strip() if cliente_nuevo else cliente_existente

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
                talla_vendida = c1.selectbox("Talla", options=PRODUCTOS.get(producto_vendido, []))
                cantidad_vendida = c2.number_input("Cantidad", min_value=1, step=1)
                precio_unitario = c3.number_input("Precio Unitario ($)", min_value=0.0, value=precio_defecto, format="%.2f", key=f"precio_venta_{producto_vendido}")

                if st.form_submit_button("➕ Añadir Producto"):
                    item = {"Producto": producto_vendido, "Talla": talla_vendida, "Cantidad": cantidad_vendida, "Precio Unitario": precio_unitario, "Total Venta": cantidad_vendida * precio_unitario}
                    st.session_state.venta_actual.append(item)
                    st.rerun()

        if st.session_state.venta_actual:
            st.markdown("---")
            st.subheader("Venta Actual")
            st.dataframe(pd.DataFrame(st.session_state.venta_actual), use_container_width=True)

            with st.form("eliminar_item_venta_form"):
                indices_a_eliminar = st.multiselect("Selecciona productos para eliminar", options=range(len(st.session_state.venta_actual)), format_func=lambda i: f"{st.session_state.venta_actual[i]['Producto']} (Talla: {st.session_state.venta_actual[i]['Talla']})")
                if st.form_submit_button("🗑️ Eliminar Seleccionados"):
                    st.session_state.venta_actual = [item for i, item in enumerate(st.session_state.venta_actual) if i not in indices_a_eliminar]
                    st.rerun()

            if st.session_state.venta_actual:
                st.markdown("---")
                st.subheader(f"Paso 3: Finalizar Venta para {cliente_final}")
                total_venta_actual = pd.DataFrame(st.session_state.venta_actual)["Total Venta"].sum()
                st.info(f"**Total de la Venta Actual: ${total_venta_actual:,.2f}**")

                estado_pago = st.selectbox("Estado del Pago", ["Pagado", "Abono", "Debe"], key="estado_pago_selector")

                with st.form("finalizar_venta_form"):
                    monto_abono_inicial = 0
                    if estado_pago == "Abono":
                        monto_abono_inicial = st.number_input("Monto del Abono Inicial ($)", min_value=0.01, max_value=total_venta_actual, format="%.2f")

                    if st.form_submit_button("✅ Registrar Venta Completa"):
                        if estado_pago == "Abono" and monto_abono_inicial <= 0:
                            st.error("Para un 'Abono', el monto debe ser mayor a cero.")
                        else:
                            if cliente_nuevo and cliente_nuevo not in clientes_df['NombreCliente'].tolist():
                                sheets["clientes"].append_row([cliente_nuevo])
                                st.success(f"¡Nuevo cliente '{cliente_nuevo}' añadido a la base de datos!")
                                st.cache_data.clear()

                            with st.spinner("Registrando venta y pago inicial..."):
                                id_venta = f"VENTA-{uuid.uuid4().hex[:8].upper()}"
                                fecha_venta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                if estado_pago == "Pagado":
                                    id_pago = f"PAGO-{uuid.uuid4().hex[:8].upper()}"
                                    sheets["pagos"].append_row([id_pago, id_venta, fecha_venta, total_venta_actual])
                                elif estado_pago == "Abono":
                                    id_pago = f"PAGO-{uuid.uuid4().hex[:8].upper()}"
                                    sheets["pagos"].append_row([id_pago, id_venta, fecha_venta, monto_abono_inicial])

                                filas_venta = [[id_venta, fecha_venta, item["Producto"], item["Talla"], cliente_final, item["Cantidad"], item["Precio Unitario"], item["Total Venta"], estado_pago] for item in st.session_state.venta_actual]
                                sheets["ventas"].append_rows(filas_venta)

                                st.success(f"¡Venta {id_venta} registrada!")
                                st.balloons()
                                st.session_state.venta_actual = []
                                actualizar_inventario()
                                st.rerun()
    else:
        st.warning("Por favor, selecciona o añade un cliente para continuar.")

# --- PESTAÑA DE COMPRAS ---
elif opcion == "🛒 Registrar Compra":
    st.header("Formulario de Registro de Compras")

    st.subheader("Paso 1: Elige el Proveedor")
    col1, col2 = st.columns([2, 2])
    with col1:
        lista_proveedores = [""] + proveedores_df['NombreProveedor'].tolist()
        proveedor_existente = st.selectbox("Selecciona un Proveedor Existente", options=lista_proveedores)
    with col2:
        proveedor_nuevo = st.text_input("O añade un Proveedor Nuevo aquí")

    proveedor_final = proveedor_nuevo.strip() if proveedor_nuevo else proveedor_existente

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
                talla_comprada = c1.selectbox("Talla", options=PRODUCTOS.get(producto_comprado, []))
                cantidad_comprada = c2.number_input("Cantidad", min_value=1, step=1)
                costo_unitario = c3.number_input("Costo Unitario ($)", min_value=0.0, value=costo_defecto, format="%.2f", key=f"costo_compra_{producto_comprado}")

                if st.form_submit_button("➕ Añadir Producto"):
                    item = {"Producto": producto_comprado, "Talla": talla_comprada, "Cantidad": cantidad_comprada, "Costo Total": cantidad_comprada * costo_unitario}
                    st.session_state.compra_actual.append(item)
                    st.rerun()

        if st.session_state.compra_actual:
            st.markdown("---")
            st.subheader("Orden de Compra Actual")
            st.dataframe(pd.DataFrame(st.session_state.compra_actual), use_container_width=True)

            with st.form("eliminar_item_compra_form"):
                indices_a_eliminar = st.multiselect("Selecciona productos para eliminar", options=range(len(st.session_state.compra_actual)), format_func=lambda i: f"{st.session_state.compra_actual[i]['Producto']} (Talla: {st.session_state.compra_actual[i]['Talla']})")
                if st.form_submit_button("🗑️ Eliminar Seleccionados"):
                    st.session_state.compra_actual = [item for i, item in enumerate(st.session_state.compra_actual) if i not in indices_a_eliminar]
                    st.rerun()

            if st.session_state.compra_actual:
                st.markdown("---")
                st.subheader(f"Paso 3: Finalizar Compra de {proveedor_final}")
                with st.form("finalizar_compra_form"):
                    costo_envio = st.number_input("Costo Total del Envío ($)", min_value=0.0, format="%.2f")
                    if st.form_submit_button("✅ Registrar Compra Completa"):
                        if proveedor_nuevo and proveedor_nuevo not in proveedores_df['NombreProveedor'].tolist():
                            sheets["proveedores"].append_row([proveedor_nuevo])
                            st.success(f"¡Nuevo proveedor '{proveedor_nuevo}' añadido a la base de datos!")
                            st.cache_data.clear()

                        with st.spinner("Registrando compra..."):
                            id_compra = f"COMPRA-{uuid.uuid4().hex[:8].upper()}"
                            fecha_compra = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            filas_para_añadir = [[id_compra, fecha_compra, item["Producto"], item["Talla"], proveedor_final, item["Cantidad"], item["Costo Total"], costo_envio] for item in st.session_state.compra_actual]
                            sheets["compras"].append_rows(filas_para_añadir)
                            st.success(f"¡Compra {id_compra} registrada!")
                            st.balloons()
                            st.session_state.compra_actual = []
                            actualizar_inventario()
                            st.rerun()
    else:
        st.warning("Por favor, selecciona o añade un proveedor para continuar.")

# --- PESTAÑA DE OBSEQUIOS ---
elif opcion == "🎁 Registrar Obsequio":
    st.header("Formulario de Registro de Obsequios")
    st.warning("Esta acción disminuirá tu inventario y se registrará como un costo (no un ingreso).")

    with st.form("obsequio_form", clear_on_submit=True):
        producto_obsequiado = st.selectbox("Producto a Obsequiar", options=list(PRODUCTOS.keys()))

        c1, c2, c3 = st.columns(3)
        talla_obsequiada = c1.selectbox("Talla", options=PRODUCTOS.get(producto_obsequiado, []))
        cantidad_obsequiada = c2.number_input("Cantidad", min_value=1, step=1)
        motivo = c3.text_input("Motivo / Cliente")

        if st.form_submit_button("Registrar Obsequio"):
            if producto_obsequiado and motivo:
                with st.spinner("Registrando obsequio..."):
                    costo_unitario = float(productos_df[productos_df['NombreProducto'] == producto_obsequiado]['CostoCompraDefecto'].iloc[0])
                    costo_total_obsequio = costo_unitario * cantidad_obsequiada

                    id_obsequio = f"OBSEQUIO-{uuid.uuid4().hex[:8].upper()}"
                    fecha_obsequio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    st.header("Gestión de Cuentas por Cobrar")

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

            st.subheader("Resumen de Deudas")
            st.dataframe(resumen_deudas[resumen_deudas['Saldo Pendiente'] > 0.01], use_container_width=True)

            st.markdown("---")
            st.subheader("Registrar Abono o Pago Final")
            with st.form("registrar_abono_form"):
                id_venta_pago = st.selectbox("Selecciona el ID de la Venta", options=resumen_deudas['ID Venta'].unique())
                monto_pago = st.number_input("Monto del Pago ($)", min_value=0.01, format="%.2f")

                if st.form_submit_button("Registrar Pago"):
                    if id_venta_pago and monto_pago > 0:
                        with st.spinner("Registrando pago..."):
                            id_pago = f"PAGO-{uuid.uuid4().hex[:8].upper()}"
                            fecha_pago = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            sheets["pagos"].append_row([id_pago, id_venta_pago, fecha_pago, monto_pago])

                            venta_info = resumen_deudas[resumen_deudas['ID Venta'] == id_venta_pago].iloc[0]
                            nuevo_saldo = venta_info['Saldo Pendiente'] - monto_pago

                            if nuevo_saldo <= 0.01:
                                cell_list = sheets["ventas"].findall(id_venta_pago)
                                estado_col_index = sheets["ventas"].row_values(1).index('Estado Pago') + 1
                                for cell in cell_list:
                                    sheets["ventas"].update_cell(cell.row, estado_col_index, "Pagado")
                                st.success(f"¡Pago registrado y Venta {id_venta_pago} marcada como 'Pagado'!")
                            else:
                                st.success(f"¡Abono de ${monto_pago:,.2f} registrado para la venta {id_venta_pago}!")

                            st.balloons()
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

        meses_disponibles = sorted(pd.concat([ventas_df_full.get('Mes'), compras_df_full.get('Mes')]).dropna().unique(), reverse=True)
        if not meses_disponibles:
             st.warning("No hay datos con fechas válidas para generar el reporte.")
             st.stop()

        mes_seleccionado = st.selectbox("Selecciona un Mes para Analizar", options=["Todos"] + meses_disponibles)

        if mes_seleccionado != "Todos":
            ventas_filtradas = ventas_df_full[ventas_df_full['Mes'] == mes_seleccionado] if not ventas_df_full.empty else pd.DataFrame()
            compras_filtradas = compras_df_full[compras_df_full['Mes'] == mes_seleccionado] if not compras_df_full.empty else pd.DataFrame()
            pagos_filtrados = pagos_df_full[pagos_df_full['Mes'] == mes_seleccionado] if not pagos_df_full.empty else pd.DataFrame()
            obsequios_filtrados = obsequios_df_full[obsequios_df_full['Mes'] == mes_seleccionado] if not obsequios_df_full.empty else pd.DataFrame()
        else:
            ventas_filtradas = ventas_df_full
            compras_filtradas = compras_df_full
            pagos_filtrados = pagos_df_full
            obsequios_filtrados = obsequios_df_full

        ingresos_de_pagos = pagos_filtrados['Monto Pagado'].sum()
        ingresos_legacy = 0
        ventas_pagadas_periodo = ventas_filtradas[ventas_filtradas['Estado Pago'] == 'Pagado']
        if not ventas_pagadas_periodo.empty:
            id_ventas_con_pago = pagos_df_full['ID Venta'].unique()
            ventas_legacy_pagadas = ventas_pagadas_periodo[~ventas_pagadas_periodo['ID Venta'].isin(id_ventas_con_pago)]
            ingresos_legacy = ventas_legacy_pagadas.groupby('ID Venta')['Total Venta'].sum().sum()
        total_ingresos_reales = ingresos_de_pagos + ingresos_legacy

        total_costo_producto = compras_filtradas['Costo Total'].sum()
        total_costo_envio = compras_filtradas.drop_duplicates(subset=['ID Compra'])['Costo Envio'].sum() if not compras_filtradas.empty else 0
        total_costo_obsequios = obsequios_filtrados['Costo Total'].sum()
        total_gastos = total_costo_producto + total_costo_envio + total_costo_obsequios

        ganancia_real = total_ingresos_reales - total_gastos

        total_ventas_brutas = get_data("ventas")['Total Venta'].sum()
        total_pagado_historico = get_data("pagos")['Monto Pagado'].sum()
        total_por_cobrar = total_ventas_brutas - total_pagado_historico

        st.markdown("---")
        st.subheader(f"Resumen Financiero para: {mes_seleccionado}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Ingresos Reales (Recibido)", f"${total_ingresos_reales:,.2f}")
        col2.metric("💸 Gastos Totales", f"${total_gastos:,.2f}")
        col3.metric("📈 Ganancia Real", f"${ganancia_real:,.2f}", delta=f"{ganancia_real:,.2f}")
        col4.metric("🧾 Cuentas por Cobrar (Total)", f"${total_por_cobrar:,.2f}")

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
            col_inv1.metric("📦 Valor del Inventario (a costo)", f"${valor_total_costo:,.2f}")
            col_inv2.metric("💵 Ganancia Potencial del Stock", f"${ganancia_potencial:,.2f}")
        else:
            st.info("No hay datos de inventario o productos para realizar el análisis.")

        st.markdown("---")
        st.subheader(f"Detalle de Movimientos para: {mes_seleccionado}")

        exp_ventas = st.expander("Ver detalle de todas las ventas")
        exp_ventas.dataframe(ventas_filtradas, use_container_width=True)

        exp_compras = st.expander("Ver detalle de compras")
        exp_compras.dataframe(compras_filtradas, use_container_width=True)

        exp_obsequios = st.expander("Ver detalle de obsequios (costo)")
        exp_obsequios.dataframe(obsequios_filtrados, use_container_width=True)

# --- PESTAÑA DE INVENTARIO ---
elif opcion == "📈 Ver Inventario":
    st.header("Vista del Inventario Actual")
    if st.button("🔄 Refrescar Inventario"):
        with st.spinner("Actualizando..."):
            actualizar_inventario()
            st.cache_data.clear()

    inventario_df = get_data("inventario")
    if not inventario_df.empty:
        st.dataframe(inventario_df, use_container_width=True)
    else:
        st.info("No hay datos de inventario. Registra compras para empezar.")
