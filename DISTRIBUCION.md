# AgroTrack para Windows y Linux

1. Descarga el paquete x64 de tu sistema desde Releases y extrae la carpeta completa en una ubicación donde puedas escribir.
2. Ten PostgreSQL iniciado en tu equipo o usa una instancia accesible. En una instalación nueva, el usuario de PostgreSQL debe poder crear la base y el rol técnico. Usa una instancia dedicada si ya existe una base llamada `agrotrack`.
3. En Windows, abre `Iniciar-AgroTrack.cmd`. En Linux, ejecuta `./Iniciar-AgroTrack.sh`.
4. En la primera ejecución escribe el DSN de PostgreSQL cuando aparezca la petición oculta. El formato es `host=127.0.0.1 port=5432 dbname=postgres user=postgres password=TU_CLAVE`.
5. Espera a que se abra el navegador en `http://127.0.0.1:5084`. Inicia sesión con los datos generados en `accesos-locales.txt`. La cuenta de administrador registra las demás cuentas.

El paquete trae Python y sus bibliotecas. PostgreSQL se gestiona por separado y conserva los datos entre versiones. Haz una copia de seguridad antes de mover una instalación. Conserva el archivo privado `.env` y la base de datos. Si usas una base existente, copia su `.env` a la carpeta del paquete antes de iniciarlo. En Linux, extrae con `tar -xzf nombre-del-paquete.tar.gz` para conservar los permisos.

Para diagnosticar, ejecuta `AgroTrack.exe --check` o `./AgroTrack --check`. La comprobación verifica el archivo de configuración, PostgreSQL y el esquema. Si ya existe la base pero se interrumpió la inicialización, revisa su estado con el administrador antes de reintentar. Si no se abre el navegador, usa la URL de la consola.
