"""Mensajes de error en español llano para el usuario de la web.

La API devuelve códigos y detalles técnicos (a veces en inglés, a veces
con rutas, puertos o textos internos). Al usuario solo le llega el mensaje
de aquí: corto, en español y sin detalles internos. El detalle técnico
queda en el registro (logs/django.log), que escribe el cliente de la API.

Reglas:
- 401: la sesión caducó. Quien llama limpia la sesión y redirige a login.
- 403: sin permiso.
- 404: eso ya no existe en la API.
- 502/503/504: la API no pudo hablar con el router o no responde.
- Sin código y fallo de conexión: la API no está corriendo o no responde.
- 400: errores de validación, con el texto ya limpio del cliente.
- Cualquier otra cosa: mensaje genérico, sin exponer nada interno.
"""

import logging

logger = logging.getLogger(__name__)

MENSAJE_SESION_CADUCADA = "Tu sesión caducó. Inicia sesión de nuevo."
MENSAJE_SIN_PERMISO = (
    "No tienes permiso para hacer eso. Si crees que es un error, pide a un "
    "administrador que revise tu usuario en la API."
)
MENSAJE_NO_EXISTE = (
    "Eso ya no existe en la API: puede que se haya eliminado. Vuelve a "
    "cargar la página e inténtalo de nuevo."
)
MENSAJE_ROUTER_SIN_RESPUESTA = (
    "La API no pudo hablar con el router (o la API no responde ahora mismo). "
    "Inténtalo de nuevo en unos minutos; si sigue fallando, revisa que la API "
    "esté corriendo y que el router tenga corriente y red."
)
MENSAJE_API_CAIDA = (
    "No se pudo conectar con la API. Revisa que la API esté corriendo e "
    "inténtalo de nuevo."
)
MENSAJE_API_ERROR = "La API devolvió un error. Inténtalo de nuevo en unos minutos."
MENSAJE_INESPERADO = (
    "Ocurrió un error inesperado. Inténtalo de nuevo y, si sigue pasando, "
    "revisa el registro (logs/django.log)."
)

# Traducciones de los mensajes más habituales de Django REST Framework.
# La API puede devolverlos en inglés; al usuario le llega la versión en
# español. Lo que no está aquí se muestra tal cual (ya viene limpio del
# cliente); nunca se inventa otra cosa.
TRADUCCIONES_DRF = {
    "This field is required.": "Este campo es obligatorio.",
    "This field may not be blank.": "Este campo no puede estar vacío.",
    "This field may not be null.": "Este campo no puede estar vacío.",
    "Enter a valid IP address.": "Ingrese una dirección IP válida.",
    "Enter a valid integer.": "Ingrese un número entero válido.",
    "Enter a number.": "Ingrese un número válido.",
    "A valid integer is required.": "Ingrese un número entero válido.",
    "Unable to log in with provided credentials.": "El usuario o la contraseña son incorrectos.",
    "Invalid token.": "El token no es válido.",
    "Invalid token": "El token no es válido.",
    "Authentication credentials were not provided.": "Faltan las credenciales de autenticación.",
    "Not found.": "No encontrado.",
    'Method "GET" not allowed.': "Esa acción no está permitida.",
    'Method "POST" not allowed.': "Esa acción no está permitida.",
    'Method "PATCH" not allowed.': "Esa acción no está permitida.",
    'Method "DELETE" not allowed.': "Esa acción no está permitida.",
}


def traducir_mensaje_drf(texto):
    """Traduce un mensaje de DRF si se conoce; si no, lo deja tal cual."""
    if not isinstance(texto, str):
        texto = str(texto)
    return TRADUCCIONES_DRF.get(texto.strip(), texto)


def mensaje_usuario(exc):
    """Mensaje en español llano para mostrar al usuario por un error."""
    status_code = getattr(exc, "status_code", None)
    if status_code == 401:
        return MENSAJE_SESION_CADUCADA
    if status_code == 403:
        return MENSAJE_SIN_PERMISO
    if status_code == 404:
        return MENSAJE_NO_EXISTE
    if status_code in (502, 503, 504):
        return MENSAJE_ROUTER_SIN_RESPUESTA
    if status_code == 400:
        texto = str(exc).strip()
        return texto or "Revisa los datos enviados: la API no los aceptó."
    if status_code is not None and status_code >= 500:
        return MENSAJE_API_ERROR
    if status_code is not None:
        # Otros 4xx (405, 409, 422...): el texto ya viene limpio del cliente.
        texto = str(exc).strip()
        return texto or MENSAJE_API_ERROR
    if hasattr(exc, "status_code"):
        # APIError sin código: fallo de conexión o respuesta no JSON.
        texto = str(exc).lower()
        if "conectar" in texto or "autenticar" in texto:
            return MENSAJE_API_CAIDA
        return MENSAJE_API_ERROR
    # No es un error de la API (un fallo propio de la web): genérico.
    return MENSAJE_INESPERADO
