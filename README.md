# MikroTik Web

Aplicación web desarrollada con Django para operar la API REST de administración MikroTik PPPoE. La interfaz consume los recursos remotos sin replicar su base de datos de routers, clientes ni planes: no tiene modelos locales (`mikrotik_web_app/models.py` está vacío). La base de datos local solo guarda lo propio de Django (sesiones, admin).

## Funcionalidades

- Dashboard de estado y sesiones PPP activas.
- Alta rápida de clientes desde el dashboard.
- Alta dedicada con validaciones de usuario, contraseña, IP de antena y asociación plan-router.
- Edición de clientes con conservación opcional de la contraseña existente.
- Listado, activación/suspensión, ping, desconexión y eliminación de clientes PPPoE.
- Gestión de clientes DHCP/IP fija (reserva, cola, reparación y eliminación).
- Consulta de planes de velocidad, con la cola padre, la dirección local y el pool remoto como desplegables por router.
- Vista dedicada de conexiones activas.
- Routers: inventario, detalle, verificación de conexión, sincronización, reparación de colas, consumo y leases DHCP.
- Facturas y pagos.
- Sincronización bidireccional con RouterOS (por router).
- Cliente HTTP centralizado (`api_client.py`), configurable; lee la primera página de las respuestas paginadas de la API (100 registros por página).
- Mensajes de operación y errores visibles para el usuario.

## Arquitectura

```text
mikrotik_web_app/
├── api_client.py      Cliente HTTP centralizado de la API
├── mixins.py          Normalización, formularios y cliente por petición
├── utils.py           Utilidades de payload y sesión
├── views/             auth_views, dashboard_views, pppoe_views,
│                      network_views, router_views, billing_views
├── urls.py            Rutas públicas de la interfaz web
├── templates/         Plantillas organizadas por dominio
│   ├── layouts/       base.html, _navbar.html, _sidebar.html
│   ├── auth/          login.html
│   ├── pppoe/         index (dashboard), clientes, planes, conexiones
│   ├── network/       clientes_red, routers, router_detalle, router_monitoreo
│   └── billing/       facturas, pagos
└── tests/             Pruebas de integración web (91 tests)

core/
├── settings.py        Configuración Django y variables de API
└── urls.py            Rutas principales del proyecto
```

## Requisitos

- Python 3.12 o 3.13 (Django 6.1.2, ver `requirements.txt`).
- La API MikroTik ejecutándose y accesible por HTTP.
- Dependencias indicadas en `requirements.txt`.

## Instalación

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
# En el .env, genera y pon una DJANGO_SECRET_KEY nueva (ver Configuración)
python manage.py migrate
python manage.py runserver 8001
```

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 8001
```

Abra `http://127.0.0.1:8001/`.

Esto es el uso en local, en su PC. Ver [Despliegue y copia de seguridad](docs/despliegue.md) para la copia de seguridad sencilla y para la opción de producción (gunicorn) cuando haya un servidor; nada de eso es requisito para usar la web así.

La API corre en el puerto 8000 y la web en el 8001: no pueden correr las dos en el mismo puerto en la misma máquina. El `migrate` crea las tablas propias de Django (sesiones y admin); la web no tiene modelos propios que migrar.

## Configuración

Antes de iniciar el servidor se pueden declarar variables de entorno en PowerShell:

```powershell
$env:MIKROTIK_API_URL="http://127.0.0.1:8000/api"
$env:MIKROTIK_API_TIMEOUT="5"
# Opcional: usa directamente un token ya obtenido
$env:MIKROTIK_API_TOKEN="tu-token"
# Opcional: solicita el token automaticamente en /api/token/
$env:MIKROTIK_API_USERNAME="usuario"
$env:MIKROTIK_API_PASSWORD="clave"
```

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `DJANGO_SECRET_KEY` | (sin valor) | Clave secreta de Django. Obligatoria en producción; sin ella la app no arranca con `DEBUG=false`. La clave anterior, que estaba escrita en `settings.py`, debe rotarse: ya está en el historial de Git y hay que considerarla expuesta. Se genera con `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | `false` | Activa el modo depuración. Solo `true` en desarrollo local |
| `DJANGO_ALLOWED_HOSTS` | (vacío; en desarrollo, `127.0.0.1,localhost`) | Dominios permitidos, separados por comas |
| `MIKROTIK_API_URL` | `http://127.0.0.1:8000/api` (igual en `settings.py` y en `.env.example`) | Base de la API REST |
| `MIKROTIK_API_TIMEOUT` | `5` | Tiempo máximo por petición, en segundos |
| `MIKROTIK_API_TOKEN` | vacío | Token DRF para autenticación `Token ...` |
| `MIKROTIK_API_USERNAME` | vacío | Usuario para solicitar el token a `/api/token/` |
| `MIKROTIK_API_PASSWORD` | vacío | Contraseña para solicitar el token a `/api/token/` |

