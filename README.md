# FutbolQuiz Arena — Backend

FastAPI con SQLAlchemy y PostgreSQL. Registro, login, Home, edición de perfil, sesión JWT, ruleta de categorías, partidas individuales, duelos online y locales, motor de torneos por eliminación directa y panel de administración integral.

El recorrido de cambios y decisiones del proyecto está documentado en los entregables de la cátedra bajo `documentacion del proyecto (entregables)/` y en [CHANGELOG.md](CHANGELOG.md).

El contrato OpenAPI y Swagger interactivo consultado para la integración con el frontend está publicado en `/docs` y `/redoc`, y resumido en [documentacion del proyecto (entregables)/naming_map.md](documentacion%20del%20proyecto%20(entregables)/naming_map.md).

## Desarrollo local

Requiere Python 3.10 o superior (recomendado Python 3.12+ o 3.14) y pip.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:crear_aplicacion --factory --reload
```

En macOS/Linux, usar `source .venv/bin/activate` y `cp .env.example .env`. La configuración del entorno y la base de datos se define en `.env`:

```dotenv
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:6543/postgres
JWT_SECRET=super_secreto_futbolquiz_arena_cambiar_en_produccion
JWT_EXPIRATION_MIN=60
ENTORNO=desarrollo
TITULO_APP="FutbolQuiz Arena API"
VERSION_APP="0.1.0"
DEBUG=true
```

Para Supabase en la nube, la URL utiliza el **puerto 6543 (Transaction Mode / PgBouncer)** para permitir alta concurrencia y múltiples conexiones simultáneas desde el cliente sin agotar los límites del servidor.

Rutas raíz: la API se expone bajo el prefijo `/api`. La documentación Swagger UI interactiva queda accesible en `http://localhost:8000/docs`, Redoc en `http://localhost:8000/redoc` y la especificación OpenAPI JSON en `http://localhost:8000/openapi.json`. El servidor incluye middleware de CORS configurado con `allow_credentials=True` y soporte para los orígenes del frontend (`http://localhost:5173`, `http://localhost:3000`, etc.).

## Home y consulta de estado

El endpoint `GET /api/usuarios/me` provee a la pantalla `/home` del frontend los datos reales del usuario autenticado: `nombre`, `email`, `rol` (`JUGADOR` o `ADMINISTRADOR`), `puntaje_total` acumulado y `esta_habilitado`.

El backend permite al frontend condicionar la navegación: la opción de acceso al panel de administración se habilita únicamente cuando la respuesta confirma el rol `ADMINISTRADOR`. Para destacar torneos en la pantalla principal, `GET /api/torneos?filtro=disponibles` entrega el listado de torneos en espera de participantes. El endpoint `GET /api/health` responde con `{"status": "ok"}` confirmando la operatividad del backend y la conectividad activa con PostgreSQL.

## Administración: preguntas — actividad 5.1.1

El controlador `app/routes/admin/pregunta_router.py` gestiona el banco de preguntas bajo el prefijo `/api/admin/preguntas`. Todas las operaciones exigen token JWT Bearer y rol `ADMINISTRADOR` validado mediante la dependencia `requiere_rol()`.

`GET /api/admin/preguntas` devuelve un listado paginado con soporte para los parámetros `page` (iniciando en 1), `page_size` (por defecto 6), búsqueda libre por texto en el enunciado (`buscar`, insensible a mayúsculas y acentos), filtro por identificador de categoría (`categoria_id`) y filtro por estado (`estado`: `ACTIVA` o `BORRADOR`). La respuesta incluye `items`, `total`, `page` y `total_paginas`, garantizando compatibilidad con el frontend. Cada pregunta incluye sus 4 opciones (`opcion_a` a `opcion_d`), respuesta correcta, dificultad y nombre de categoría.

`POST /api/admin/preguntas` permite dar de alta una nueva pregunta validando previamente la existencia de la categoría indicada. Exige cuatro opciones no vacías y una respuesta correcta válida (`A`, `B`, `C` o `D`). Devuelve `201 Created` con la pregunta creada.

`GET /api/admin/preguntas/{id}` y `PATCH /api/admin/preguntas/{id}` permiten consultar el detalle y actualizar parcialmente cualquier campo (enunciado, opciones, respuesta correcta, categoría, dificultad o estado) validando las reglas de negocio.

`DELETE /api/admin/preguntas/{id}` aplica una **baja lógica (*soft-delete*)** seteando la marca temporal `eliminada_en`. La pregunta deja de ser visible en el panel administrativo y no se selecciona para nuevas partidas, pero se preserva la fila en la base de datos para mantener intacta la integridad referencial con el historial de partidas ya disputadas.

