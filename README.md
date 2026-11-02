# MikroTik Web

Aplicación web desarrollada con Django para operar la API REST de administración MikroTik PPPoE. La interfaz consume los recursos remotos sin replicar su base de datos de routers, clientes ni planes.

## Funcionalidades

- Dashboard de estado y sesiones PPP activas.
- Alta rápida de clientes desde la interfaz web.
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
python manage.py migrate
python manage.py runserver
```

Abra `http://127.0.0.1:8000/`.

## Configuración

Antes de iniciar el servidor se pueden declarar variables de entorno en PowerShell:

```powershell
$env:MIKROTIK_API_URL="http://127.0.0.1:8000/api"
$env:MIKROTIK_API_TIMEOUT="5"
# Opcional, para una API protegida con Bearer Token
$env:MIKROTIK_API_TOKEN="tu-token"
# Opcional, como alternativa a Bearer Token
$env:MIKROTIK_API_USERNAME="usuario"
$env:MIKROTIK_API_PASSWORD="clave"
```

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `MIKROTIK_API_URL` | `http://localhost:8000/api` | Base de la API REST |
| `MIKROTIK_API_TIMEOUT` | `5` | Tiempo máximo por petición, en segundos |
| `MIKROTIK_API_TOKEN` | vacío | Token Bearer opcional |
| `MIKROTIK_API_USERNAME` | vacío | Usuario para autenticación HTTP Basic |
| `MIKROTIK_API_PASSWORD` | vacío | Contraseña para autenticación HTTP Basic |

Si la API y la interfaz se ejecutan en puertos distintos, configure `MIKROTIK_API_URL` con la dirección real. No son necesarios modelos locales para los recursos administrados por la API.

## Rutas web

| Ruta | Función |
|---|---|
| `/` | Dashboard, alta rápida y sesiones activas |
| `/web/clientes/` | Gestión de clientes PPPoE |
| `/web/planes/` | Consulta de planes de velocidad |
| `/web/conexiones/` | Sesiones PPP activas |
| `/web/clientes/sincronizar/` | Acción de sincronización con MikroTik |

Las acciones de estado y eliminación se realizan mediante formularios POST protegidos con CSRF.

## Contrato esperado de la API

La interfaz espera los siguientes recursos REST:

- `GET/POST /api/planes/`
- `GET/POST /api/clientes-pppoe/`
- `GET /api/clientes-pppoe/activos/`
- `POST /api/clientes-pppoe/sincronizar/` o el endpoint compatible `/importar-desde-mikrotik/`
- `POST /api/clientes-pppoe/{id}/cambiar-estado/`
- `DELETE /api/clientes-pppoe/{id}/`
- `GET /api/routers/`

Las respuestas paginadas de Django REST Framework con la forma `{"results": [...]}` también son admitidas.

## Operación

```powershell
python manage.py check
python manage.py test
python manage.py runserver
```

## Estructura futura

Las nuevas integraciones deben agregarse en `api_client.py` mediante métodos REST pequeños. Las vistas deben separar la obtención de datos, las acciones POST y los mensajes de usuario. Las nuevas páginas deben extender `layouts/base.html` y reutilizar la barra lateral modular.
