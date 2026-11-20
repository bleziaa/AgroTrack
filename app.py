import csv
import hmac
import io
import os
import re
import secrets
import sys
import webbrowser
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps
from threading import Timer

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash


from paths import DATA_DIR

def load_env():
    p = DATA_DIR / '.env'
    if p.exists():
        for line in p.read_text(encoding='utf-8-sig').splitlines():
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)


load_env()
app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY'), SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('HTTPS') == '1',
                  MAX_CONTENT_LENGTH=128 * 1024)


@contextmanager
def db(readonly=False):
    with psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row) as conn:
        if readonly:
            conn.execute('SET TRANSACTION READ ONLY')
        yield conn


def f(name, label, kind='text', **kwargs):
    return dict(name=name, label=label, kind=kind, required=True, **kwargs)


PROD = 'SELECT id,nombre AS label FROM productor ORDER BY nombre'
FINCA = "SELECT f.id,p.nombre||' / '||f.nombre AS label FROM finca f JOIN productor p ON p.id=f.productor_id ORDER BY label"
PARCELA = "SELECT p.id,f.nombre||' / '||p.nombre AS label FROM parcela p JOIN finca f ON f.id=p.finca_id ORDER BY label"
CULTIVO = "SELECT id,nombre||' · '||variedad AS label FROM cultivo ORDER BY label"
CICLO = "SELECT c.id,'#'||c.id||' · '||cu.nombre||' / '||p.nombre AS label FROM ciclo c JOIN cultivo cu ON cu.id=c.cultivo_id JOIN parcela p ON p.id=c.parcela_id ORDER BY c.id DESC"
COSECHA = "SELECT h.id,'#'||h.id||' · ciclo '||h.ciclo_id||' · '||h.cantidad_kg||' kg' AS label FROM cosecha h ORDER BY h.id DESC"
CLIENTE = 'SELECT id,nombre AS label FROM cliente ORDER BY nombre'
VENTA = "SELECT v.id,'#'||v.id||' · '||c.nombre||' · '||v.fecha AS label FROM venta v JOIN cliente c ON c.id=v.cliente_id ORDER BY v.id DESC"


MODULES = {
 'productores': dict(table='productor', title='Productores', singular='productor', icon='01', description='Personas que cultivan y sostienen la comunidad.', fields=[f('documento','Documento',maxlen=25),f('nombre','Nombre completo',maxlen=120),f('telefono','Teléfono',optional=True,maxlen=25),f('vereda','Vereda o sector',maxlen=100)]),
 'fincas': dict(table='finca',title='Fincas',singular='finca',icon='02',description='Ubicación y vínculo con cada productor.',fields=[f('productor_id','Productor','ref',ref=PROD),f('nombre','Nombre',maxlen=120),f('ubicacion','Ubicación',maxlen=200)]),
 'parcelas': dict(table='parcela',title='Parcelas',singular='parcela',icon='03',description='Unidades de terreno para organizar la siembra.',fields=[f('finca_id','Finca','ref',ref=FINCA),f('nombre','Nombre',maxlen=120),f('area_ha','Área (ha)','number',step='0.001',maximum='9999999.999')]),
 'cultivos': dict(table='cultivo',title='Productos / cultivos',singular='producto / cultivo',icon='04',description='Registra los productos que vas a sembrar y sus variedades.',fields=[f('nombre','Cultivo',maxlen=80),f('variedad','Variedad',maxlen=80)]),
 'ciclos': dict(table='ciclo',title='Ciclos de siembra',singular='ciclo',icon='05',description='Cada temporada conecta una parcela con un cultivo.',fields=[f('parcela_id','Parcela','ref',ref=PARCELA),f('cultivo_id','Cultivo','ref',ref=CULTIVO),f('fecha_siembra','Fecha de siembra','date'),f('fecha_fin','Fecha de cierre','date',optional=True),f('estado','Estado','select',choices=['planificado','activo','finalizado'])]),
 'cosechas': dict(table='cosecha',title='Cosechas',singular='cosecha',icon='06',description='Producción recolectada, siempre expresada en kilogramos.',fields=[f('ciclo_id','Ciclo','ref',ref=CICLO),f('fecha','Fecha','date'),f('cantidad_kg','Cantidad (kg)','number',step='0.001',maximum='999999999.999')]),
 'clientes': dict(table='cliente',title='Clientes',singular='cliente',icon='07',description='Compradores de la producción registrada.',fields=[f('documento','Documento',maxlen=25),f('nombre','Nombre',maxlen=120),f('telefono','Teléfono',optional=True,maxlen=25)]),
 'ventas': dict(table='venta',title='Ventas',singular='venta',icon='08',description='Crea la venta y luego registra sus productos en Detalles de venta.',fields=[f('cliente_id','Cliente','ref',ref=CLIENTE),f('fecha','Fecha','date'),f('observacion','Observación',optional=True,maxlen=250)]),
 'detalles': dict(table='detalle_venta',title='Detalles de venta',singular='detalle de venta',icon='09',description='Cantidad y precio por cosecha. La base impide vender más de lo disponible.',fields=[f('venta_id','Venta','ref',ref=VENTA),f('cosecha_id','Cosecha','ref',ref=COSECHA),f('cantidad_kg','Cantidad (kg)','number',step='0.001',maximum='999999999.999'),f('precio_kg','Precio por kg (COP)','number',step='0.01',maximum='999999999999.99')]),
 'gastos': dict(table='gasto',title='Gastos',singular='gasto',icon='10',description='Costos registrados para cada ciclo de producción.',fields=[f('ciclo_id','Ciclo','ref',ref=CICLO),f('fecha','Fecha','date'),f('concepto','Concepto',maxlen=180),f('valor','Valor (COP)','number',step='0.01',maximum='999999999999.99')])
}


