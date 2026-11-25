# MikroTik Web

Aplicación web desarrollada con Django para operar la API REST de administración MikroTik PPPoE. La interfaz consume los recursos remotos sin replicar su base de datos de routers, clientes ni planes.

## Funcionalidades

- Dashboard de estado y sesiones PPP activas.
- Alta rápida de clientes desde la interfaz web.
- Alta dedicada con validaciones de usuario, contraseña, IP de antena y asociación plan-router.
- Edición de clientes con conservación opcional de la contraseña existente.
- Listado, activación/suspensión y eliminación de clientes.
- Sincronización bidireccional con RouterOS.
- Consulta de planes de velocidad.
- Vista dedicada de conexiones activas.
- Cliente HTTP centralizado, configurable y preparado para paginación DRF.
- Mensajes de operación y errores visibles para el usuario.

## Arquitectura

```text
mikrotik_web_app/
├── api_client.py      Cliente HTTP centralizado de la API
├── views.py           Orquestación y presentación
├── urls.py            Rutas públicas de la interfaz web
├── templates/         Plantillas organizadas por dominio
└── tests.py           Pruebas de integración web

core/
├── settings.py        Configuración Django y variables de API
└── urls.py            Rutas principales del proyecto
```

## Requisitos

- Python 3.13.
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

Abra `http://127.0.0.1:8001/`.

La API corre en el puerto 8000 y la web en el 8001: no pueden correr las dos
en el mismo puerto en la misma máquina.

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
| `MIKROTIK_API_URL` | `http://localhost:8000/api` | Base de la API REST |
| `MIKROTIK_API_TIMEOUT` | `5` | Tiempo máximo por petición, en segundos |
| `MIKROTIK_API_TOKEN` | vacío | Token DRF para autenticación `Token ...` |
| `MIKROTIK_API_USERNAME` | vacío | Usuario para solicitar el token a `/api/token/` |
| `MIKROTIK_API_PASSWORD` | vacío | Contraseña para solicitar el token a `/api/token/` |

Si la API y la interfaz se ejecutan en puertos distintos, configure `MIKROTIK_API_URL` con la dirección real. No son necesarios modelos locales para los recursos administrados por la API.

## Rutas web

| Ruta | Función |
|---|---|
| `/web/login/` | Inicio de sesión con las credenciales de la API |
| `/web/logout/` | Cierre de sesión web |
| `/` | Dashboard, alta rápida y sesiones activas |
| `/web/clientes/` | Gestión de clientes PPPoE |
| `/web/clientes/crear/` | Alta dedicada de clientes PPPoE |
| `/web/clientes/<id>/editar/` | Edición de clientes PPPoE |
| `/web/clientes/<id>/estado/` | Activación o suspensión de clientes PPPoE |
| `/web/planes/` | Consulta de planes de velocidad |
| `/web/conexiones/` | Sesiones PPP activas |
| `/web/routers/` | Inventario de routers MikroTik |
| `/web/clientes/sincronizar/` | Acción de sincronización con MikroTik |

Las acciones de estado y eliminación se realizan mediante formularios POST protegidos con CSRF.
Las vistas operativas requieren iniciar sesión en la interfaz. El token obtenido se guarda en la sesión Django y se envía a la API con el esquema `Authorization: Token <token>`.

## Contrato esperado de la API

La interfaz espera los siguientes recursos REST:

- `GET/POST /api/planes/`
- `GET/POST /api/clientes-pppoe/`
- `GET /api/clientes-pppoe/activos/`
- `POST /api/clientes-pppoe/sincronizar/` o el endpoint compatible `/importar-desde-mikrotik/`
- `POST /api/clientes-pppoe/{id}/cambiar-estado/`
- `DELETE /api/clientes-pppoe/{id}/`
- `GET /api/routers/`

Las páginas "Interfaces" y "Enlaces ISP" se quitaron de la web porque los
endpoints `GET /api/interfaces/` y `GET /api/enlaces-isp/` no existen en la
API y esas páginas siempre fallaban con 404, y porque no son necesarias para
la regla de negocio actual. Si se necesitan después, hay que crear primero
esos endpoints en `mikrotik-admin-api` como trabajo aparte; no se crean en
este repositorio.

Las respuestas paginadas de Django REST Framework con la forma `{"results": [...]}` también son admitidas.

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

```powershell
python manage.py check
python manage.py test
python manage.py runserver 8001
```

## Estructura futura

Las nuevas integraciones deben agregarse en `api_client.py` mediante métodos REST pequeños. Las vistas deben separar la obtención de datos, las acciones POST y los mensajes de usuario. Las nuevas páginas deben extender `layouts/base.html` y reutilizar la barra lateral modular.
