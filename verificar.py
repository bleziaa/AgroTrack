"""Pruebas de integración sobre PostgreSQL real; no sustituyen validación comunitaria."""
import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import psycopg
from psycopg import sql
from app import app, db, MODULES
from paths import DATA_DIR

app.config['TESTING']=True
root=Path(__file__).resolve().parent
lines=(DATA_DIR/'accesos-locales.txt').read_text(encoding='utf-8').splitlines()
admin_password=lines[lines.index('admin@agrotrack.local')+1]
viewer_password=lines[lines.index('consulta@agrotrack.local')+1]
results=[]
token=secrets.token_hex(5)


def check(name, fn):
    fn()
    results.append({'prueba':name,'resultado':'correcto'})


def csrf(client):
    with client.session_transaction() as sess:
        return sess['csrf']


def login(email,password):
    client=app.test_client()
    assert client.get('/login').status_code==200
    response=client.post('/login',data={'csrf':csrf(client),'correo':email,'clave':password})
    assert response.status_code==302
    return client


admin=login('admin@agrotrack.local',admin_password)
viewer=login('consulta@agrotrack.local',viewer_password)
results.append({'prueba':'Inicio de sesión de ambos roles','resultado':'correcto'})


def permissions():
    assert app.test_client().get('/').status_code==302
    for key in MODULES:
        for path in [f'/datos/{key}/nuevo',f'/datos/{key}/1/editar',f'/datos/{key}/1/eliminar']:
            assert viewer.get(path).status_code==403,path
            assert viewer.post(path,data={'csrf':csrf(viewer)}).status_code==403,path
    assert admin.post('/datos/productores/nuevo',data={'csrf':'inválido'}).status_code==400
    invalid=app.test_client();invalid.get('/login')
    response=invalid.post('/login',data={'csrf':csrf(invalid),'correo':'admin@agrotrack.local','clave':'incorrecta'})
    assert response.status_code==200 and b'no coinciden' in response.data
check('Permisos en servidor, sesión inválida y CSRF',permissions)


def pages():
    for path in ['/','/reportes','/reportes?productor=1','/reportes?formato=csv']:
        assert admin.get(path).status_code==200,path
        assert viewer.get(path).status_code==200,path
    for key in MODULES:
        for path in [f'/datos/{key}',f'/datos/{key}?q=demo',f'/exportar/{key}',f'/datos/{key}/nuevo']:
            assert admin.get(path).status_code==200,path
        assert viewer.get(f'/datos/{key}').status_code==200
check('Pantallas, formularios y exportaciones de todos los módulos',pages)


ids={}
created=[]


def create(key,data):
    table=MODULES[key]['table']
    with db(True) as conn:
        previous=conn.execute(sql.SQL('SELECT COALESCE(max(id),0) AS id FROM {}').format(sql.Identifier(table))).fetchone()['id']
    response=admin.post(f'/datos/{key}/nuevo',data={'csrf':csrf(admin),**data})
    assert response.status_code==302,(key,response.data.decode()[:500])
    with db(True) as conn:
        row=conn.execute(sql.SQL('SELECT * FROM {} WHERE id>%s ORDER BY id DESC LIMIT 1').format(sql.Identifier(table)),(previous,)).fetchone()
    assert row is not None,key
    ids[key]=row['id'];created.append((key,row['id']))
    return row['id']


