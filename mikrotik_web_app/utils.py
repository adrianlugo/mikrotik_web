from datetime import date
from decimal import Decimal, InvalidOperation
from ipaddress import ip_address
import re


def _related_id(value):
    if isinstance(value, dict):
        return value.get("id") or value.get("pk")
    return value


def _related_form_id(value):
    try:
        return int(_related_id(value))
    except (TypeError, ValueError):
        return None


def _decimal(value):
    try:
        amount = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    return amount


def _pppoe_form_value(data, primary, fallback):
    value = data.get(primary)
    if value in (None, "") and fallback:
        value = data.get(fallback)
    return value or ""


def _pppoe_payload(data, plans=None, require_password=True):
    nombre = str(data.get("nombre_completo", "")).strip()
    usuario = str(_pppoe_form_value(data, "usuario_pppoe", "usuario")).strip().lower()
    password = str(_pppoe_form_value(data, "password_pppoe", "password")).strip()
    ip_antena = str(data.get("direccion_ip_antena", "")).strip()

    if not nombre:
        raise ValueError("Ingrese el nombre completo del cliente.")
    if not re.fullmatch(r"[a-z0-9._-]+", usuario):
        raise ValueError(
            "El usuario PPPoE solo puede contener letras minúsculas, números, puntos, guiones y guiones bajos."
        )
    if (require_password and not password) or (password and len(password) < 6):
        raise ValueError("La contraseña PPPoE debe tener al menos 6 caracteres.")
    if ip_antena:
        try:
            ip_address(ip_antena)
        except ValueError:
            raise ValueError("Ingrese una dirección IP de antena válida.") from None

    try:
        router = int(data["router"])
        plan = int(data["plan"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Seleccione un router y un plan válidos.") from None

    if plans is not None:
        selected_plan = next(
            (item for item in plans if str(item.get("id")) == str(plan)),
            None,
        )
        if selected_plan is None:
            raise ValueError("El plan seleccionado no existe.")
        plan_router = _related_id(selected_plan.get("router"))
        if plan_router is not None and str(plan_router) != str(router):
            raise ValueError("El plan seleccionado pertenece a otro router.")

    payload = {
        "nombre_completo": nombre,
        "usuario_pppoe": usuario,
        **({"password_pppoe": password} if password else {}),
        "plan": plan,
        "router": router,
        "estado": data.get("estado", "activo"),
        "direccion_ip_antena": ip_antena or None,
    }
    if payload["estado"] not in ("activo", "suspendido"):
        raise ValueError("Seleccione un estado válido para el cliente.")
    return payload


def clear_api_session(request):
    for key in (
        "mikrotik_api_token",
        "mikrotik_api_username",
        "mikrotik_api_role",
    ):
        request.session.pop(key, None)
    request.session.modified = True