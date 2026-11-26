# MikroTik Web

Aplicación web desarrollada con Django para operar la API REST de administración MikroTik PPPoE. La interfaz consume los recursos remotos sin replicar su base de datos de routers, clientes ni planes: no tiene modelos locales (`mikrotik_web_app/models.py` está vacío). La base de datos local solo guarda lo propio de Django (sesiones, admin).

## Funcionalidades

- Dashboard de estado y sesiones PPP activas.
- Alta rápida de clientes desde el dashboard.
- Alta dedicada con validaciones de usuario, contraseña, IP de antena y asociación plan-router.
- Edición de clientes con conservación opcional de la contraseña existente.
- Listado, activación/suspensión, ping, desconexión y eliminación de clientes PPPoE.
- Gestión de clientes DHCP/IP fija (reserva, cola, reparación y eliminación).
- Consulta de planes de velocidad, con la cola padre como desplegable.
- Vista dedicada de conexiones activas.
- Routers: inventario, detalle, verificación de conexión, sincronización, reparación de colas, consumo y leases DHCP.
- Facturas y pagos.
- Sincronización bidireccional con RouterOS (por router).
- Cliente HTTP centralizado (`api_client.py`), configurable; tolera respuestas paginadas con forma `{"results": [...]}` aunque la API no pagina: devuelve listas planas.
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
└── tests/             Pruebas de integración web (51 tests)

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
| `MIKROTIK_API_URL` | `http://localhost:8000/api` en `settings.py` (`http://127.0.0.1:8000/api` en `.env.example`; ambas son la misma máquina) | Base de la API REST |
| `MIKROTIK_API_TIMEOUT` | `5` | Tiempo máximo por petición, en segundos |
| `MIKROTIK_API_TOKEN` | vacío | Token DRF para autenticación `Token ...` |
| `MIKROTIK_API_USERNAME` | vacío | Usuario para solicitar el token a `/api/token/` |
| `MIKROTIK_API_PASSWORD` | vacío | Contraseña para solicitar el token a `/api/token/` |

Si la API y la interfaz se ejecutan en puertos distintos, configure `MIKROTIK_API_URL` con la dirección real. No son necesarios modelos locales para los recursos administrados por la API.

## Autenticación

El inicio de sesión web (`/web/login/`) pide usuario y contraseña a la API (`POST /api/token/`) y guarda el token en la sesión Django; se envía a la API con el esquema `Authorization: Token <token>`. Si hay credenciales en el entorno (`MIKROTIK_API_USERNAME`/`MIKROTIK_API_PASSWORD`), el cliente se reautentica solo una vez al recibir un 401.

Las vistas operativas requieren iniciar sesión en la interfaz: sin token en sesión ni credenciales configuradas, redirigen a `/web/login/`.

El rol que se guarda en sesión es solo informativo: el endpoint de token de la API devuelve solo `{"token": "..."}`, sin usuario ni rol, así que la web siempre guarda `Rol administrado por la API`. Quien aplica los roles (Administrador, Técnico, Solo lectura) es la API; la web no restringe páginas por rol.

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

- Planes: `GET/POST /api/planes/`, con `nombre_perfil`, `subida_mbps`, `bajada_mbps`, `router` y `cola_padre` como desplegable (alimentado por `GET /api/routers/{id}/colas/`; vacío = la API genera `Plan-{perfil}`).
- **Los campos `direccion_local` y `pool_remoto` del plan no están en el formulario web**: solo se pueden poner por la API directamente, en el admin de la API o importándolos con la sincronización desde un perfil ya creado en el router. Es trabajo pendiente de la web, no un error de la API.
- Clientes PPPoE: `GET/POST /api/clientes-pppoe/`, estado, ping y desconexión.
- Clientes DHCP/IP fija: `GET/POST /api/clientes-red/`, con su cola y reparación.
- Routers: CRUD y acciones `verificar-conexion`, `sincronizar`, `reparar-colas`, `consumo` y `dhcp-leases`.
- Facturas y pagos: CRUD.
- Sincronización: `POST /api/routers/{id}/sincronizar/` por router. No existe `POST /api/clientes-pppoe/sincronizar/` ni `/importar-desde-mikrotik/` en la API.

Las páginas "Interfaces" y "Enlaces ISP" se quitaron de la web porque los endpoints `GET /api/interfaces/` y `GET /api/enlaces-isp/` no existen en la API y esas páginas siempre fallaban con 404, y porque no son necesarias para la regla de negocio actual. Si se necesitan después, hay que crear primero esos endpoints en `mikrotik-admin-api` como trabajo aparte; no se crean en este repositorio.

Las respuestas paginadas de Django REST Framework con la forma `{"results": [...]}` también son admitidas por el cliente, aunque la API no pagina y devuelve listas planas.

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

## Problemas conocidos (no corregidos en este cambio)

- El dashboard muestra el nombre del router como "Ninguno": el endpoint `GET /api/clientes-pppoe/activos/` devuelve `routers` (una lista), no `router` ni `router_nombre`, y el dashboard lee esas claves inexistentes. El total de conectados y la lista de sesiones sí se muestran bien.
- La suite tiene 51 tests; 1 fallo preexistente y ajeno a la documentación: `test_create_invoice`, dependiente de la fecha.

## Estructura futura

Las nuevas integraciones deben agregarse en `api_client.py` mediante métodos REST pequeños. Las vistas deben separar la obtención de datos, las acciones POST y los mensajes de usuario. Las nuevas páginas deben extender `layouts/base.html` y reutilizar la barra lateral modular.
