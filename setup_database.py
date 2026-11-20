"""Inicialización no destructiva sobre el clúster local privado de AgroTrack."""
import getpass
import os
import secrets
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from werkzeug.security import generate_password_hash

from paths import DATA_DIR, RESOURCES

def initialize(*, local=False):
    if hasattr(os, "umask"):
        os.umask(0o077)
    if (DATA_DIR/'.env').exists():
        raise SystemExit('Ya existe .env. Se conserva la configuración y no se reinicializa la base.')
    admin = os.environ.get('POSTGRES_ADMIN_DSN', '').strip()
    if local and not admin:
        admin = make_conninfo(host=str(DATA_DIR / '.pgsocket'), port=55438, dbname='postgres',
                              user=getpass.getuser())
    if not admin:
        admin = getpass.getpass('DSN de administrador PostgreSQL (entrada oculta): ').strip()
        if not admin:
            raise SystemExit('Falta el DSN de administrador PostgreSQL.')
    with psycopg.connect(admin, autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname='agrotrack'").fetchone():
            raise SystemExit('La base agrotrack ya existe; se requiere revisión manual. No se modifica.')
        conn.execute('CREATE DATABASE agrotrack')
    owner = make_conninfo(admin, dbname='agrotrack')
    admin_password=secrets.token_urlsafe(15)
    viewer_password=secrets.token_urlsafe(15)
    runtime_password=secrets.token_urlsafe(36)
    with psycopg.connect(owner) as conn:
        conn.execute((RESOURCES/'sql/schema.sql').read_text(encoding='utf-8'),prepare=False)
        conn.execute("INSERT INTO rol(nombre) VALUES ('administrador'),('consulta')")
        conn.execute("INSERT INTO usuario(rol_id,nombre,correo,clave_hash) VALUES (1,'Administrador AgroTrack','admin@agrotrack.local',%s),(2,'Consulta AgroTrack','consulta@agrotrack.local',%s)",(generate_password_hash(admin_password),generate_password_hash(viewer_password)))
        conn.execute("INSERT INTO productor(documento,nombre,telefono,vereda) VALUES ('DEMO-001','Productor demo A','0000000000','Sector de demostración A'),('DEMO-002','Productor demo B','0000000000','Sector de demostración B')")
        conn.execute("INSERT INTO finca(productor_id,nombre,ubicacion) VALUES (1,'Finca demo A','Ubicación ficticia para pruebas'),(2,'Finca demo B','Ubicación ficticia para pruebas')")
        conn.execute("INSERT INTO parcela(finca_id,nombre,area_ha) VALUES (1,'Parcela norte',1.5),(1,'Parcela sur',0.8),(2,'Parcela central',2.2)")
        conn.execute("INSERT INTO cultivo(nombre,variedad) VALUES ('Maíz','Amarillo demo'),('Yuca','Variedad demo'),('Ñame','Variedad demo')")
        conn.execute("INSERT INTO ciclo(parcela_id,cultivo_id,usuario_id,fecha_siembra,fecha_fin,estado) VALUES (1,1,1,'2026-07-01',NULL,'activo'),(2,2,1,'2026-03-01','2026-11-01','finalizado'),(3,3,1,'2026-09-15',NULL,'activo')")
        conn.execute("INSERT INTO cosecha(ciclo_id,fecha,cantidad_kg) VALUES (1,'2026-11-10',1200),(1,'2026-11-12',800),(2,'2026-10-25',2500),(3,'2026-11-15',400)")
        conn.execute("INSERT INTO cliente(documento,nombre,telefono) VALUES ('DEMO-C01','Comprador demo A','0000000000'),('DEMO-C02','Comprador demo B','0000000000')")
        conn.execute("INSERT INTO venta(cliente_id,fecha,observacion) VALUES (1,'2026-11-12','Venta ficticia de demostración'),(2,'2026-11-14','Venta ficticia de demostración')")
        conn.execute("INSERT INTO detalle_venta(venta_id,cosecha_id,cantidad_kg,precio_kg) VALUES (1,1,600,1800),(1,3,1000,2200),(2,2,300,1900)")
        conn.execute("INSERT INTO gasto(ciclo_id,fecha,concepto,valor) VALUES (1,'2026-07-01','Semillas (demo)',150000),(1,'2026-08-01','Jornada de trabajo (demo)',250000),(2,'2026-03-01','Insumos (demo)',600000),(3,'2026-09-15','Siembra (demo)',180000)")
        # Usuario técnico sin permisos de administración del esquema.
        conn.execute(sql.SQL('CREATE ROLE agrotrack_runtime LOGIN PASSWORD {}').format(sql.Literal(runtime_password)))
        conn.execute('GRANT CONNECT ON DATABASE agrotrack TO agrotrack_runtime')
        conn.execute('GRANT USAGE ON SCHEMA public TO agrotrack_runtime')
        conn.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO agrotrack_runtime')
        conn.execute('GRANT INSERT,UPDATE,DELETE ON productor,finca,parcela,cultivo,ciclo,cosecha,cliente,venta,detalle_venta,gasto TO agrotrack_runtime')
        conn.execute('GRANT INSERT ON usuario TO agrotrack_runtime')
        conn.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO agrotrack_runtime')
    settings=conninfo_to_dict(admin)
    dsn=make_conninfo(host=settings.get('host','127.0.0.1'),port=settings.get('port','5432'),dbname='agrotrack',user='agrotrack_runtime',password=runtime_password)
    if local:
        dsn=make_conninfo(dsn, host='127.0.0.1')
    (DATA_DIR/'.env').write_text('DATABASE_URL='+dsn+'\nSECRET_KEY='+secrets.token_hex(32)+'\nDEMO_DATA=1\nPORT=5084\n', encoding='utf-8')
    (DATA_DIR/'accesos-locales.txt').write_text('AgroTrack: http://127.0.0.1:5084\n\nAdministrador\nadmin@agrotrack.local\n'+admin_password+'\n\nSolo consulta\nconsulta@agrotrack.local\n'+viewer_password+'\n\nDatos ficticios. No reutilizar estas claves fuera de esta instalación.\n', encoding='utf-8')
    print('Inicialización completada con datos ficticios. Accesos en accesos-locales.txt.')
