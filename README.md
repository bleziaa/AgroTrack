# AgroTrack

Sistema web local para administrar la operación de una unidad agrícola. Registra productores, fincas, parcelas, productos y cultivos, ciclos de siembra, cosechas, clientes, ventas, detalles de venta y gastos. Incluye roles de administrador y consulta, filtros, exportación CSV y reportes por ciclo.

## Tecnologías y arquitectura

- Python 3 con Flask y plantillas Jinja.
- PostgreSQL como base de datos relacional.
- Psycopg 3 para consultas parametrizadas y transacciones.
- CSS para la interfaz web.
- Waitress para servir la aplicación local empaquetada.
- PyInstaller para distribuir una aplicación con el runtime de Python incluido.

El navegador muestra la interfaz y Flask procesa rutas, autenticación, permisos, validaciones y operaciones CRUD. PostgreSQL guarda los registros y aplica las relaciones e integridad del esquema. La instalación desde código en Linux puede iniciar un clúster privado del proyecto. Los paquetes descargables requieren PostgreSQL instalado o accesible.

## Funcionalidades principales

- Inicio de sesión con roles de administrador y consulta.
- Administración de productores, usuarios, fincas, parcelas, cultivos, ciclos, cosechas, clientes, ventas, detalles y gastos.
- Búsqueda y filtros combinables, reportes por ciclo y exportación CSV.
- Protección contra modificaciones por cuentas de consulta y respeto de las dependencias de la base de datos.
- Datos demostrativos ficticios claramente identificados.

## Ejecución desde el código fuente en Linux

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

## Ejecutables para Windows y Linux

Descarga la aplicación autocontenida desde [GitHub Releases](https://github.com/bleziaa/AgroTrack/releases/tag/cross-v0.1.0). Se incluye Python, pero se necesita PostgreSQL en ejecución. La configuración inicial solicita un DSN de administración, crea la base y genera credenciales locales. La instalación desde código fuente en Linux puede iniciar un clúster privado del proyecto.

Consulta [la guía de distribución](DISTRIBUCION.md).

