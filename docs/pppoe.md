# Operación PPPoE

## Flujo integrado

1. Seleccionar el router.
2. Seleccionar un plan asociado al mismo router.
3. Registrar usuario, contraseña, nombre, estado y IP opcional de la antena.
4. Crear o actualizar el cliente mediante `/api/clientes-pppoe/`.
5. Consultar, activar, suspender, hacer ping o patear la sesión desde el listado.

## Contrato enviado a la API

Alta:

```json
{
  "nombre_completo": "Cliente Ejemplo",
  "usuario_pppoe": "cliente.ejemplo",
  "password_pppoe": "secreto123",
  "direccion_ip_antena": "192.168.50.10",
  "plan": 2,
  "router": 3,
  "estado": "activo"
}
```

Edición sin cambio de contraseña:

```json
{
  "nombre_completo": "Cliente Ejemplo",
  "usuario_pppoe": "cliente.ejemplo",
  "direccion_ip_antena": "192.168.50.10",
  "plan": 2,
  "router": 3,
  "estado": "activo"
}
```

Cambio de estado:

```json
{"estado": "suspendido"}
```

## Validaciones

- El usuario normalizado debe coincidir con `^[a-z0-9._-]+$`.
- La contraseña nueva debe tener al menos seis caracteres.
- La IP de antena, cuando existe, debe ser una dirección IPv4 o IPv6 válida.
- El plan y el router se validan juntos antes de enviar la petición.
- La contraseña no se incluye al editar si el campo se deja vacío.

## Problemas resueltos

| Evidencia | Corrección aplicada |
|---|---|
| El botón de estado enviaba únicamente la ruta, sin consultar el estado actual ni el payload requerido. | Se consulta el cliente y se envía `{"estado": "activo"}` o `{"estado": "suspendido"}`. |
| La edición exigía contraseña porque reutilizaba el constructor de alta. | Se añadió una opción de contraseña requerida únicamente al crear. |
| Los planes podían aparecer asociados a un router incorrecto. | La selección web muestra, filtra y valida planes por el router elegido. |
| Las respuestas de API podían representar routers y planes como objetos o identificadores. | La normalización resuelve relaciones `{id: ...}` a su identificador. |
| La validación de edición podía perder la IP de antena. | Se añadió el campo al formulario y al payload. |

## Verificación

```powershell
python manage.py test mikrotik_web_app
python manage.py check
python manage.py makemigrations --check --dry-run
```
