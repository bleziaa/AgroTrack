-- AgroTrack / PostgreSQL. Ejecutar en una base nueva, nunca sobre datos existentes.
BEGIN;
CREATE TABLE rol (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 nombre text NOT NULL UNIQUE CHECK(nombre IN ('administrador','consulta'))
);
CREATE TABLE usuario (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 rol_id bigint NOT NULL REFERENCES rol(id) ON DELETE RESTRICT,
 nombre text NOT NULL CHECK(length(trim(nombre)) BETWEEN 2 AND 120),
 correo text NOT NULL UNIQUE CHECK(correo = lower(correo)),
 clave_hash text NOT NULL,
 activo boolean NOT NULL DEFAULT true
);
CREATE TABLE productor (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 documento varchar(25) NOT NULL UNIQUE,
 nombre varchar(120) NOT NULL CHECK(length(trim(nombre)) >= 2),
 telefono varchar(25), vereda varchar(100) NOT NULL
);
CREATE TABLE finca (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 productor_id bigint NOT NULL REFERENCES productor(id) ON DELETE RESTRICT,
 nombre varchar(120) NOT NULL, ubicacion varchar(200) NOT NULL,
 UNIQUE(productor_id,nombre)
);
CREATE TABLE parcela (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 finca_id bigint NOT NULL REFERENCES finca(id) ON DELETE RESTRICT,
 nombre varchar(120) NOT NULL,
 area_ha numeric(10,3) NOT NULL CHECK(area_ha > 0),
 UNIQUE(finca_id,nombre)
);
CREATE TABLE cultivo (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 nombre varchar(80) NOT NULL, variedad varchar(80) NOT NULL,
 UNIQUE(nombre,variedad)
);
CREATE TABLE ciclo (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 parcela_id bigint NOT NULL REFERENCES parcela(id) ON DELETE RESTRICT,
 cultivo_id bigint NOT NULL REFERENCES cultivo(id) ON DELETE RESTRICT,
 usuario_id bigint NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
 fecha_siembra date NOT NULL,
 fecha_fin date,
 estado varchar(20) NOT NULL CHECK(estado IN ('planificado','activo','finalizado')),
 CHECK(fecha_fin IS NULL OR fecha_fin >= fecha_siembra),
 CHECK(estado <> 'finalizado' OR fecha_fin IS NOT NULL)
);
CREATE UNIQUE INDEX un_ciclo_activo_por_parcela ON ciclo(parcela_id) WHERE estado = 'activo';
CREATE TABLE cosecha (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 ciclo_id bigint NOT NULL REFERENCES ciclo(id) ON DELETE RESTRICT,
 fecha date NOT NULL, cantidad_kg numeric(12,3) NOT NULL CHECK(cantidad_kg > 0)
);
CREATE TABLE cliente (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 documento varchar(25) NOT NULL UNIQUE,
 nombre varchar(120) NOT NULL, telefono varchar(25)
);
CREATE TABLE venta (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 cliente_id bigint NOT NULL REFERENCES cliente(id) ON DELETE RESTRICT,
 fecha date NOT NULL, observacion varchar(250)
);
CREATE TABLE detalle_venta (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 venta_id bigint NOT NULL REFERENCES venta(id) ON DELETE RESTRICT,
 cosecha_id bigint NOT NULL REFERENCES cosecha(id) ON DELETE RESTRICT,
 cantidad_kg numeric(12,3) NOT NULL CHECK(cantidad_kg > 0),
 precio_kg numeric(14,2) NOT NULL CHECK(precio_kg > 0),
 UNIQUE(venta_id,cosecha_id)
);
CREATE TABLE gasto (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 ciclo_id bigint NOT NULL REFERENCES ciclo(id) ON DELETE RESTRICT,
 fecha date NOT NULL,
 concepto varchar(180) NOT NULL,
 valor numeric(14,2) NOT NULL CHECK(valor > 0)
);
CREATE INDEX ON finca(productor_id);
CREATE INDEX ON parcela(finca_id);
CREATE INDEX ON ciclo(cultivo_id);
CREATE INDEX ON ciclo(usuario_id);
CREATE INDEX ON cosecha(ciclo_id);
CREATE INDEX ON cosecha(fecha);
CREATE INDEX ON venta(cliente_id);
CREATE INDEX ON venta(fecha);
CREATE INDEX ON detalle_venta(cosecha_id);
CREATE INDEX ON gasto(ciclo_id);

