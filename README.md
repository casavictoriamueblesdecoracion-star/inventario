# Plantilla — Sistema de Inventario y Ventas

Aplicación web para gestionar **inventario, ventas, compras, obsequios, clientes, proveedores, pagos y finanzas** de un pequeño negocio. Está hecha en **Streamlit** (Python) y usa una **hoja de cálculo de Google Sheets** como base de datos.

> 📌 Esta es una **plantilla**. Para ponerla en marcha tienes que crear tus propias cuentas (GitHub, Google Cloud, Streamlit Cloud) y configurar la app con tus datos. Esta guía te lleva de la mano paso a paso, **incluso si nunca has usado estas herramientas**.

---

## Tabla de contenido

1. [Lo que necesitas antes de empezar](#1-lo-que-necesitas-antes-de-empezar)
2. [Resumen del flujo](#2-resumen-del-flujo)
3. [PASO 1 — Crear cuenta en GitHub y subir la plantilla](#paso-1--crear-cuenta-en-github-y-subir-la-plantilla)
4. [PASO 2 — Configurar el backend (Google Cloud + Service Account)](#paso-2--configurar-el-backend-google-cloud--service-account)
5. [PASO 3 — Crear la hoja de cálculo (base de datos)](#paso-3--crear-la-hoja-de-cálculo-base-de-datos)
6. [PASO 4 — Compartir la hoja con la cuenta de servicio](#paso-4--compartir-la-hoja-con-la-cuenta-de-servicio)
7. [PASO 5 — Personalizar `app.py` con los datos de tu empresa](#paso-5--personalizar-apppy-con-los-datos-de-tu-empresa)
8. [PASO 6 — (Opcional) Probar la app en tu computador](#paso-6--opcional-probar-la-app-en-tu-computador)
9. [PASO 7 — Desplegar en Streamlit Cloud](#paso-7--desplegar-en-streamlit-cloud)
10. [Estructura de las hojas (encabezados exactos)](#estructura-de-las-hojas-encabezados-exactos)
11. [Cómo usar la app día a día](#cómo-usar-la-app-día-a-día)
12. [Solución de problemas frecuentes](#solución-de-problemas-frecuentes)

---

## 1. Lo que necesitas antes de empezar

Crea (gratis) las siguientes cuentas si no las tienes:

- ✅ Una **cuenta de Google** (la que usas para Gmail/Drive sirve).
- ✅ Una **cuenta de GitHub** → https://github.com/signup
- ✅ Una **cuenta de Streamlit Cloud** → https://streamlit.io/cloud (se inicia sesión con GitHub).

No necesitas saber programar. Vas a tocar **un solo archivo** (`app.py`), solo en una sección al inicio donde se cambia el nombre de tu negocio y el de tu hoja de cálculo.

---

## 2. Resumen del flujo

La app es una página web que muestra y modifica una **hoja de cálculo de Google Sheets**. Para que funcione:

1. Tu **código** vive en GitHub.
2. **Streamlit Cloud** toma el código de GitHub y lo convierte en una página web.
3. La app, al abrirse, se conecta a tu **Google Sheets** usando una "cuenta de servicio" de Google (un usuario robot con permisos para leer y escribir en tu hoja).

```
[Tu Google Sheet] ⇄ [App Streamlit] ← (lee de) ← [GitHub repositorio]
        ↑
    (la cuenta de servicio le da permiso a la app)
```

---

## PASO 1 — Crear cuenta en GitHub y subir la plantilla

### 1.1 Crea la cuenta
- Ve a https://github.com/signup y regístrate.

### 1.2 Crea un nuevo repositorio
1. Una vez dentro de GitHub, haz clic en el botón verde **New** (o **+** arriba a la derecha → *New repository*).
2. **Repository name:** elige un nombre, por ejemplo `inventario-mi-empresa`.
3. **Public** o **Private**: Streamlit Cloud (plan gratuito) puede leer ambos. Recomendado: **Private**.
4. **NO marques** "Add a README", "Add .gitignore" ni "license" (la plantilla ya los trae).
5. Clic en **Create repository**.

### 1.3 Sube los archivos de la plantilla
La forma más fácil (sin instalar nada) es por la web:

1. En tu repositorio recién creado verás la opción **"uploading an existing file"** (o ve a la pestaña **Add file → Upload files**).
2. **Arrastra TODOS los archivos** de esta carpeta `inventario-ventas-plantilla/` (excepto `credentials.ejemplo.json` y `.streamlit/secrets.toml.ejemplo` si no los necesitas), incluyendo:
   - `app.py`
   - `requirements.txt`
   - `.gitignore`
   - La carpeta `assets/`
3. Escribe un mensaje de commit (ej: "primer commit") y clic en **Commit changes**.

> 💡 **Importante:** **NUNCA subas** los archivos `credentials.json` ni `.streamlit/secrets.toml` reales (con tus claves privadas). El archivo `.gitignore` ya está configurado para evitarlo, pero ten cuidado al arrastrar archivos.

---

## PASO 2 — Configurar el backend (Google Cloud + Service Account)

Este paso crea el "usuario robot" (cuenta de servicio) que le permitirá a tu app leer y escribir en Google Sheets.

### 2.1 Crear un proyecto en Google Cloud
1. Entra a https://console.cloud.google.com/ con tu cuenta de Google.
2. Si es tu primera vez, acepta los términos.
3. Arriba, junto al logo "Google Cloud", clic en el **selector de proyecto** → **NEW PROJECT**.
4. **Project name:** algo como `inventario-mi-empresa` → clic en **Create**.
5. Espera unos segundos y selecciona el proyecto recién creado.

### 2.2 Habilitar las APIs necesarias
Tienes que activar dos APIs (servicios) en tu proyecto:

1. Arriba en la barra de búsqueda escribe **Google Sheets API** → entra al resultado → clic en **Enable**.
2. Vuelve a la barra de búsqueda, escribe **Google Drive API** → entra → clic en **Enable**.

### 2.3 Crear la cuenta de servicio
1. En la barra de búsqueda escribe **Service Accounts** y entra.
2. Clic en **+ Create Service Account**.
3. **Service account name:** ej `inventario-app`. Clic en **Create and continue**.
4. **Grant this service account access**: puedes dejarlo en blanco. Clic en **Continue** y luego **Done**.
5. Te aparecerá una lista. Clic sobre la cuenta que acabas de crear.
6. Ve a la pestaña **KEYS** → **Add Key** → **Create new key** → tipo **JSON** → **Create**.
7. Se descargará un archivo `.json`. **Guárdalo bien**, lo necesitarás más adelante. Renómbralo a `credentials.json`.

### 2.4 Anota el email de la cuenta de servicio
Dentro del JSON (o en la pantalla de la cuenta de servicio) verás un campo `client_email` que se ve así:

```
inventario-app@tu-proyecto-id.iam.gserviceaccount.com
```

**Cópialo**. Lo vas a necesitar en el Paso 4.

> ⚠️ El archivo `credentials.json` es como una contraseña. **NUNCA lo subas a GitHub**, no lo compartas por chat ni por email. Si se filtra, alguien puede modificar tu hoja de cálculo.

---

## PASO 3 — Crear la hoja de cálculo (base de datos)

### 3.1 Crear la hoja
1. Ve a https://sheets.google.com y crea una **hoja de cálculo nueva**.
2. Nómbrala con un nombre claro, por ejemplo: `BaseDeDatos_MiEmpresa`. **Anota este nombre exacto**, lo usarás en `app.py`.

### 3.2 Crear las 8 pestañas con sus encabezados
La app espera **exactamente 8 hojas** (pestañas) con nombres y columnas específicas. En la parte inferior del archivo de Google Sheets verás pestañas; renombra la primera y agrega las demás.

Crea estas 8 pestañas (los nombres deben coincidir LETRA POR LETRA, mayúsculas incluidas):

| # | Nombre de la pestaña | Encabezados (fila 1) |
|---|---|---|
| 1 | `Productos` | `NombreProducto` · `TallasDisponibles` · `PrecioVentaDefecto` · `CostoCompraDefecto` |
| 2 | `Clientes` | `NombreCliente` |
| 3 | `Proveedores` | `NombreProveedor` |
| 4 | `Ventas` | `ID Venta` · `Fecha` · `Producto` · `Talla` · `Cliente` · `Cantidad` · `Precio Unitario` · `Total Venta` · `Estado Pago` |
| 5 | `Compras` | `ID Compra` · `Fecha` · `Producto` · `Talla` · `Proveedor` · `Cantidad` · `Costo Total` · `Costo Envio` |
| 6 | `Pagos` | `ID Pago` · `ID Venta` · `Fecha Pago` · `Monto Pagado` |
| 7 | `Obsequios` | `ID Obsequio` · `Fecha` · `Producto` · `Talla` · `Cantidad` · `Motivo` · `Costo Total` |
| 8 | `Inventario` | (déjala vacía: la app la llena automáticamente) |

> 🔑 Los **nombres de las columnas son sensibles a mayúsculas, espacios y tildes**. Cópialos tal cual aparecen.

> 💡 La pestaña `Productos` no acepta tallas con espacios al inicio/final. Las tallas se separan por coma, ejemplo: `S,M,L,XL`.

---

## PASO 4 — Compartir la hoja con la cuenta de servicio

Aunque la hoja sea tuya, la cuenta de servicio (el robot) **no puede acceder hasta que se la compartas**.

1. Abre tu hoja de cálculo.
2. Clic en el botón **Share** (Compartir) arriba a la derecha.
3. En "Add people, groups, and calendar events" pega el `client_email` que copiaste en el Paso 2.4. Algo como:
   ```
   inventario-app@tu-proyecto-id.iam.gserviceaccount.com
   ```
4. Asígnale el rol de **Editor** (porque la app necesita escribir).
5. **Desmarca** la opción "Notify people" (no le va a llegar correo a un robot).
6. Clic en **Share**.

---

## PASO 5 — Personalizar `app.py` con los datos de tu empresa

Abre el archivo `app.py` desde tu repositorio en GitHub (clic en el archivo → ícono de lápiz **Edit**). Busca al inicio del archivo este bloque:

```python
# =============================================================================
# CONFIGURACIÓN DE TU NEGOCIO  ←  MODIFICA ESTOS VALORES
# =============================================================================
NOMBRE_APP = "Gestor de Negocio"
ICONO_APP = "🌟"
NOMBRE_HOJA_CALCULO = "BaseDeDatos_Negocio"
LOGO_URL = ""
```

Cambia los valores:

- **`NOMBRE_APP`** → el nombre que se mostrará en la pestaña del navegador y como título. Ej: `"Inventario Tienda Mariana"`.
- **`ICONO_APP`** → un emoji que aparecerá como ícono. Ej: `"🛍️"`, `"👕"`, `"☕"`.
- **`NOMBRE_HOJA_CALCULO`** → el nombre **exacto** de la hoja de cálculo que creaste en el Paso 3. Ej: `"BaseDeDatos_MiEmpresa"`.
- **`LOGO_URL`** → si quieres logo:
  1. Sube tu logo (jpeg/png) a la carpeta `assets/` del repositorio (Add file → Upload files).
  2. Entra al archivo subido en GitHub, clic en **Raw**, copia la URL del navegador.
  3. Pégala entre las comillas, ej: `"https://raw.githubusercontent.com/tu_usuario/tu_repo/main/assets/logo.jpeg"`.
  4. Si no quieres logo, déjalo como `""`.

Guarda con **Commit changes**.

---

## PASO 6 — (Opcional) Probar la app en tu computador

> Si prefieres saltar al despliegue, ve directo al PASO 7. Esta sección es opcional.

### 6.1 Instalar Python
Descarga e instala Python 3.10 o superior desde https://www.python.org/downloads/.
Durante la instalación, **marca la casilla "Add Python to PATH"**.

### 6.2 Descargar tu repositorio
- En tu repositorio de GitHub: botón verde **Code** → **Download ZIP**. Descomprímelo en una carpeta.
- (Alternativa: usar Git, pero no es indispensable).

### 6.3 Poner el archivo de credenciales
Copia el `credentials.json` que descargaste en el Paso 2.3 dentro de la carpeta del proyecto, **al lado** de `app.py`.

### 6.4 Instalar dependencias y ejecutar
Abre una terminal (CMD, PowerShell o Terminal) en la carpeta del proyecto y ejecuta:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abrirá un navegador en `http://localhost:8501` con tu app.

---

## PASO 7 — Desplegar en Streamlit Cloud

Aquí es donde la app se vuelve **una página web pública** (o privada) accesible desde cualquier celular o computador.

### 7.1 Iniciar sesión en Streamlit Cloud
1. Ve a https://share.streamlit.io
2. Inicia sesión con tu cuenta de **GitHub**. Acepta los permisos.

### 7.2 Crear la app
1. Clic en **Create app** (o **New app**).
2. Selecciona el repositorio que creaste en el Paso 1.
3. **Branch:** `main`.
4. **Main file path:** `app.py`.
5. (Opcional) **App URL:** elige un subdominio personalizado, ej: `inventario-mariana.streamlit.app`.
6. **Antes de hacer Deploy**, clic en **Advanced settings** → ve a la sección **Secrets**.

### 7.3 Pegar las credenciales en Secrets
Esta es la parte más delicada. Necesitas convertir el contenido de tu `credentials.json` en un formato llamado **TOML**.

1. Abre tu `credentials.json` con un editor de texto (Bloc de notas, VS Code, etc.).
2. En la ventana de Secrets de Streamlit, pega lo siguiente y **reemplaza cada valor** con el del archivo JSON:

```toml
[gcp_service_account]
type = "service_account"
project_id = "tu-proyecto-id"
private_key_id = "xxxxxxxxxxxxxxxxxxxxx"
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADAN...===\n-----END PRIVATE KEY-----\n"
client_email = "inventario-app@tu-proyecto-id.iam.gserviceaccount.com"
client_id = "1234567890"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"
```

> ⚠️ **El campo `private_key` es el más complicado**: en el JSON viene en una sola línea muy larga con muchos `\n`. Cópialo COMPLETO (incluyendo `-----BEGIN PRIVATE KEY-----` y `-----END PRIVATE KEY-----`), entre comillas dobles, **sin alterar los `\n`** (déjalos tal cual están).
>
> El archivo `.streamlit/secrets.toml.ejemplo` que viene en la plantilla muestra el formato exacto.

### 7.4 Lanzar la app
- Clic en **Deploy**. Espera 1-3 minutos mientras Streamlit instala dependencias.
- Si todo va bien, verás la app en línea. Compártela con el link.

---

## Estructura de las hojas (encabezados exactos)

Aquí los encabezados de referencia, copiables tal cual:

**Productos** (fila 1):
```
NombreProducto | TallasDisponibles | PrecioVentaDefecto | CostoCompraDefecto
```

**Clientes:**
```
NombreCliente
```

**Proveedores:**
```
NombreProveedor
```

**Ventas:**
```
ID Venta | Fecha | Producto | Talla | Cliente | Cantidad | Precio Unitario | Total Venta | Estado Pago
```

**Compras:**
```
ID Compra | Fecha | Producto | Talla | Proveedor | Cantidad | Costo Total | Costo Envio
```

**Pagos:**
```
ID Pago | ID Venta | Fecha Pago | Monto Pagado
```

**Obsequios:**
```
ID Obsequio | Fecha | Producto | Talla | Cantidad | Motivo | Costo Total
```

**Inventario:** se llena sola; no toques las columnas a mano.

---

## Cómo usar la app día a día

La app tiene 7 secciones en el menú lateral:

- **📈 Ver Inventario** — muestra el stock disponible por producto y talla.
- **💰 Registrar Venta** — ventas con cliente, productos, total y estado de pago (Pagado / Abono / Debe).
- **🛒 Registrar Compra** — compras al proveedor, con costo de envío.
- **🎁 Registrar Obsequio** — descuenta inventario y lo registra como costo.
- **📊 Finanzas** — ingresos, gastos, ganancia real, valor de inventario, filtrable por mes.
- **🧾 Cuentas por Cobrar** — saldos pendientes y registro de abonos.
- **⚙️ Gestión** — alta de productos, clientes y proveedores nuevos.

> 💡 Antes de empezar a vender, ve a **⚙️ Gestión → 🛍️ Productos** y carga al menos un producto con sus tallas, precio y costo. Sin productos cargados, las pantallas de venta y compra no muestran opciones.

---

## Solución de problemas frecuentes

**❌ "No se encontró la hoja de cálculo 'BaseDeDatos_Negocio'"**
- Revisa que `NOMBRE_HOJA_CALCULO` en `app.py` coincida **letra por letra** con el nombre del archivo en Google Sheets.
- Asegúrate de haber compartido la hoja con el `client_email` de la cuenta de servicio (Paso 4).

**❌ "Falta una o más hojas requeridas"**
- Tu archivo de Google Sheets debe tener **las 8 pestañas** con los nombres exactos del Paso 3. Verifica mayúsculas y tildes.

**❌ La app despliega pero al abrirla da error sobre `credentials`**
- En Streamlit Cloud verifica que **Secrets** tenga el bloque `[gcp_service_account]` completo y bien formateado. Especialmente el `private_key` con todos los `\n`.

**❌ KeyError: 'NombreProducto' (u otro encabezado)**
- Una columna de la hoja está mal escrita. Compara con la tabla del Paso 3.

**❌ El logo no aparece**
- Verifica que la URL en `LOGO_URL` sea la versión **Raw** de GitHub (empieza con `https://raw.githubusercontent.com/...`), no el link normal.
- Si el repositorio es **privado**, GitHub no entrega imágenes a Streamlit. Solución: hazlo público, o usa otro hosting (Drive público, Imgur, etc.).

**❌ "Quota exceeded" al cargar muchos datos**
- Google Sheets tiene un límite de lecturas/escrituras por minuto. La app ya tiene caché (`ttl=300`), pero si vendes mucho, considera migrar a una base de datos real (Postgres, Supabase) más adelante.

---

## Soporte

Esta plantilla está basada en un proyecto real ya en producción. Si tienes dudas:
- Revisa primero los mensajes de error que muestra la app (suelen ser muy específicos).
- Verifica los pasos 2, 3 y 4 (son los que más errores generan).
- Consulta la documentación oficial: [Streamlit](https://docs.streamlit.io/) · [gspread](https://docs.gspread.org/).

---

¡Éxitos con tu negocio! 🚀