Si la API y la interfaz se ejecutan en puertos distintos, configure `MIKROTIK_API_URL` con la dirección real. No son necesarios modelos locales para los recursos administrados por la API.

## Autenticación

El inicio de sesión web (`/web/login/`) pide usuario y contraseña a la API (`POST /api/token/`) y guarda el token en la sesión Django; se envía a la API con el esquema `Authorization: Token <token>`. Si hay credenciales en el entorno (`MIKROTIK_API_USERNAME`/`MIKROTIK_API_PASSWORD`), el cliente se reautentica solo una vez al recibir un 401.

Las vistas operativas requieren iniciar sesión en la interfaz: sin token en sesión ni credenciales configuradas, redirigen a `/web/login/`.

El rol que se guarda en sesión es solo informativo: el endpoint de token de la API devuelve solo `{"token": "..."}`, sin usuario ni rol, así que la web siempre guarda `Rol administrado por la API`. Quien aplica los roles (Administrador, Técnico, Solo lectura) es la API; la web no restringe páginas por rol.

Al cerrar sesión (`/web/logout/`, POST), la web revoca el token DRF en la API (`POST /api/token/revocar/`, y como alternativa `POST /api/logout/`). Si la API responde 404/405 en esas rutas (una API anterior a ese endpoint), la web solo limpia la sesión local y el cierre de sesión funciona igual. Si la API usa otra ruta, basta con cambiar `RUTAS_REVOCACION_TOKEN` en `api_client.py`.

## Cómo se muestran los errores

La API devuelve todos sus errores en un único formato: `{"error": "<mensaje claro en español>", "codigo": "<clave>"}` (y en los 400 además `"detalles"` por campo). Al usuario solo le llega el mensaje de `error`, corto y en español, sin detalles internos (nada de inglés, rutas, puertos ni trazas: eso queda en el registro, `logs/django.log`). La `codigo` nunca se muestra: es solo para la lógica. La traducción de código a mensaje vive en `mikrotik_web_app/errores.py` (`mensaje_usuario()`); el cliente de la API (`api_client.py`) ya entrega el error limpio y traducido, y las vistas nunca muestran el texto crudo de la excepción.

| Lo que pasa | Qué ve el usuario |
|---|---|
| La API no está corriendo o no responde | "No se pudo conectar con la API. Revisa que la API esté corriendo e inténtalo de nuevo." |
| La API no pudo hablar con el router (502/503/504) | "La API no pudo hablar con el router (o la API no responde ahora mismo). Inténtalo de nuevo en unos minutos; si sigue fallando, revisa que la API esté corriendo y que el router tenga corriente y red." Las listas y contadores muestran "No disponible" / "—", nunca un 0 inventado. |
| Sesión caducada / token inválido (401) | "Tu sesión caducó. Inicia sesión de nuevo." La sesión se limpia y la web redirige a `/web/login/`. |
| Sin permiso (403) | "No tienes permiso para hacer eso. Si crees que es un error, pide a un administrador que revise tu usuario en la API." La sesión se mantiene. |
| Algo que ya no existe (404) | "Eso ya no existe en la API: puede que se haya eliminado. Vuelve a cargar la página e inténtalo de nuevo." |
| Datos no válidos (400) | El error de validación en español, con los detalles por campo de la API para decir qué corregir (por ejemplo "subida_mbps: El valor debe ser mayor o igual que 0."). El formulario se vuelve a mostrar con los datos enviados y dice qué corregir. |
| No se puede eliminar porque hay registros que dependen de él (409) | "No se puede eliminar porque hay registros que dependen de él." |
| Demasiadas peticiones (429) | El texto de la API, que dice cuántos segundos esperar. |
| Reparar colas a medias | Un aviso (no un éxito): "Colas reparadas en parte: X de Y no se pudieron reparar (nombres). Inténtalo de nuevo." Si fallaron todas, la API responde 502 y se muestra el error del router. |
| Error propio de la web (500) o página inexistente (404) | Páginas amigables `templates/500.html` y `templates/404.html`, con un enlace para volver al inicio. |