-- Serializa ventas concurrentes sobre una cosecha para impedir sobreventa.
-- El orden de bloqueo evita invertir locks cuando se cambia la cosecha de un detalle.
CREATE FUNCTION validar_disponibilidad() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE disponible numeric; usado numeric;
BEGIN
 IF TG_OP = 'UPDATE' THEN
  PERFORM id FROM cosecha WHERE id IN (OLD.cosecha_id,NEW.cosecha_id) ORDER BY id FOR UPDATE;
 ELSE
  PERFORM id FROM cosecha WHERE id = NEW.cosecha_id FOR UPDATE;
 END IF;
 SELECT cantidad_kg INTO disponible FROM cosecha WHERE id=NEW.cosecha_id;
 SELECT COALESCE(sum(cantidad_kg),0) INTO usado FROM detalle_venta
 WHERE cosecha_id=NEW.cosecha_id AND id <> COALESCE(NEW.id,0);
 IF usado + NEW.cantidad_kg > disponible THEN
  RAISE EXCEPTION 'La venta supera los kilogramos disponibles de la cosecha.' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER controlar_stock BEFORE INSERT OR UPDATE ON detalle_venta
 FOR EACH ROW EXECUTE FUNCTION validar_disponibilidad();

CREATE FUNCTION validar_reduccion_cosecha() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.cantidad_kg < (SELECT COALESCE(sum(cantidad_kg),0) FROM detalle_venta WHERE cosecha_id=NEW.id) THEN
  RAISE EXCEPTION 'La cosecha no puede ser menor que la cantidad ya vendida.' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER controlar_reduccion BEFORE UPDATE OF cantidad_kg ON cosecha
 FOR EACH ROW EXECUTE FUNCTION validar_reduccion_cosecha();

CREATE FUNCTION fn_ingresos_ciclo(p_ciclo bigint) RETURNS numeric
 LANGUAGE sql STABLE AS $$
 SELECT COALESCE(sum(round(d.cantidad_kg*d.precio_kg,2)),0)
 FROM detalle_venta d JOIN cosecha h ON h.id=d.cosecha_id WHERE h.ciclo_id=p_ciclo
$$;

CREATE VIEW v_existencias AS
 SELECT h.id,h.ciclo_id,h.fecha,h.cantidad_kg,
 h.cantidad_kg-COALESCE((SELECT sum(d.cantidad_kg) FROM detalle_venta d WHERE d.cosecha_id=h.id),0) AS disponible_kg
 FROM cosecha h;

-- Cada agregado se calcula por separado: evita multiplicar ingresos y gastos al hacer JOIN.
CREATE VIEW v_resumen_ciclos AS
 SELECT c.id,p.id AS productor_id,cu.id AS cultivo_id,p.nombre AS productor,f.nombre AS finca,pa.nombre AS parcela,
 cu.nombre||' · '||cu.variedad AS cultivo,c.estado,c.fecha_siembra,c.fecha_fin,
 COALESCE((SELECT sum(h.cantidad_kg) FROM cosecha h WHERE h.ciclo_id=c.id),0) AS cosechado_kg,
 fn_ingresos_ciclo(c.id) AS ingresos,
 COALESCE((SELECT sum(g.valor) FROM gasto g WHERE g.ciclo_id=c.id),0) AS gastos,
 fn_ingresos_ciclo(c.id)-COALESCE((SELECT sum(g.valor) FROM gasto g WHERE g.ciclo_id=c.id),0) AS saldo
 FROM ciclo c JOIN parcela pa ON pa.id=c.parcela_id JOIN finca f ON f.id=pa.finca_id
 JOIN productor p ON p.id=f.productor_id JOIN cultivo cu ON cu.id=c.cultivo_id;
COMMENT ON VIEW v_resumen_ciclos IS 'Saldo parcial de ventas registradas menos gastos registrados; no equivale a utilidad contable total.';
COMMIT;