`POST /api/admin/preguntas/{id}/duplicar` clona una pregunta existente inicializándola automáticamente en estado `BORRADOR` para revisión antes de su activación. `PATCH /api/admin/preguntas/{id}/estado` realiza el cambio rápido de estado entre `ACTIVA` y `BORRADOR`.

## Administración: categorías — actividad 5.1.2

El controlador `app/routes/admin/categoria_router.py` implementa la gestión de categorías bajo `/api/admin/categorias`, restringido a administradores.

`GET /api/admin/categorias` lista las categorías existentes permitiendo filtrar por búsqueda de texto y estado (`ACTIVA` o `BORRADOR`). Cada elemento incluye el cálculo dinámico `preguntas_count` con la cantidad real de preguntas asociadas no eliminadas, dato que consume la grilla y tarjetas móviles de `/admin/categorias`.

`POST /api/admin/categorias` crea una nueva categoría validando que el nombre no esté duplicado; ante colisiones responde con `409 Conflict`.

`GET /api/admin/categorias/{id}` y `PATCH /api/admin/categorias/{id}` devuelven el detalle y permiten renombrar o cambiar el estado de la categoría.

`DELETE /api/admin/categorias/{id}` elimina físicamente una categoría del sistema únicamente si no posee preguntas vinculadas. Si la categoría tiene preguntas asociadas, la solicitud es rechazada con código `400 Bad Request` informando que no es posible eliminarla por restricciones de integridad. `PATCH /api/admin/categorias/{id}/estado` alterna el estado entre `ACTIVA` y `BORRADOR`.

## Administración: usuarios — actividad 5.1.3

El controlador `app/routes/admin/usuario_router.py` implementa la gestión de cuentas de usuario bajo `/api/admin/usuarios` con autorización de administrador.

`GET /api/admin/usuarios` lista los usuarios registrados con filtros opcionales de búsqueda parcial por nombre o correo electrónico (`buscar`), filtro por rol (`rol`: `JUGADOR` o `ADMINISTRADOR`) y filtro por estado (`esta_habilitado`: true/false).

`GET /api/admin/usuarios/{id}` devuelve la ficha completa del usuario (ID, nombre, correo, rol, puntaje acumulado, estado de habilitación y fecha de alta).

`PATCH /api/admin/usuarios/{id}/estado` actualiza el campo `esta_habilitado` recibiendo `{ esta_habilitado: boolean }`. El servicio implementa una regla de protección que impide que un administrador desactive su propia cuenta, respondiendo con `400 Bad Request` ante este intento para evitar el bloqueo del acceso administrativo al sistema.

## Siembra de datos del sistema (Seed) — actividad 5.1.4

El endpoint protegido `POST /api/admin/sistema/sembrar` lee el archivo de datos `scripts/preguntas_seed.json` y puebla la base de datos de manera modular e idempotente.

Inserta las categorías temáticas de fútbol y el banco completo de preguntas de opción múltiple verificando previamente su existencia por nombre y enunciado. Si los registros ya existen, los omite sin duplicar datos ni alterar los IDs asignados. Retorna un resumen con el conteo de categorías y preguntas creadas y omitidas.

El proceso también puede ejecutarse de manera directa desde la terminal mediante el script CLI:

```powershell
.venv\Scripts\python scripts/sembrar_datos.py
```

## Perfil — actividad 1.3

El controlador `app/routes/usuario_router.py` gestiona la consulta y modificación de los datos de la cuenta activa.

`GET /api/usuarios/me` devuelve los datos del usuario autenticado a partir del JWT enviado en el encabezado `Authorization: Bearer <token>`.

`PATCH /api/usuarios/me` permite modificar el nombre y el correo electrónico. Si se modifica el email, valida que el nuevo correo no esté registrado por otro usuario (`409 Conflict`). Si se incluye contraseña nueva, valida la contraseña actual antes de aplicar el cambio.

`PATCH /api/usuarios/me/password` expone el endpoint específico para actualizar la clave de acceso recibiendo `{ password_actual, nuevo_password }`. Valida que la contraseña actual coincida con el hash almacenado, verifica los requisitos mínimos de seguridad para la nueva clave y guarda el nuevo hash seguro.

## Categorías y ruleta — actividad 2.1

El controlador `app/routes/categoria_router.py` expone `GET /api/categorias` (y su alias `GET /api/partidas/categorias`), el cual entrega la lista de categorías en estado `ACTIVA` (Mundiales, Champions League, Copa Libertadores, Copa América, Clubes, etc.).