try:
    create('productores',{'documento':'TEST-'+token,'nombre':'Prueba '+token,'telefono':'0','vereda':'Sector prueba'})
    create('fincas',{'productor_id':ids['productores'],'nombre':'Finca '+token,'ubicacion':'Prueba temporal'})
    create('parcelas',{'finca_id':ids['fincas'],'nombre':'Parcela '+token,'area_ha':'1.001'})
    create('cultivos',{'nombre':'Cultivo prueba','variedad':token})
    create('ciclos',{'parcela_id':ids['parcelas'],'cultivo_id':ids['cultivos'],'fecha_siembra':'2026-01-01','fecha_fin':'','estado':'activo'})
    create('cosechas',{'ciclo_id':ids['ciclos'],'fecha':'2026-11-01','cantidad_kg':'10.001'})
    create('clientes',{'documento':'TEST-C'+token,'nombre':'Cliente '+token,'telefono':'0'})
    create('ventas',{'cliente_id':ids['clientes'],'fecha':'2026-11-01','observacion':'Prueba '+token})
    create('detalles',{'venta_id':ids['ventas'],'cosecha_id':ids['cosechas'],'cantidad_kg':'2.001','precio_kg':'1000.50'})
    create('gastos',{'ciclo_id':ids['ciclos'],'fecha':'2026-11-01','concepto':'Gasto prueba','valor':'100.25'})
    results.append({'prueba':'Inserción real en los diez módulos','resultado':'correcto'})

    def updates():
        for key,rid in created:
            mod=MODULES[key]
            assert admin.get(f'/datos/{key}/{rid}/editar').status_code==200
            with db(True) as conn:
                row=conn.execute(sql.SQL('SELECT * FROM {} WHERE id=%s').format(sql.Identifier(mod['table'])),(rid,)).fetchone()
            data={field['name']:str(row[field['name']]) if row[field['name']] is not None else '' for field in mod['fields']}
            if key=='productores':data['nombre']='Actualizado '+token
            response=admin.post(f'/datos/{key}/{rid}/editar',data={'csrf':csrf(admin),**data})
            assert response.status_code==302,key
        response=admin.get('/datos/productores?q='+token)
        assert ('Actualizado '+token).encode() in response.data
    check('Edición real y lectura posterior en todos los módulos',updates)

    def filtering():
        params=f'ciclo_id={ids["ciclos"]}&desde=2026-11-01&hasta=2026-11-01&q=10.001'
        response=admin.get('/exportar/cosechas?'+params)
        text=response.data.decode('utf-8-sig')
        assert response.status_code==200 and len(text.splitlines())==2,text
        assert '10.001' in text
        assert len(admin.get('/exportar/cosechas?'+params.replace('q=10.001','q=NO_EXISTE')).data.decode('utf-8-sig').splitlines())==1
        assert admin.get('/datos/cosechas?desde=mal').status_code==400
        assert admin.get('/datos/cosechas?ciclo_id=no').status_code==400
    check('Filtros combinados y CSV coincidente',filtering)

    def totals():
        with db(True) as conn:
            row=conn.execute('SELECT * FROM v_resumen_ciclos WHERE id=%s',(ids['ciclos'],)).fetchone()
            stock=conn.execute('SELECT disponible_kg FROM v_existencias WHERE id=%s',(ids['cosechas'],)).fetchone()
            function=conn.execute('SELECT fn_ingresos_ciclo(%s) AS n',(ids['ciclos'],)).fetchone()['n']
        expected=(Decimal('2.001')*Decimal('1000.50')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        assert row['ingresos']==function==expected
        assert row['gastos']==Decimal('100.25')
        assert row['saldo']==expected-Decimal('100.25')
        assert stock['disponible_kg']==Decimal('8.000')
    check('Función SQL, agregados, existencias y saldo',totals)

    def restrictions():
        response=admin.post(f'/datos/productores/{ids["productores"]}/eliminar',data={'csrf':csrf(admin)},follow_redirects=True)
        assert 'relacionado'.encode() in response.data
        response=admin.post('/datos/detalles/nuevo',data={'csrf':csrf(admin),'venta_id':ids['ventas'],'cosecha_id':ids['cosechas'],'cantidad_kg':'20','precio_kg':'1000'},follow_redirects=True)
        # El duplicado puede rechazarse por stock o unicidad; verificar además stock directamente.
        assert response.status_code==200 and ('supera'.encode() in response.data or b'Ya existe' in response.data)
        response=admin.post(f'/datos/cosechas/{ids["cosechas"]}/editar',data={'csrf':csrf(admin),'ciclo_id':ids['ciclos'],'fecha':'2026-11-01','cantidad_kg':'1'},follow_redirects=True)
        assert 'ya vendida'.encode() in response.data
        response=admin.post('/datos/gastos/nuevo',data={'csrf':csrf(admin),'ciclo_id':ids['ciclos'],'fecha':'2026-11-01','concepto':'Negativo','valor':'-1'})
        assert response.status_code==200 and b'positivo' in response.data
        response=admin.post('/datos/ciclos/nuevo',data={'csrf':csrf(admin),'parcela_id':ids['parcelas'],'cultivo_id':ids['cultivos'],'fecha_siembra':'2026-01-01','fecha_fin':'','estado':'activo'})
        assert response.status_code==200 and b'Ya existe' in response.data
        with db() as conn:
            try:
                with conn.transaction():
                    conn.execute('INSERT INTO gasto(ciclo_id,fecha,concepto,valor) VALUES (%s,current_date,%s,-1)',(ids['ciclos'],'Prueba negativa SQL'))
            except psycopg.errors.CheckViolation: pass
            else: raise AssertionError('CHECK no rechazó negativo por SQL')
    check('Protección de dependencias, sobreventa, reducción, negativos y ciclo duplicado',restrictions)

    # Dos ventas compiten por el mismo stock: solo una debe comprometer siete de diez kilos.
    concurrency=[];extra_sales=[];extra_harvest=None
    try:
        with db() as conn:
            extra_harvest=conn.execute('INSERT INTO cosecha(ciclo_id,fecha,cantidad_kg) VALUES (%s,current_date,10) RETURNING id',(ids['ciclos'],)).fetchone()['id']
            for _ in range(2):
                extra_sales.append(conn.execute('INSERT INTO venta(cliente_id,fecha) VALUES (%s,current_date) RETURNING id',(ids['clientes'],)).fetchone()['id'])
        barrier=threading.Barrier(2)
        def sell(vid):
            try:
                with db() as conn:
                    conn.execute("SET LOCAL lock_timeout='10s'")
                    barrier.wait(timeout=10)
                    conn.execute('INSERT INTO detalle_venta(venta_id,cosecha_id,cantidad_kg,precio_kg) VALUES (%s,%s,7,1000)',(vid,extra_harvest))
                concurrency.append('confirmada')
            except psycopg.errors.CheckViolation: concurrency.append('rechazada')
            except Exception as exc: concurrency.append(type(exc).__name__)
        threads=[threading.Thread(target=sell,args=(vid,)) for vid in extra_sales]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        assert sorted(concurrency)==['confirmada','rechazada'],concurrency
        with db(True) as conn:
            assert conn.execute('SELECT disponible_kg FROM v_existencias WHERE id=%s',(extra_harvest,)).fetchone()['disponible_kg']==3
        results.append({'prueba':'Ventas concurrentes sobre la misma cosecha: una confirmada y otra rechazada','resultado':'correcto'})
    finally:
        with db() as conn:
            for vid in extra_sales:
                conn.execute('DELETE FROM detalle_venta WHERE venta_id=%s',(vid,));conn.execute('DELETE FROM venta WHERE id=%s',(vid,))
            if extra_harvest:conn.execute('DELETE FROM cosecha WHERE id=%s',(extra_harvest,))
finally:
    for key,rid in reversed(created):
        response=admin.post(f'/datos/{key}/{rid}/eliminar',data={'csrf':csrf(admin)})
        assert response.status_code==302
        with db(True) as conn:
            assert conn.execute(sql.SQL('SELECT id FROM {} WHERE id=%s').format(sql.Identifier(MODULES[key]['table'])),(rid,)).fetchone() is None

results.append({'prueba':'Eliminación real de registros de prueba respetando dependencias','resultado':'correcto'})
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'entorno':'PostgreSQL real y cliente HTTP de Flask','datos':'Ficticios; pruebas temporales eliminadas','pruebas':results,'alcance':'No acredita validación con una comunidad real ni prueba de producción.'}
(Path(os.environ.get('AGROTRACK_TEST_REPORT_DIR', root / 'docs')) / 'verificacion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
