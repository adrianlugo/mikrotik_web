# Despliegue y copia de seguridad

Esta web hoy corre **en la PC de Adrián, en local**, con la API en el puerto
8000 y la web en el 8001. No hay un servidor dedicado ni hace falta montarlo
para usarla: lo de abajo distingue qué es el uso normal en su PC y qué sería
el paso a producción **cuando** monte un servidor, como opción, no como
obligación.

## En su PC (uso normal, desarrollo y uso interno)

Es lo que se hace hoy; nada de esto cambia:

```bash
python -m venv venv
# Windows PowerShell: .\venv\Scripts\Activate.ps1
# Linux/macOS: source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# En el .env, pon una DJANGO_SECRET_KEY nueva (ver Configuración en el README)
python manage.py migrate
python manage.py runserver 8001
```

Abrir `http://127.0.0.1:8001/`. La API corre en el puerto 8000 y la web en el
8001: no pueden correr las dos en el mismo puerto en la misma máquina.

- `runserver` es solo para uso local: sirve los archivos estáticos y se
  reinicia solo, pero no es un servidor de producción (un solo proceso, sin
  tolerancia a fallos). Para usar la web en su PC es suficiente.
- No hace falta ejecutar `collectstatic` en local.
- Los registros (logs) quedan en `logs/django.log` además de en la consola,
  para revisar qué pasó sin tener la terminal delante.
- La base de datos sigue siendo SQLite por defecto (`db.sqlite3`). No se
  cambió: pasar a PostgreSQL u otra base sería una decisión aparte, cuando
  haya un servidor.

## Copia de seguridad (en su PC, lo sencillo primero)

La web casi no guarda datos propios: su base local solo tiene lo de Django
(sesiones y admin). Los datos de verdad (routers, clientes, planes,
facturas) viven en la API, no aquí. Por eso la copia de la web es simple:

1. **Lo primero y suficiente:** copiar el archivo `db.sqlite3` a otra
   carpeta, un USB o un disco externo, de vez en cuando (por ejemplo, una
   vez por semana o antes de un cambio grande). Con eso basta para
   recuperar las sesiones y el admin de la web.
2. **El `.env` aparte:** guarda una copia del `.env` fuera del repositorio
   (nunca se sube a Git). Sin él se pierde la `DJANGO_SECRET_KEY` y las
   credenciales de la API, y habría que generarlas de nuevo.
3. **Lo importante de verdad está en la API:** la copia que no puede
   faltar es la de `mikrotik-admin-api` (su base de datos y su `.env`).
   Esa copia se explica en la documentación de la API, no aquí.

Para restaurar la web: copiar de vuelta el `db.sqlite3` guardado y el
`.env`, y arrancar como siempre.

## Producción (opcional, solo cuando monte un servidor)

Nada de esto es requisito para seguir usando la web en su PC. Es el camino
cuando haya un servidor (Linux) dedicado:

1. Instalar dependencias con `pip install -r requirements.txt` (ya incluye
   `gunicorn`, el servidor de producción).
2. En el `.env`: `DJANGO_DEBUG=false`, una `DJANGO_SECRET_KEY` nueva y
   `DJANGO_ALLOWED_HOSTS` con el dominio o IP del servidor.
3. `python manage.py migrate` y `python manage.py collectstatic` (esto
   último junta los archivos estáticos en `staticfiles/`, porque gunicorn
   no los sirve solo).
4. Levantar la web con gunicorn en el puerto 8001:
   ```bash
   gunicorn core.wsgi:application --bind 127.0.0.1:8001 --workers 2
   ```
5. Opcional, si el servidor queda expuesto a la red: un proxy inverso
   (nginx) delante de gunicorn para servir los estáticos y el HTTPS, y un
   servicio `systemd` para que la web arranque sola al encender el
   servidor. Docker es otra alternativa para empaquetar todo esto, pero no
   hay `Dockerfile` en este repositorio: sería trabajo aparte y no es
   necesario para el uso en local.

## Qué sigue sin estar listo para producción

Ver el README ("Problemas conocidos"): entre otras cosas, la cola padre
capa el total del plan a la velocidad del plan, la seguridad depende de
pasos manuales sin hacer en el servidor (rotar `SECRET_KEY`, cifrar
credenciales) y no se ha probado nunca contra un router real con clientes
de verdad (todo se validó con mocks). Este PR no pretende dejarlo "listo
para producción": deja la web mejor preparada y documentada, sin imponer
una infraestructura que hoy no existe.