Este catálogo alimenta la ruleta visual de selección de categorías y el selector de modos de juego en el frontend. Cada pregunta del banco está asociada a una categoría activa y almacena 4 opciones, nivel de dificultad y respuesta correcta. El servicio `obtener_preguntas_aleatorias_sin_repeticion()` garantiza que al iniciar cualquier partida se seleccionen 10 preguntas al azar sin repeticiones, verificando previamente que la categoría cuente con stock suficiente.

## Partidas individuales — actividad 2.2

El controlador `app/routes/partida_router.py` gestiona el ciclo completo del modo de juego individual:

- `POST /api/partidas/individual` inicia una partida individual para el usuario autenticado: selecciona una categoría activa (por ruleta o elección) y asigna 10 preguntas aleatorias sin repetición, inicializando el registro en la tabla `partidas_individuales`.
- `POST /api/partidas/preguntas/{pregunta_partida_id}/respuesta` recibe `{ opcion_seleccionada, tiempo_respuesta_segundos }`. Valida que la pregunta pertenezca a la partida activa del usuario y que no haya sido respondida con anterioridad. Compara la opción enviada con la respuesta correcta registrada, calcula el puntaje según acierto y velocidad de respuesta, marca la pregunta como respondida y acumula los puntos.
- `GET /api/partidas/{partida_id}/resultado` devuelve el balance de la partida al finalizar: total de aciertos, total de errores, desglose detallado pregunta por pregunta con puntos obtenidos y el puntaje final consolidado, sumándolo al `puntaje_total` global del perfil del jugador.

## Duelos online y locales — actividad 2.3

El controlador `app/routes/duelo_router.py` implementa las dos modalidades de enfrentamiento directo de trivias:

- **Duelo Online (`POST /api/duelos/online`)**: sistema de emparejamiento automático (*matchmaking*). Si encuentra una partida en estado `PENDIENTE_RIVAL`, asocia al usuario autenticado como jugador 2, pasa el estado a `EN_CURSO` y comparte el mismo conjunto de preguntas. Si no hay rival esperando, crea una nueva partida de duelo y queda en espera.
- **Duelo Local / Pass & Play (`POST /api/duelos/local`)**: inicia una partida para dos jugadores en un mismo dispositivo por turnos alternados, recibiendo el nombre del invitado sin requerir cuenta adicional.
- `POST /api/duelos/preguntas/{id}/respuesta` procesa las respuestas de cada competidor calculando los puntos de manera individual.
- `GET /api/duelos/{id}` y `GET /api/duelos/{id}/estado` permiten a ambos participantes consultar el estado de la partida, el progreso del rival y la resolución final del ganador (`numero_ganador`: 1, 2 o empate).

## Listado de torneos — actividad 3.1.1 (3.3.1)

El endpoint `GET /api/torneos` bajo `app/routes/torneo_router.py` entrega el listado de torneos admitiendo los filtros `filtro=mios`, `filtro=disponibles`, `filtro=finalizados` y `todos`.

Retorna para cada torneo su identificador, nombre, cupo total de participantes (**4, 8 o 16**), cantidad de participantes inscriptos en tiempo real, estado (`ESPERANDO_JUGADORES`, `EN_CURSO`, `FINALIZADO`), código de acceso alfanumérico, si requiere contraseña y la fecha de creación. El listado alimenta las pestañas de torneos del frontend adaptadas a vistas de escritorio y tarjetas móviles.

## Creación de torneos — actividad 3.1.2 (3.3.2)

`POST /api/torneos` permite a un usuario autenticado crear un torneo enviando `{ nombre, cantidad_participantes, contrasena_acceso }`.

El servicio valida que el nombre no esté vacío y que el cupo sea estrictamente **4, 8 o 16**. Genera un **código de acceso alfanumérico único de 6 caracteres** en mayúsculas (ej. `TRN8X2`), persiste el torneo en estado `ESPERANDO_JUGADORES` e **inscribe automáticamente al usuario creador como primer participante**. Responde con `201 Created` informando el ID del torneo, el código generado y los cupos restantes para permitir la redirección inmediata a la sala.

## Ingreso y salida de torneo — actividad 3.1.3 (3.3.3)

`POST /api/torneos/unirse` permite a un jugador incorporarse a un torneo mediante `{ codigo_acceso, contrasena }`.

Normaliza el código a mayúsculas, valida la contraseña si el torneo es privado, comprueba que el usuario no esté inscripto previamente y que el cupo no esté completo. Al completarse el cupo máximo de participantes (ej. 8/8), el torneo cambia automáticamente su estado a `EN_CURSO` y **dispara de forma automática el motor de generación de cruces de la primera ronda**.

