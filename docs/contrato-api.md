# Contrato con la API

La web es un cliente puro de `mikrotik-admin-api`: no tiene modelos locales. Esta página lista los endpoints reales que usa, para que el README no prometa recursos que la API no tiene.

Base: `MIKROTIK_API_URL` (por defecto `http://localhost:8000/api`). Autenticación: `Authorization: Token <token>`, guardado en la sesión Django tras `POST /api/token/`.

## Autenticación

| Método | Endpoint | Uso en la web |
|---|---|---|
| `POST` | `/api/token/` | Inicio de sesión web. Devuelve solo `{"token": "..."}` (sin usuario ni rol). |
| `POST` | `/api/token/revocar/` | Cierre de sesión web: revocar el token. Si la API responde 404/405 en esa ruta (una API anterior a ese endpoint), la web solo limpia la sesión local. Como alternativa la web prueba `POST /api/logout/`. Si la API usa otra ruta, se cambia `RUTAS_REVOCACION_TOKEN` en `api_client.py`. |

## Routers

| Método | Endpoint | Uso en la web |
|---|---|---|
| `GET` | `/api/routers/` | Inventario y desplegables. |
| `POST` | `/api/routers/` | Alta de router (nombre, `ip_address`, `puerto_api` por defecto 8729, usuario, contraseña, activo). |
| `GET` | `/api/routers/{id}/` | Detalle del router. |
| `PATCH` | `/api/routers/{id}/` | Edición (la contraseña se omite si está vacía, para conservarla). |
| `DELETE` | `/api/routers/{id}/` | Eliminación. |
| `POST` | `/api/routers/{id}/verificar-conexion/` | Verificación de conexión. |
| `POST` | `/api/routers/{id}/sincronizar/` | Sincronización de ese router. |
| `POST` | `/api/routers/{id}/reparar-colas/` | Reparación de colas de clientes DHCP/IP fija. |
| `GET` | `/api/routers/{id}/consumo/` | Consumo de colas (`router`, `total_colas`, `colas`). |
| `GET` | `/api/routers/{id}/dhcp-leases/` | Leases DHCP. |
| `GET` | `/api/routers/{id}/direcciones-ip/` | Desplegable de `direccion_local` en el formulario de plan. Devuelve `{"direcciones": [{"interfaz", "direccion", "direccion_con_mascara", "red"}]}`; se guarda `direccion` (la IP sin máscara). |
| `GET` | `/api/routers/{id}/pools/` | Desplegable de `pool_remoto` en el formulario de plan. Devuelve `{"pools": [{"nombre", "rangos"}]}`; se guarda `nombre`. |
| `GET` | `/api/routers/{id}/colas/` | Desplegable de `cola_padre` del plan. |

## Planes

| Método | Endpoint | Uso en la web |
|---|---|---|
| `GET` | `/api/planes/` | Listado de planes. |
| `POST` | `/api/planes/` | Alta de plan. |
| `GET` | `/api/planes/{id}/` | Edición de plan. |
| `PATCH` | `/api/planes/{id}/` | Guardado de la edición. |
| `DELETE` | `/api/planes/{id}/` | Eliminación. |

Campos que envía la web: `nombre_perfil`, `subida_mbps`, `bajada_mbps`, `router`, `cola_padre` (desplegable por router; vacío = sin cola padre, la API ya no genera `Plan-{perfil}`), `direccion_local` (desplegable por router; vacía = `null`, la API no toca el local-address del perfil) y `pool_remoto` (desplegable por router; vacío = `""`, la API no toca el remote-address del perfil). La web valida que `direccion_local`, si se pone, sea una IP válida.

## Clientes PPPoE

| Método | Endpoint | Uso en la web |
|---|---|---|
| `GET` | `/api/clientes-pppoe/` | Listado y alta rápida del dashboard. |
| `POST` | `/api/clientes-pppoe/` | Alta (`nombre_completo`, `usuario_pppoe`, `password_pppoe`, `direccion_ip_antena`, `plan`, `router`, `estado`). |
| `GET` | `/api/clientes-pppoe/{id}/` | Edición. |
| `PATCH` | `/api/clientes-pppoe/{id}/` | Guardado (sin `password_pppoe` si se deja vacía, para conservarla). |
| `DELETE` | `/api/clientes-pppoe/{id}/` | Eliminación. |
| `GET` | `/api/clientes-pppoe/activos/` | Conexiones activas. Devuelve `routers` (lista de nombres), `total_conectados`, `conexiones` y `errores` (routers que no se pudieron consultar; el total puede estar incompleto). |
| `POST` | `/api/clientes-pppoe/{id}/cambiar-estado/` | Activación/suspensión, con `{"estado": "activo"}` o `{"estado": "suspendido"}`. |
| `POST` | `/api/clientes-pppoe/{id}/ping/` | Ping desde el router. |
| `POST` | `/api/clientes-pppoe/{id}/patear/` | Desconexión de la sesión. |