Además: un valor no numérico en una velocidad, un puerto o un monto ya no se convierte en silencio en 0 (antes un plan con subida "abc" se guardaba en 0 Mbps y una factura con monto "abc" en 0.00); el formulario dice qué corregir antes de enviar nada. Y si un catálogo del formulario de plan falla con 404, el aviso dice que el endpoint no existe en esa versión de la API, no que el router no tenga valores.

## Rutas web

Las rutas de la interfaz cuelgan de `/web/`, salvo el dashboard, que está en `/`.

| Ruta | Función |
|---|---|
| `/` | Dashboard, alta rápida y sesiones activas |
| `/web/login/` | Inicio de sesión con las credenciales de la API |
| `/web/logout/` | Cierre de sesión web (POST) |
| `/web/clientes/` | Gestión de clientes PPPoE |
| `/web/clientes/crear/` | Alta dedicada de clientes PPPoE |
| `/web/clientes/<id>/editar/` | Edición de clientes PPPoE |
| `/web/clientes/<id>/estado/` | Activación o suspensión de clientes PPPoE (POST) |
| `/web/clientes/<id>/ping/` | Ping desde el router (POST) |
| `/web/clientes/<id>/patear/` | Desconexión de la sesión (POST) |
| `/web/clientes/<id>/eliminar/` | Eliminación de clientes PPPoE (POST) |
| `/web/clientes/sincronizar/` | Sincronización con MikroTik del router elegido (POST) |
| `/web/clientes-red/` | Gestión de clientes DHCP/IP fija |
| `/web/clientes-red/crear/` | Alta de clientes DHCP/IP fija |
| `/web/clientes-red/<id>/editar/` | Edición de clientes DHCP/IP fija |
| `/web/clientes-red/<id>/reparar-cola/` | Reparación de reserva y cola (POST) |
| `/web/clientes-red/<id>/eliminar/` | Eliminación de clientes DHCP/IP fija (POST) |
| `/web/planes/` | Consulta de planes de velocidad |
| `/web/planes/crear/` | Alta de planes de velocidad |
| `/web/planes/<id>/editar/` | Edición de planes de velocidad |
| `/web/planes/<id>/eliminar/` | Eliminación de planes (POST) |
| `/web/conexiones/` | Sesiones PPP activas |
| `/web/routers/` | Inventario de routers MikroTik |
| `/web/routers/crear/` | Alta de routers |
| `/web/routers/<id>/` | Detalle del router |
| `/web/routers/<id>/editar/` | Edición de routers |
| `/web/routers/<id>/eliminar/` | Eliminación de routers (POST) |
| `/web/routers/<id>/verificar/` | Verificación de conexión (POST) |
| `/web/routers/<id>/sincronizar/` | Sincronización de ese router (POST) |
| `/web/routers/<id>/reparar-colas/` | Reparación de colas (POST) |
| `/web/routers/<id>/consumo/` | Consumo de colas del router |
| `/web/routers/<id>/leases/` | Leases DHCP del router |
| `/web/facturas/` | Historial de recibos |
| `/web/facturas/crear/` | Alta de facturas |
| `/web/facturas/<id>/editar/` | Edición de facturas |
| `/web/facturas/<id>/eliminar/` | Eliminación de facturas (POST) |
| `/web/pagos/` | Control de caja |
| `/web/pagos/crear/` | Alta de pagos |
| `/web/pagos/<id>/editar/` | Edición de pagos |
| `/web/pagos/<id>/eliminar/` | Eliminación de pagos (POST) |

Las acciones de estado y eliminación se realizan mediante formularios POST protegidos con CSRF.

## Contrato con la API

Ver [Contrato con la API](docs/contrato-api.md) para la lista completa de endpoints que consume la web, con sus campos.

Resumen:

- Planes: `GET/POST /api/planes/`, con `nombre_perfil`, `subida_mbps`, `bajada_mbps`, `router`, `cola_padre`, `direccion_local` y `pool_remoto`. Los tres últimos son desplegables por router: `cola_padre` por `GET /api/routers/{id}/colas/`, `direccion_local` por `GET /api/routers/{id}/direcciones-ip/` (se guarda la IP, no la interfaz) y `pool_remoto` por `GET /api/routers/{id}/pools/` (se guarda el nombre del pool). Los tres son opcionales: vacíos, `cola_padre` deja el plan sin cola padre (la API ya no genera `Plan-{perfil}`), y `direccion_local`/`pool_remoto` hacen que la API no toque el valor que ya tenga el perfil. Si un catálogo falla (por ejemplo 502 con el router sin respuesta), el formulario avisa y sigue funcionando con ese campo vacío.
- Clientes PPPoE: `GET/POST /api/clientes-pppoe/`, estado, ping y desconexión.
- Clientes DHCP/IP fija: `GET/POST /api/clientes-red/`, con su cola y reparación.
- Routers: CRUD y acciones `verificar-conexion`, `sincronizar`, `reparar-colas`, `consumo` y `dhcp-leases`.
- Facturas y pagos: CRUD.
- Sincronización: `POST /api/routers/{id}/sincronizar/` por router. No existe `POST /api/clientes-pppoe/sincronizar/` ni `/importar-desde-mikrotik/` en la API.

Las páginas "Interfaces" y "Enlaces ISP" se quitaron de la web porque los endpoints `GET /api/interfaces/` y `GET /api/enlaces-isp/` no existen en la API y esas páginas siempre fallaban con 404, y porque no son necesarias para la regla de negocio actual. Si se necesitan después, hay que crear primero esos endpoints en `mikrotik-admin-api` como trabajo aparte; no se crean en este repositorio.

La API pagina con 100 registros por página y la web lee solo la primera página: con más de 100 registros en un listado, solo se ven los 100 primeros.

### Alta y edición PPPoE

El alta y la edición web validan:

- Nombre completo requerido.
- Usuario PPPoE en minúsculas, con letras, números, punto, guion o guion bajo.
- Contraseña de al menos seis caracteres.
- Dirección IP de antena válida cuando se proporciona.
- Plan existente asociado al router seleccionado.
- Estado `activo` o `suspendido`.

El cambio de estado de un cliente requiere enviar explícitamente el nuevo estado:

```json
{"estado": "suspendido"}
```

En edición se puede omitir `password_pppoe` para conservar la contraseña almacenada en la API. Consulte [Operación PPPoE](docs/pppoe.md) para los casos resueltos y las pruebas.

## Operación

```bash
python manage.py check
python manage.py test
python manage.py runserver 8001
```

`runserver` es el uso normal en la PC (ver [Despliegue y copia de seguridad](docs/despliegue.md)): la web corre en local en el puerto 8001 y no hace falta montar un servidor. Ese documento explica también la copia de seguridad sencilla (copiar `db.sqlite3` y guardar el `.env` aparte) y, como opción para cuando haya un servidor, cómo levantarla con gunicorn (`collectstatic` incluido) en vez de runserver.

## Problemas conocidos (no corregidos en este cambio)

- La suite pasa a 91 tests (28 nuevos de errores en `mikrotik_web_app/tests/test_errores.py` y `test_errores_api6.py`); 1 fallo preexistente y ajeno a este cambio: `test_create_invoice`, dependiente de la fecha (también falla en main). El workflow de CI (`check` + tests en cada PR) sale en rojo por ese test hasta que se arregle aparte. Este cambio no se pudo verificar por ejecución en local por control de riesgo: hay que correr `manage.py check` y `manage.py test` antes de mezclar.
- La cola padre: desde la API, elegir una cola existente ya no toca su límite y vacío es sin cola padre (ya no se auto-genera `Plan-{perfil}`). Falta decidir el total del proveedor y si hay una cola global o una por plan.
- Si varias listas del dashboard fallan a la vez, el mismo mensaje de error se repite una vez por lista (no se deduplica).
- `get_list()` devuelve `[]` en silencio si la API trae una respuesta con una forma inesperada (ni lista ni `{"results"/"items"/"data": [...]}`): en ese caso la página diría "No hay..." sin avisar de que la respuesta no se entendió.
- El alta rápida del dashboard (`DashboardIndexView.post`) no tiene formulario en las plantillas y al fallar redirige perdiendo la selección: es código heredado sin uso visible.
- Todo se validó con mocks, nunca contra un router real con clientes de verdad.

## Estructura futura

Las nuevas integraciones deben agregarse en `api_client.py` mediante métodos REST pequeños. Las vistas deben separar la obtención de datos, las acciones POST y los mensajes de usuario. Las nuevas páginas deben extender `layouts/base.html` y reutilizar la barra lateral modular.
