-- Ejecutar una vez como propietario en el clúster privado existente.
-- No altera registros ni concede modificación o borrado de usuarios al proceso web.
BEGIN;
GRANT INSERT ON usuario TO agrotrack_runtime;
COMMIT;