`DELETE /api/torneos/{id}/salir` permite a un participante abandonar la sala mientras el torneo se encuentre en estado `ESPERANDO_JUGADORES`, liberando su cupo. Si quien sale es el usuario creador, el torneo se cancela formalmente para todos los inscriptos.

## Sala, detalle y cuadro de llaves — actividad 3.1.4 y 3.1.5 (3.3.4 y 3.3.5)

`GET /api/torneos/{id}` entrega la información integral del torneo: participantes inscriptos con sus nombres de usuario, fecha de ingreso, estado del torneo y la estructura completa del **cuadro de llaves (*bracket*)**.

El cuadro organiza los cruces por rondas sucesivas (**Octavos de final, Cuartos de final, Semifinal y Final**). Cada cruce informa su identificador, ronda, jugador A, jugador B, estado (`PENDIENTE` o `JUGADO`) y el ganador asignado.

El motor de avance de llaves provee:
- `POST /api/torneos/cruces/{id}/iniciar-duelo`: vincula el cruce del torneo con una partida de duelo real entre los dos competidores emparejados.
- `POST /api/torneos/cruces/{id}/resolver`: recibe el ganador del cruce, lo clasifica automáticamente al cruce correspondiente de la ronda siguiente y, si se resolvió el cruce final, consagra al campeón y finaliza el torneo pasando su estado a `FINALIZADO`.

## Sesión JWT y seguridad — actividad 1.2.5

El módulo de seguridad (`app/core/seguridad.py`) centraliza la verificación de identidad y la protección perimetral:

- Los tokens JWT se firman mediante el algoritmo criptográfico `HS256` utilizando la clave `JWT_SECRET` y el tiempo de expiración definido en `JWT_EXPIRATION_MIN` (por defecto 60 minutos).
- El payload del token contiene `sub` con el identificador del usuario, su `rol` (`JUGADOR` o `ADMINISTRADOR`) y la marca de expiración estándar `exp`.
- La dependencia `obtener_usuario_actual` intercepta cada solicitud protegida leyendo el encabezado `Authorization: Bearer <token>`, valida la firma digital, comprueba que no haya expirado y recupera la entidad en la base de datos comprobando que la cuenta esté activa (`esta_habilitado`). Ante cualquier discrepancia responde con código `401 Unauthorized` (`TOKEN_INVALIDO`).
- `requiere_rol(RolUsuario.ADMINISTRADOR)` implementa la defensa en profundidad: rechaza de inmediato con `403 Forbidden` (`ACCESO_DENEGADO`) a cualquier usuario que no posea privilegios administrativos, protegiendo todas las rutas bajo `/api/admin`.

## Autenticación

El controlador `app/routes/autenticacion_router.py` gestiona el acceso bajo el prefijo `/api/auth`:

- `POST /api/auth/registro`: recibe `{ nombre, email, password }`. Valida nombre no vacío, formato de correo válido y contraseña de longitud mínima. Hashea la clave con algoritmos de derivación de claves seguros y verifica la unicidad del email; ante correos ya existentes responde con `409 Conflict` y código `EMAIL_YA_REGISTRADO`. Asigna por defecto el rol `JUGADOR` y devuelve `201 Created` con el perfil del usuario creado (omitiendo hashes y contraseñas).
- `POST /api/auth/login`: recibe `{ email, password }`. Valida las credenciales contra la base de datos; si el correo no existe o la contraseña no coincide, responde con `401 Unauthorized` y código `CREDENCIALES_INVALIDAS`. Si la cuenta fue suspendida, responde con `CUENTA_DESHABILITADA`. Al autenticar exitosamente, retorna `{ access_token, token_type: "bearer" }`.
- `POST /api/auth/logout`: endpoint autenticado para registrar el cierre formal de sesión en el backend.
- Todas las respuestas de error en la API respetan el formato estándar `{ code, message, detail }`, facilitando su consumo y presentación directa en el frontend.

## Estructura y diseño