## Clientes DHCP / IP fija

| Método | Endpoint | Uso en la web |
|---|---|---|
| `GET` | `/api/clientes-red/` | Listado. |
| `POST` | `/api/clientes-red/` | Alta (nombre, tipo, IP, MAC, plan, router, interfaz, servidor DHCP). |
| `GET` | `/api/clientes-red/{id}/` | Edición. |
| `PATCH` | `/api/clientes-red/{id}/` | Guardado. |
| `DELETE` | `/api/clientes-red/{id}/` | Eliminación. |
| `POST` | `/api/clientes-red/{id}/crear-cola/` | Reparación de reserva y cola. |

## Facturación

| Método | Endpoint | Uso en la web |
|---|---|---|
| `GET/POST` | `/api/facturas/` | Listado y alta. |
| `GET/PATCH/DELETE` | `/api/facturas/{id}/` | Edición y eliminación. |
| `GET/POST` | `/api/pagos/` | Listado y alta. |
| `GET/PATCH/DELETE` | `/api/pagos/{id}/` | Edición y eliminación. |

## Sincronización

| Método | Endpoint | Uso en la web |
|---|---|---|
| `POST` | `/api/routers/{id}/sincronizar/` | Sincronización bidireccional de ese router (desde el dashboard y desde el detalle del router). |

No existen en la API `POST /api/clientes-pppoe/sincronizar/` ni `/importar-desde-mikrotik/`: versiones anteriores de este documento los nombraban y eran incorrectas.

## Endpoints que no existen

- `GET /api/interfaces/` y `GET /api/enlaces-isp/`: no existen en la API. Por eso las páginas "Interfaces" y "Enlaces ISP" se quitaron de la web.

## Errores honestos

Cuando la API devuelve un error en vez de una lista (por ejemplo 502 con el router sin respuesta), la web no muestra una lista vacía ni un 0 como si todo fuera bien:

- Dashboard y conexiones activas: si `GET /api/clientes-pppoe/activos/` falla, el total de conectados muestra "No disponible" y la lista dice que no se pudo consultar; si la API trae `errores`, se listan los routers que no se pudieron consultar y se avisa de que el total puede estar incompleto.
- Formulario de plan: si un catálogo (`colas`, `direcciones-ip`, `pools`) falla, el formulario avisa qué catálogo y de qué router no cargó, y sigue funcionando con ese campo vacío y opcional.
- Consumo y leases del router: si la consulta falla, la tabla dice que no se pudo consultar el router, no "No se encontraron...".
- Listas (clientes, planes, routers, clientes de red, facturas, pagos): si la lista falla, el estado vacío dice que no se pudo consultar, no "No hay...".
- Dashboard: si una lista falla, su tarjeta muestra "—" con "No se pudo consultar", nunca un 0 inventado (lo mismo que ya hacían las sesiones activas).
- Formularios: si fallan, se vuelven a mostrar con los datos enviados (antes editar un cliente PPPoE o crear/editar un cliente de red redirigían y se perdía todo lo escrito).
- Sesión caducada (401): la web limpia la sesión y redirige a login con "Tu sesión caducó. Inicia sesión de nuevo." Un 403 no cierra la sesión.
- Login: el mensaje depende del código, no del texto del error. Un 400 son credenciales incorrectas; la API caída dice que no se pudo conectar; un 500 de la API dice que la API devolvió un error (antes cualquier error se mostraba como "No se pudo conectar", y cualquier 400 como credenciales incorrectas).
- Errores 500 propios de la web y páginas inexistentes (404): páginas amigables `templates/500.html` y `templates/404.html`, con enlace para volver al inicio.

La correspondencia de cada código con su mensaje está en `mikrotik_web_app/errores.py` (`mensaje_usuario()`): 401 sesión caducada, 403 sin permiso, 404 ya no existe, 502/503/504 router sin respuesta, sin código y fallo de conexión API caída, 400 validación en español, 500 error de la API. El detalle técnico nunca llega al usuario: queda en el registro (`logs/django.log`).

## Formato de las respuestas

La API no pagina: devuelve listas planas. El cliente (`get_list`) también acepta la forma paginada `{"results": [...]}`, `{"items": [...]}` o `{"data": [...]}` por si la API pagina en el futuro.
