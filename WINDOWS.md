# AgroTrack en Windows 10/11

Requiere Python 3.11+ y PostgreSQL 15+ con el servidor iniciado. No necesita WSL ni Bash.
Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-windows.ps1
```

La primera ejecución solicita la cadena de conexión administrativa PostgreSQL (por ejemplo `host=localhost port=5432 dbname=postgres user=postgres password=...`) para crear **una base nueva** `agrotrack`, el usuario técnico y las cuentas de demostración. No modifica bases preexistentes: si ya existe `agrotrack`, se detiene y exige revisión manual. La contraseña se solicita localmente y no se guarda en el repositorio. Después abre http://127.0.0.1:5084 y consulta `accesos-locales.txt` (privado).

Para las ejecuciones posteriores basta correr el mismo archivo; reutiliza la configuración y los datos. Para detener, Ctrl+C. PostgreSQL es un servicio separado y no se apaga automáticamente.

**Seguridad:** ejecución local de demostración en 127.0.0.1, no adecuada para publicar sin HTTPS/servidor WSGI y controles de acceso. No subas `.env` ni `accesos-locales.txt`. Si se interrumpe el primer inicio después de crear la base y antes de escribir `.env`, detente y revisa manualmente; no elimines la base sin respaldo.