@app.before_request
def protect():
    g.user = None
    if session.get('uid'):
        with db(True) as conn:
            g.user = conn.execute('SELECT u.id,u.nombre,r.nombre AS rol FROM usuario u JOIN rol r ON r.id=u.rol_id WHERE u.id=%s AND u.activo', (session['uid'],)).fetchone()
        if not g.user:
            session.clear()
    if request.method == 'POST':
        token = session.get('csrf', '')
        if not token or not hmac.compare_digest(token.encode(), request.form.get('csrf','').encode()):
            abort(400, description='El formulario venció. Actualiza la página e inténtalo de nuevo.')


@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.context_processor
def context():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return dict(modules=MODULES, csrf=session['csrf'], demo=os.getenv('DEMO_DATA','1') == '1')


@app.template_filter('num')
def num(value, precision=2):
    return f'{value or 0:,.{precision}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user['rol'] != 'administrador':
            abort(403, description='Tu cuenta permite consultar y exportar. Los cambios requieren un administrador.')
        return fn(*args, **kwargs)
    return wrapped


@app.route('/login', methods=['GET','POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        with db(True) as conn:
            user = conn.execute('SELECT id,clave_hash FROM usuario WHERE correo=%s AND activo', (request.form.get('correo','').strip().lower(),)).fetchone()
        if user and check_password_hash(user['clave_hash'], request.form.get('clave','')):
            session.clear()
            session['uid'] = user['id']
            session['csrf'] = secrets.token_urlsafe(32)
            return redirect(url_for('dashboard'))
        flash('El correo o la contraseña no coinciden.', 'error')
    return render_template('login.html',title='Bienvenido')


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.get('/')
@login_required
def dashboard():
    with db(True) as conn:
        stats=conn.execute('''SELECT (SELECT count(*) FROM productor) AS productores,
            (SELECT count(*) FROM ciclo WHERE estado='activo') AS ciclos,
            (SELECT COALESCE(sum(disponible_kg),0) FROM v_existencias) AS disponible,
            (SELECT COALESCE(sum(ingresos),0) FROM v_resumen_ciclos) AS ingresos''').fetchone()
        cycles=conn.execute('SELECT * FROM v_resumen_ciclos ORDER BY id DESC LIMIT 6').fetchall()
        stocks=conn.execute('SELECT * FROM v_existencias ORDER BY id DESC LIMIT 5').fetchall()
    return render_template('dashboard.html',title='Vista general',stats=stats,cycles=cycles,stocks=stocks)


def get_module(key):
    if key not in MODULES:
        abort(404)
    return MODULES[key]


RELATED = {'productor_id':'productores','finca_id':'fincas','parcela_id':'parcelas','cultivo_id':'cultivos','ciclo_id':'ciclos','cliente_id':'clientes','venta_id':'ventas','cosecha_id':'cosechas'}


@app.context_processor
def related_context():
    return dict(related_modules=RELATED)


def options(conn, mod):
    return {field['name']:conn.execute(field['ref']).fetchall() for field in mod['fields'] if field['kind']=='ref'}


def listing_query(mod, args):
    conditions=[]
    params=[]
    search=[]
    for field in mod['fields']:
        ident=sql.Identifier(field['name'])
        search.append(sql.SQL('t.{}::text').format(ident))
        if field['kind']=='ref':
            search.append(sql.SQL('(SELECT label FROM ({}) opt WHERE opt.id=t.{})').format(sql.SQL(field['ref']),ident))
        value=args.get(field['name'],'').strip()
        if value and field['kind'] in ('ref','select'):
            if field['kind']=='ref':
                try: value=int(value)
                except ValueError: abort(400,description='Filtro inválido.')
            conditions.append(sql.SQL('t.{}=%s').format(ident));params.append(value)
    q=args.get('q','').strip()[:200]
    if q:
        conditions.append(sql.SQL("concat_ws(' ',{}) ILIKE %s").format(sql.SQL(',').join(search)))
        params.append('%'+q+'%')
    if mod['table'] in ('cosecha','venta','gasto','ciclo'):
        column='fecha_siembra' if mod['table']=='ciclo' else 'fecha'
        for arg,op in [('desde','>='),('hasta','<=')]:
            if args.get(arg):
                try: value=date.fromisoformat(args[arg])
                except ValueError: abort(400,description='La fecha del filtro no es válida.')
                conditions.append(sql.SQL('t.{} {} %s').format(sql.Identifier(column),sql.SQL(op)));params.append(value)
    where=sql.SQL(' WHERE ')+sql.SQL(' AND ').join(conditions) if conditions else sql.SQL('')
    return sql.SQL('SELECT t.* FROM {} t').format(sql.Identifier(mod['table']))+where+sql.SQL(' ORDER BY t.id DESC'),params


@app.get('/datos/<key>')
@login_required
def records(key):
    mod=get_module(key)
    query,params=listing_query(mod,request.args)
    try: page=max(1,int(request.args.get('page',1)))
    except ValueError: abort(400)
    with db(True) as conn:
        count=conn.execute(sql.SQL('SELECT count(*) AS n FROM ({}) q').format(query),params).fetchone()['n']
        page=min(page,max(1,(count+24)//25))
        rows=conn.execute(query+sql.SQL(' LIMIT 25 OFFSET %s'),params+[(page-1)*25]).fetchall()
        opts=options(conn,mod)
    labels={name:{row['id']:row['label'] for row in rows} for name,rows in opts.items()}
    return render_template('records.html',title=mod['title'],key=key,mod=mod,rows=rows,opts=opts,labels=labels,count=count,page=page,pages=max(1,(count+24)//25))


def validate(mod, form):
    values={}
    for field in mod['fields']:
        name=field['name'];value=form.get(name,'').strip()
        if not value:
            if field.get('optional'): values[name]=None;continue
            raise ValueError('Completa el campo '+field['label']+'.')
        if len(value)>field.get('maxlen',250):
            raise ValueError(field['label']+': el texto es demasiado largo.')
        if field['kind']=='ref':
            try: value=int(value)
            except ValueError: raise ValueError('Selecciona '+field['label']+'.')
            if value<=0: raise ValueError('Selecciona '+field['label']+'.')
        elif field['kind']=='number':
            try:
                value=Decimal(value)
                if not value.is_finite() or value<=0 or value>Decimal(field['maximum']) or value % Decimal(field['step']) != 0:
                    raise InvalidOperation
            except (InvalidOperation,ValueError):
                raise ValueError(field['label']+': usa un número positivo y respeta los decimales indicados.')
        elif field['kind']=='date':
            try: value=date.fromisoformat(value)
            except ValueError: raise ValueError('Revisa '+field['label']+'.')
        elif field['kind']=='select' and value not in field['choices']:
            raise ValueError('Selecciona una opción válida.')
        if name == 'nombre' and len(value) < 2:
            raise ValueError(field['label']+': escribe al menos dos caracteres.')
        values[name]=value
    if mod['table']=='ciclo':
        if values['fecha_fin'] and values['fecha_fin'] < values['fecha_siembra']:
            raise ValueError('La fecha de cierre no puede ser anterior a la siembra.')
        if values['estado']=='finalizado' and not values['fecha_fin']:
            raise ValueError('Indica la fecha de cierre para finalizar el ciclo.')
    return values


def friendly_error(exc):
    if isinstance(exc,(psycopg.errors.ForeignKeyViolation,psycopg.errors.RestrictViolation)):
        return 'Este registro está relacionado con otros datos. Revisa las relaciones antes de cambiarlo o eliminarlo.'
    if isinstance(exc,psycopg.errors.UniqueViolation):
        return 'Ya existe ese documento o combinación de datos; también puede haber un ciclo activo en esa parcela.'
    if isinstance(exc,psycopg.errors.CheckViolation):
        message=exc.diag.message_primary or ''
        if message.startswith(('La venta','La cosecha')): return message
        return 'Revisa las cantidades, el estado y las fechas: no cumplen las reglas de la base de datos.'
    return 'No se pudo guardar: revisa los valores y las relaciones.'


@app.route('/datos/<key>/nuevo', methods=['GET','POST'])
@app.route('/datos/<key>/<int:rid>/editar', methods=['GET','POST'])
@admin_required
def edit(key,rid=None):
    mod=get_module(key)
    with db(True) as conn:
        opts=options(conn,mod)
        row=conn.execute(sql.SQL('SELECT * FROM {} WHERE id=%s').format(sql.Identifier(mod['table'])),(rid,)).fetchone() if rid else {}
    if rid and not row: abort(404)
    if not rid and request.method=='GET':
        row={field['name']:request.args.get(field['name'],'') for field in mod['fields'] if field['kind']=='ref'}
    if request.method=='POST':
        row=request.form
        try:
            values=validate(mod,request.form)
            for field in mod['fields']:
                if field['kind']=='ref' and values[field['name']] not in {opt['id'] for opt in opts[field['name']]}:
                    raise ValueError('Selecciona un registro existente para '+field['label']+'.')
            if mod['table']=='ciclo' and not rid: values['usuario_id']=g.user['id']
            with db() as conn:
                if rid:
                    assignments=sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(n)) for n in values)
                    result=conn.execute(sql.SQL('UPDATE {} SET {} WHERE id=%s').format(sql.Identifier(mod['table']),assignments),list(values.values())+[rid])
                else:
                    result=conn.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(mod['table']),sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values))+sql.SQL(' RETURNING id'),list(values.values()))
                if result.rowcount != 1: abort(404)
                new_id=result.fetchone()['id'] if not rid else rid
            flash('Registro guardado correctamente.','success')
            parent=request.args.get('volver')
            if not rid and parent in MODULES:
                field=next((f['name'] for f in MODULES[parent]['fields'] if RELATED.get(f['name'])==key),None)
                if field:
                    return redirect(url_for('edit',key=parent,**{field:new_id}))
            return redirect(url_for('records',key=key))
        except ValueError as exc: flash(str(exc),'error')
        except psycopg.IntegrityError as exc: flash(friendly_error(exc),'error')
    return render_template('form.html',title=('Editar ' if rid else 'Nuevo ')+mod['singular'],mod=mod,key=key,row=row,opts=opts)



@app.get('/usuarios')
@admin_required
def users():
    with db(True) as conn:
        rows=conn.execute('SELECT u.id,u.nombre,u.correo,u.activo,r.nombre AS rol FROM usuario u JOIN rol r ON r.id=u.rol_id ORDER BY u.id DESC').fetchall()
    return render_template('users.html',title='Usuarios',rows=rows)


@app.route('/usuarios/nuevo',methods=['GET','POST'])
@admin_required
def create_user():
    row={}
    if request.method=='POST':
        row={key:request.form.get(key,'').strip() for key in ('nombre','correo','rol')}
        row['correo']=row['correo'].lower()
        password=request.form.get('clave','')
        try:
            if not 2 <= len(row['nombre']) <= 120:
                raise ValueError('El nombre debe tener entre 2 y 120 caracteres.')
            if len(row['correo']) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',row['correo']):
                raise ValueError('Escribe un correo válido.')
            if row['rol'] not in ('administrador','consulta'):
                raise ValueError('Selecciona el rol administrador o consulta.')
            if not 12 <= len(password) <= 128 or not password.strip():
                raise ValueError('La contraseña debe tener entre 12 y 128 caracteres.')
            if password != request.form.get('confirmar_clave',''):
                raise ValueError('Las contraseñas no coinciden.')
            with db() as conn:
                role=conn.execute('SELECT id FROM rol WHERE nombre=%s',(row['rol'],)).fetchone()
                if not role:
                    raise ValueError('El rol no está configurado en la base de datos.')
                conn.execute('INSERT INTO usuario(rol_id,nombre,correo,clave_hash) VALUES (%s,%s,%s,%s)',(role['id'],row['nombre'],row['correo'],generate_password_hash(password)))
            flash('Usuario creado correctamente. Ya puede iniciar sesión con su correo y contraseña.','success')
            return redirect(url_for('users'))
        except ValueError as exc:
            flash(str(exc),'error')
        except psycopg.errors.UniqueViolation:
            flash('Ya existe un usuario con ese correo.','error')
    return render_template('user_form.html',title='Crear usuario',row=row)


@app.route('/datos/<key>/<int:rid>/eliminar',methods=['GET','POST'])
@admin_required
def delete(key,rid):
    mod=get_module(key)
    if request.method=='POST':
        try:
            with db() as conn:
                result=conn.execute(sql.SQL('DELETE FROM {} WHERE id=%s').format(sql.Identifier(mod['table'])),(rid,))
                if result.rowcount != 1: abort(404)
            flash('Registro eliminado.','success')
        except psycopg.IntegrityError as exc: flash(friendly_error(exc),'error')
        return redirect(url_for('records',key=key))
    with db(True) as conn:
        row=conn.execute(sql.SQL('SELECT id FROM {} WHERE id=%s').format(sql.Identifier(mod['table'])),(rid,)).fetchone()
    if not row: abort(404)
    return render_template('delete.html',title='Eliminar registro',key=key,mod=mod,rid=rid)


def csv_response(rows,columns,filename):
    stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';')
    writer.writerow([label for _,label in columns])
    for row in rows:
        output=[]
        for key,_ in columns:
            raw=row.get(key)
            value='' if raw is None else str(raw)
            # Previene fórmulas al abrir texto de usuario en hojas de cálculo.
            if isinstance(raw,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')): value="'"+value
            output.append(value)
        writer.writerow(output)
    return Response('\ufeff'+stream.getvalue(),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}.csv"'})


@app.get('/exportar/<key>')
@login_required
def export(key):
    mod=get_module(key);query,params=listing_query(mod,request.args)
    with db(True) as conn:
        rows=conn.execute(query,params).fetchall();opts=options(conn,mod)
    labels={name:{r['id']:r['label'] for r in items} for name,items in opts.items()}
    for row in rows:
        for field in mod['fields']:
            if field['kind']=='ref': row[field['name']]=labels[field['name']].get(row[field['name']],row[field['name']])
    return csv_response(rows,[('id','ID')]+[(f['name'],f['label']) for f in mod['fields']], 'agrotrack_'+key)


@app.get('/reportes')
@login_required
def reports():
    conditions=[];params=[]
    for arg in ('productor','cultivo','estado'):
        value=request.args.get(arg,'').strip()
        if value:
            column={'productor':'productor_id','cultivo':'cultivo_id','estado':'estado'}[arg]
            if arg != 'estado':
                try: value=int(value)
                except ValueError: abort(400,description='Filtro inválido.')
            conditions.append(sql.SQL('{}=%s').format(sql.Identifier(column)));params.append(value)
    for arg,op in [('desde','>='),('hasta','<=')]:
        if request.args.get(arg):
            try: value=date.fromisoformat(request.args[arg])
            except ValueError: abort(400,description='Fecha inválida.')
            conditions.append(sql.SQL('fecha_siembra {} %s').format(sql.SQL(op)));params.append(value)
    where=sql.SQL(' WHERE ')+sql.SQL(' AND ').join(conditions) if conditions else sql.SQL('')
    with db(True) as conn:
        rows=conn.execute(sql.SQL('SELECT * FROM v_resumen_ciclos')+where+sql.SQL(' ORDER BY id DESC'),params).fetchall()
        above=conn.execute(sql.SQL('SELECT count(*) AS n FROM v_resumen_ciclos')+where+(sql.SQL(' AND ') if conditions else sql.SQL(' WHERE '))+sql.SQL('ingresos > (SELECT avg(ingresos) FROM v_resumen_ciclos) '),params).fetchone()['n']
        producers=conn.execute('SELECT DISTINCT productor_id AS id,productor FROM v_resumen_ciclos ORDER BY productor').fetchall()
        crops=conn.execute('SELECT DISTINCT cultivo_id AS id,cultivo FROM v_resumen_ciclos ORDER BY cultivo').fetchall()
    columns=[('id','Ciclo'),('productor','Productor'),('finca','Finca'),('parcela','Parcela'),('cultivo','Cultivo'),('estado','Estado'),('fecha_siembra','Siembra'),('fecha_fin','Cierre'),('cosechado_kg','Cosechado (kg)'),('ingresos','Ventas (COP)'),('gastos','Gastos (COP)'),('saldo','Saldo parcial (COP)')]
    if request.args.get('formato')=='csv': return csv_response(rows,columns,'agrotrack_reporte_ciclos')
    totals={key:sum((row[key] for row in rows),Decimal(0)) for key in ['cosechado_kg','ingresos','gastos','saldo']}
    return render_template('reports.html',title='Análisis de producción',rows=rows,totals=totals,above=above,producers=producers,crops=crops)


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def http_error(exc):
    return render_template('error.html',title=str(exc.code),message=exc.description),exc.code


def main():
    if '--setup' in sys.argv:
        from setup_database import initialize
        initialize()
        return
    if not app.secret_key or not os.environ.get('DATABASE_URL'):
        raise SystemExit('Falta SECRET_KEY o DATABASE_URL. Revisa .env o inicializa AgroTrack con --setup.')
    try:
        with db(True) as conn:
            conn.execute('SELECT 1 FROM usuario LIMIT 1')
    except psycopg.Error as error:
        raise SystemExit(f'No se pudo comprobar PostgreSQL y el esquema de AgroTrack ({type(error).__name__}).') from None
    if '--check' in sys.argv:
        print('Configuración, conexión PostgreSQL y esquema verificados.')
        return
    from waitress import create_server
    port = int(os.getenv('PORT', '5084'))
    url = f'http://127.0.0.1:{port}'
    server = create_server(app, host='127.0.0.1', port=port)
    print(f'AgroTrack disponible en {url}. Ctrl+C para detenerlo.', flush=True)
    if '--open-browser' in sys.argv:
        browser = Timer(0.2, webbrowser.open, args=(url,))
        browser.daemon = True
        browser.start()
    server.run()


if __name__ == '__main__':
    main()