```text
app/
  core/            configuracion.py, base_datos.py, excepciones.py y seguridad.py
  models/          usuario.py, categoria.py, pregunta.py, partida.py, partida_individual.py, partida_duelo.py, torneo.py, cruce.py y enumeraciones.py
  schemas/         autenticacion_schema.py, usuario_schema.py, categoria_schema.py, pregunta_schema.py, partida_schema.py, duelo_schema.py, torneo_schema.py y comun_schema.py
  repositories/    usuario_repository.py, categoria_repository.py, pregunta_repository.py, partida_repository.py, duelo_repository.py y torneo_repository.py
  services/        autenticacion_service.py, usuario_service.py, categoria_service.py, pregunta_service.py, puntaje_service.py, partida_service.py, duelo_service.py, torneo_service.py y semilla_service.py
  routes/          autenticacion_router.py, usuario_router.py, categoria_router.py, partida_router.py, duelo_router.py, torneo_router.py, salud_router.py y admin/
  main.py          Fábrica FastAPI, CORS, middlewares y OpenAPI schema
tests/             260 pruebas automatizadas con pytest y SQLite en memoria
scripts/           sembrar_datos.py, preguntas_seed.json y utilidades de base de datos
alembic/           Control de versiones y migraciones del esquema relacional
```

Nombres propios del proyecto en español; las variables de entorno, claves de configuración y dependencias de terceros conservan sus convenciones técnicas.

Convenciones verificadas contra `documentacion del proyecto (entregables)/Entregable 2/Convenciones de nombres.docx`:

| Elemento del backend | Convención | Ejemplo del repositorio |
| --- | --- | --- |
| Archivos y módulos | snake_case | `torneo_service.py`, `autenticacion_router.py` |
| Variables y funciones | snake_case | `obtener_usuario_por_id()`, `generar_cruces()` |
| Clases (modelos, schemas) | PascalCase | `Usuario`, `Torneo`, `PreguntaCreate` |
| Constantes | UPPER_SNAKE_CASE | `CONFIGURACION`, `JWT_SECRET` |
| Endpoints / rutas REST | snake_case en minúscula con `/api` | `/api/torneos`, `/api/admin/preguntas` |
| Tablas en BD | snake_case, plural | `usuarios`, `preguntas`, `cruces_torneo` |
| Columnas en BD | snake_case | `fecha_creacion`, `categoria_id` |
| Booleanos | prefijo `es_` / `esta_` / `tiene_` | `esta_habilitado`, `es_correcta` |

En Git se utiliza el flujo de trabajo **GitFlow** con ramas nombradas bajo el formato `tipo/descripcion-corta` (ej. `feature/admin-preguntas`, `fix/admin-preguntas-error`) y Conventional Commits (ej. `feat: agregar generación de cruces de torneo`, `fix: corregir concurrencia en pool de base de datos`). Los Pull Requests se abren siempre hacia `develop` describiendo los cambios y referenciando la tarea de la EDT/WBS correspondiente.

El modelo de datos y las relaciones ORM implementan fielmente el Diagrama de Clases UML del **Entregable 4**, desacoplando los modelos de persistencia de los esquemas DTO de Pydantic v2.

## Verificación

```powershell
# Ejecutar la suite completa de pruebas unitarias y de integración
.venv\Scripts\pytest.exe -v

# Ejecutar con reporte de cobertura de código
.venv\Scripts\pytest.exe --cov=app tests/
```

Las pruebas automatizadas utilizan una base de datos **SQLite en memoria (`sqlite:///:memory:`)** configurada en `tests/conftest.py`. Esto aísla por completo las pruebas del entorno de producción o desarrollo remoto, permitiendo ejecutar la suite de forma veloz, confiable y sin necesidad de servicios externos.

La suite incluye **260 pruebas automatizadas** que cubren:
- Registro, inicio de sesión, hashing seguro y validación de tokens JWT válidos, vencidos y adulterados.
- Control de acceso por roles y rechazo estricto (401 y 403) ante intentos de acceso no autorizado a rutas administrativas.
- Ciclo de vida de partidas individuales, selección aleatoria de preguntas sin repetición y cálculo de puntajes.
- Emparejamiento de duelos en línea, sincronización de turnos y definición de ganadores.
- Creación de torneos con validación de cupos (4, 8, 16), inscripción con contraseña, salida de participantes y disparo automático del bracket.
- Motor de cruces, avance de participantes por ronda y consagración del campeón del torneo.
- Operaciones CRUD completas sobre preguntas, categorías y usuarios en el panel de administración, incluyendo soft-delete y duplicación.
- Validación de contratos JSON y respuestas de error HTTP 422, 404, 409 y 400.
- Idempotencia del proceso de siembra de datos del sistema.

Para verificar manualmente el backend con la base de datos real, iniciar el servidor local con `uvicorn app.main:crear_aplicacion --factory --reload` y acceder a [http://localhost:8000/docs](http://localhost:8000/docs). Desde Swagger UI es posible autenticarse mediante el botón **Authorize** pegando el token JWT obtenido en `/api/auth/login` y probar interactivamente cualquiera de los endpoints del sistema.

