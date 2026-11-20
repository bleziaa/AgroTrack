"""Pruebas de altas administrativas con PostgreSQL; elimina solo sus propios registros."""
import getpass
import psycopg
import hashlib
import json
import os
import secrets
from pathlib import Path
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from app import app, db, MODULES
from psycopg import sql
from psycopg.conninfo import make_conninfo
app.config['TESTING']=True
client=app.test_client()
created=[]
mark='QA-'+secrets.token_hex(8)
pwd=secrets.token_urlsafe(24)
def snapshot():
    with db(True) as c:
        return {t:hashlib.sha256(json.dumps(c.execute(sql.SQL('SELECT * FROM {} ORDER BY id').format(sql.Identifier(t))).fetchall(),sort_keys=True,default=str).encode()).hexdigest() for t in ['rol','usuario']+[m['table'] for m in MODULES.values()]}
before=snapshot()
with db(True) as c:
    uid=c.execute("SELECT u.id FROM usuario u JOIN rol r ON r.id=u.rol_id WHERE u.activo AND r.nombre='administrador' ORDER BY u.id LIMIT 1").fetchone()['id']
with client.session_transaction() as s:s['uid']=uid;s['csrf']=mark
checks=[]
def post(path,**data):return client.post(path,data={'csrf':mark,**data})
def user_data(role):return dict(nombre=mark,correo=mark+'-'+role+'@example.invalid',rol=role,clave=pwd,confirmar_clave=pwd)
def reject(data,message):
    r=post('/usuarios/nuevo',**data)
    assert r.status_code==200 and message in r.get_data(as_text=True),message
try:
    for role in ['administrador','consulta']:
        data=user_data(role)
        assert post('/usuarios/nuevo',**data).status_code==302
        with db(True) as c:
            row=c.execute('SELECT * FROM usuario WHERE correo=%s',(data['correo'].lower(),)).fetchone()
        created.append(('usuario',row['id']))
        assert row['clave_hash']!=pwd and check_password_hash(row['clave_hash'],pwd)
        other=app.test_client();other.get('/login')
        with other.session_transaction() as s:token=s['csrf']
        assert other.post('/login',data={'csrf':token,'correo':data['correo'].upper(),'clave':pwd}).status_code==302
        for path in ['/usuarios','/usuarios/nuevo','/datos/fincas/nuevo','/datos/cultivos/nuevo']:
            assert other.get(path).status_code==(200 if role=='administrador' else 403),path
            if role=='consulta':
                with other.session_transaction() as s:token=s['csrf']
                assert other.post(path,data={'csrf':token}).status_code in [403,405]
        checks.append('Alta e inicio de sesión real: '+role+'; permisos verificados')
    reject(user_data('consulta'),'Ya existe un usuario')
    for patch,msg in [({'nombre':'x'},'nombre debe'),({'correo':'invalido'},'correo válido'),({'rol':'root'},'Selecciona el rol'),({'clave':'corta','confirmar_clave':'corta'},'12 y 128'),({'confirmar_clave':'no coincide'},'no coinciden')]:
        reject({**user_data('consulta'),**patch},msg)
    assert client.post('/usuarios/nuevo',data={'csrf':'incorrecto',**user_data('consulta')}).status_code==400
    checks.append('Rechazo de duplicados, nombre, correo, rol, contraseña, confirmación y CSRF')
    r=post('/datos/productores/nuevo?volver=fincas',documento=mark,nombre=mark,vereda='Prueba temporal')
    assert r.status_code==302 and '/datos/fincas/nuevo?productor_id=' in r.location
    with db(True) as c:pid=c.execute('SELECT id FROM productor WHERE documento=%s',(mark,)).fetchone()['id']
    created.append(('productor',pid))
    assert f'value="{pid}" selected' in client.get(r.location).get_data(as_text=True)
    for path,data,table in [('/datos/fincas/nuevo',dict(productor_id=pid,nombre=mark,ubicacion='Prueba temporal'),'finca'),('/datos/cultivos/nuevo',dict(nombre=mark,variedad='Prueba temporal'),'cultivo')]:
        assert post(path,**data).status_code==302
        with db(True) as c:rid=c.execute(sql.SQL('SELECT id FROM {} WHERE nombre=%s').format(sql.Identifier(table)),(mark,)).fetchone()['id']
        created.append((table,rid))
        assert post(path,**data).status_code==200
        for field in ['nombre']:
            assert 'al menos dos' in post(path,**{**data,field:'x'}).get_data(as_text=True)
        assert 'Completa el campo' in post(path,**{**data,'nombre':'   '}).get_data(as_text=True)
    assert 'registro existente' in post('/datos/fincas/nuevo',productor_id=9223372036854775807,nombre=mark,ubicacion='Prueba').get_data(as_text=True)
    checks.append('Productor → finca con selección automática; alta real de finca y cultivo, duplicados, vacíos y referencia inválida')
    for role in ['administrador','consulta']:
        with db(True) as c:rid=c.execute('SELECT id FROM usuario WHERE correo=%s',(user_data(role)['correo'].lower(),)).fetchone()['id']
        ui=app.test_client()
        with ui.session_transaction() as s:s['uid']=rid;s['csrf']=mark
        html=ui.get('/').get_data(as_text=True)
        assert ('Crear finca' in html)==(role=='administrador')
        assert ('Usuarios y roles' in html)==(role=='administrador')
        assert pwd not in ui.get('/usuarios').get_data(as_text=True)
    checks.append('Accesos visibles según rol y contraseñas ausentes de listados')
finally:
    admin_dsn = os.environ.get('POSTGRES_ADMIN_DSN') or make_conninfo(
        host=str(Path('.pgsocket').resolve()), port=55438, user=getpass.getuser()
    )
    with psycopg.connect(make_conninfo(admin_dsn, dbname='agrotrack')) as c:
        for table,rid in reversed(created):c.execute(sql.SQL('DELETE FROM {} WHERE id=%s').format(sql.Identifier(table)),(rid,))
assert snapshot()==before,'Los registros originales cambiaron'
checks.append('Registros temporales eliminados; contenido original idéntico antes y después (secuencias pueden avanzar)')
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'pruebas':checks,'resultado':'correcto'}
(Path(os.environ.get('AGROTRACK_TEST_REPORT_DIR', 'docs')) / 'verificacion_admin.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
