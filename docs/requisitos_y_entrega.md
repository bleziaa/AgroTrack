# AgroTrack · correspondencia con la guía del profesor

La fuente de los requisitos es la descripción completa suministrada por Luis el 17 de noviembre de 2026. No se ha suministrado una fecha de cierre.

| Requisito oficial | Implementación prevista o incluida | Evidencia necesaria |
|---|---|---|
| Empresa, entidad o comunidad local REAL | Agricultores de San Jacinto como contexto propuesto | Confirmar comunidad concreta, interlocutor y problemática observada; pendiente |
| Al menos 8 tablas relacionadas | 12 tablas con PK y FK | schema.sql y diagrama |
| Base normalizada y diagrama de relación | Separación de entidades y justificación de 1FN, 2FN, 3FN | docs/modelo_relacional.md; validar supuestos con comunidad |
| Administrador y solo consulta | Sesiones y autorización de rutas en servidor | Pruebas de acceso a escritura con ambos roles |
| Búsqueda por varios parámetros | Texto, relaciones, estado y rangos de fecha según módulo | Consultas con filtros combinados y comparación de resultados |
| Insertar, actualizar, eliminar y visualizar | Diez módulos de registros | Ciclo CRUD y rechazos de integridad |
| Funciones, consultas y subconsultas | fn_ingresos_ciclo, vistas, filtros parametrizados, comparación con promedio | SQL y resultados reproducibles |
| Extracción y análisis | CSV filtrados y resumen por ciclo | Archivo exportado coincidente con filtros y totales verificados |
| Utilidad y fiabilidad con el software | Trazabilidad de cosecha a venta; restricciones y transacciones | Pruebas y validación del caso real; no basta mostrar pantallas |
| Documento mínimo 3000 palabras | Pendiente de elaboración con contexto confirmado | Conteo del cuerpo y revisión final |
| Times New Roman 12 e interlineado 1.5 | Aplicar al documento final | Revisar estilos del DOCX/PDF |
| Texto original y APA, Vancouver o Icontec | Se propone APA, por confirmar al redactar | Citas verificadas y bibliografía concordante |
| Estructura obligatoria | Portada, contenido, problemática, objetivos, solución detallada, resultados, bibliografía | Revisar secciones completas |

## Qué debe confirmarse antes del informe final

1. Nombre de la comunidad, asociación o grupo real. Si es un grupo informal, describirlo con precisión sin inventar una organización.
2. Cómo registran actualmente parcelas, producción, ventas y gastos; problemas observados y sus evidencias.
3. Tema adicional que haya definido el tutor: la guía lo menciona pero no especifica cuál es.
4. Fecha y modalidad de entrega, integrantes y datos de portada.
5. Validación de los supuestos: un responsable por finca, kilos como unidad y un cultivo activo por parcela.

## Estructura de trabajo para el informe

El documento final debe superar las 3000 palabras con contenido sustantivo. Distribución orientativa del cuerpo: contexto 650; objetivos 200; solución y proceso de creación 1500; resultados y discusión 850. La portada, índice y referencias no se usarán para completar artificialmente el mínimo.

Los resultados deben separar pruebas técnicas sobre datos ficticios de observaciones reales. No afirmar reducción de pérdidas, aumento de productividad, entrevistas, implementación comunitaria ni satisfacción de usuarios sin evidencia.

## Guion breve de demostración

Entrar como consulta y revisar filtros y exportación. Verificar que no existen acciones de edición y que el servidor rechaza el acceso directo a esas rutas. Entrar como administrador; registrar un productor, finca, parcela y ciclo; añadir cosecha y gastos; crear cliente, venta y detalle. Revisar el reporte y comparar la función SQL con los ingresos mostrados. Intentar una sobreventa, una cantidad negativa y eliminar un productor con finca vinculada; explicar por qué se rechazan. Exportar los datos filtrados y revisar sus totales.
