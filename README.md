# AgroTrack

Primera versión funcional para Base de Datos II: gestión de productores, fincas, parcelas, cultivos, ciclos, cosechas, clientes, ventas, detalles de venta y gastos. Dos roles, filtros combinables, exportación CSV y reportes por ciclo. PostgreSQL + Flask + HTML/CSS, sin servicios externos durante el uso local.

## Ejecución local en Linux

Requiere PostgreSQL con initdb/pg_ctl disponibles en PATH y Python con venv/pip. En la carpeta del proyecto:

```bash
bash start.sh
```

La primera ejecución instala dependencias aisladas e inicializa un clúster privado en .pgdata sobre el puerto 55438. No utiliza ni reinicia el servicio PostgreSQL del sistema. Abre http://127.0.0.1:5084. Los correos y claves generados están en accesos-locales.txt (permisos privados). No se incluyen credenciales en el paquete de código. El archivo .env es privado y contiene la clave de sesión y la conexión técnica. Las siguientes ejecuciones conservan los datos.

Para detener la web, Ctrl+C en su terminal. Para detener exclusivamente el PostgreSQL de este proyecto, desde la carpeta ejecuta `pg_ctl -D "$PWD/.pgdata" stop`. No elimines .pgdata si quieres conservar los registros. No inicies dos copias de la web en el mismo puerto.

La aplicación se enlaza únicamente a 127.0.0.1. Este servidor es para desarrollo y demostración local. Una publicación requiere servidor WSGI, HTTPS, respaldo, gestión de cuentas, limitación de intentos de acceso y revisión operativa. Los administradores pueden crear usuarios con rol administrador o consulta desde Usuarios y roles. No existe recuperación de contraseña.

## Administración

Entra con una cuenta de administrador. En Vista general aparecen Crear finca, Registrar producto / cultivo y Crear usuario. Una finca pertenece a un productor; el formulario permite crearlo y volver con el nuevo productor seleccionado. El catálogo Productos / cultivos permite registrar el nombre y la variedad antes de crear ciclos de siembra. Las cuentas de consulta no pueden modificar datos ni acceder a Usuarios y roles.

## Datos y alcance

Los registros iniciales son ficticios y aparecen como demostración en la interfaz. La comunidad real de San Jacinto sigue pendiente de identificación. No cambiar DEMO_DATA a 0 mientras se sigan usando registros ficticios.

La venta se registra en dos pasos: cabecera en Ventas y líneas en Detalles de venta. Una cabecera sin detalles no suma ingresos. Los detalles se eliminan antes de eliminar la venta; la aplicación protege las dependencias. El saldo mostrado es parcial: ventas registradas menos gastos registrados.

El esquema completo y sus funciones están en sql/schema.sql. La arquitectura, diagrama y normalización están en docs/modelo_relacional.md. La matriz contra la guía oficial y los pendientes del informe están en docs/requisitos_y_entrega.md.

## Comprobación reproducible

Con la instalación inicializada, ejecuta `.venv/bin/python verificar.py`. Las pruebas usan las credenciales locales, comprueban ambos roles, operaciones CRUD, filtros, exportación, totales e integridad. Crean y eliminan registros de prueba y dejan constancia en docs/verificacion.json. Las secuencias pueden avanzar durante intentos rechazados; los identificadores no son contadores de filas.
