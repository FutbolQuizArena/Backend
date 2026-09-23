# Changelog

## 23/9 [3.1.4] Endpoint listar torneos

- **Capa de presentación (API REST):** Implementación del endpoint `GET /api/torneos` en `app/routes/torneo_router.py` (código `200 OK`), protegido con `obtener_usuario_actual`. Soporta el parámetro de consulta `filtro` (`mios`, `disponibles`, `finalizados`), con valor por defecto `mios` y validación estricta con HTTP 422 ante valores no reconocidos. Documentación OpenAPI exhaustiva con esquema de seguridad `BearerAuth`.
- **Capa de lógica de negocio:** Creación de `listar_torneos` en `app/services/torneo_service.py`, transformando resultados de persistencia en `TorneoListItemResponse`, calculando el flag seguro `tiene_contrasena` (sin exponer credenciales) y restringiendo la visibilidad del `codigo_acceso` exclusivamente a los torneos donde el usuario autenticado es el creador.
- **Capa de persistencia:** Consolidación de métodos de consulta en `app/repositories/torneo_repository.py` (`obtener_por_codigo_acceso` como canónico) e incorporación de consultas optimizadas para evitar problemas de N+1 queries (`listar_por_participante`, `listar_disponibles` y `listar_finalizados_por_participante`), utilizando subqueries escalares correlacionadas para computar `cantidad_participantes_actual`.
- **Esquemas Pydantic:** Creación de `FiltroTorneoEnum` (`mios`, `disponibles`, `finalizados`) y `TorneoListItemResponse` (`id`, `nombre`, `cantidad_participantes`, `cantidad_participantes_actual`, `tiene_contrasena`, `estado`, `fecha_creacion`, `creador_id`, `codigo_acceso` condicional) en `app/schemas/torneo_schema.py`.
- **Testing automatizado:** Suite de pruebas en `tests/test_listar_torneos.py` (9 tests unitarios y de integración) cubriendo filtros `mios`, `disponibles`, `finalizados`, valor por defecto, cálculo exacto de cupo actual, bandera segura de contraseña, control de exposición de código de acceso, validación de filtro inválido (422) y autenticación requerida (401).

## 23/9 [3.1.3] Endpoint ingresar por código

- **Modelo de dominio:** Implementación del método de instancia `Torneo.unirse(usuario, contrasena_ingresada)` en `app/models/torneo.py` según el Diagrama de clases E4, validando estado `ESPERANDO_JUGADORES`, verificación de cupo (`esta_completo()`) y comprobación criptográfica segura de contraseña con `bcrypt.checkpw`.
- **Capa de lógica de negocio:** Creación de `unirse_a_torneo` en `app/services/torneo_service.py` siguiendo el Diagrama de Secuencia Nº3 (pasos 10 a 24): búsqueda por código, prevención de doble inscripción, delegación en `Torneo.unirse()`, persistencia de `ParticipanteTorneo` y transición automática de estado a `EN_CURSO` al completarse el cupo.
- **Capa de persistencia:** Incorporación de los métodos `obtener_por_codigo_acceso`, `actualizar_estado` y `es_participante` en `app/repositories/torneo_repository.py`.
- **Manejo de excepciones de dominio:** Creación de `TorneoNoDisponibleError` (código `TORNEO_NO_DISPONIBLE`, HTTP 400) en `app/core/excepciones.py`, proveyendo una respuesta homogénea ante códigos inexistentes, contraseñas erróneas, torneos completos o torneos en curso, previniendo ataques de enumeración.
- **Esquemas Pydantic:** Creación de `TorneoUnirseRequest` (`codigo_acceso`, `contrasena`) con normalización y validación de código en `app/schemas/torneo_schema.py`.
- **Capa de presentación (API REST):** Incorporación del endpoint `POST /api/torneos/unirse` (código `200 OK`) en `app/routes/torneo_router.py`, protegido con la dependencia `obtener_usuario_actual` y documentado exhaustivamente en OpenAPI.
- **Testing automatizado:** Suite de pruebas en `tests/test_unirse_torneo.py` (11 tests unitarios y de integración) cubriendo unión a torneo sin contraseña (200), torneo con contraseña correcta (200), rechazo por contraseña errónea (400), código inexistente (400), torneo completo (400), torneo no disponible (400), prevención de doble inscripción (400), transición automática a `EN_CURSO` y control de autenticación (401).

## 23/9 [3.1.2] Endpoint crear torneo

- **Capa de presentación (API REST):** Creación del controlador `app/routes/torneo_router.py` implementando el endpoint `POST /api/torneos` (código `201 Created`), protegido mediante la dependencia `obtener_usuario_actual`. Documentación completa en OpenAPI con respuestas 201, 401 y 422, y esquema de seguridad `BearerAuth`.
- **Capa de lógica de negocio:** Creación de `app/services/torneo_service.py` con la función `crear_torneo`, implementando el flujo del Diagrama de Secuencia Nº3 (pasos 1 a 7): asignación de estado `ESPERANDO_JUGADORES`, invocación de `Torneo.generar_codigo_acceso()`, verificación de no colisión, hashing seguro con `bcrypt` de `contrasena_acceso` (opcional), persistencia del torneo e inscripción automática del creador como primer participante (`ParticipanteTorneo`).
- **Capa de persistencia:** Creación de `app/repositories/torneo_repository.py` con métodos `crear`, `agregar_participante`, `obtener_por_id` y `obtener_por_codigo`.
- **Esquemas Pydantic:** Creación de `TorneoCreate` (validando nombre no vacío y `cantidad_participantes` en `{4, 8, 16}`) y `TorneoCreadoResponse` (serialización segura protegiendo contraseña) en `app/schemas/torneo_schema.py`.
- **Integración de rutas:** Registro de `torneo_router` en `app/main.py` con tag `"Torneos"`.
- **Testing automatizado:** Suite de pruebas en `tests/test_crear_torneo.py` (20 tests unitarios y de integración con `TestClient`) cubriendo creación exitosa sin contraseña (201), creación con contraseña hasheada y segura (201), inscripción automática del creador en BD, validaciones de cupo (`422`), validaciones de nombre vacío/ausente (`422`), acceso no autenticado (`401`) y unicidad de código de acceso entre torneos.

## 23/9 [3.1.1] Modelo: Torneo/Participante/Cruce

- **Modelos de dominio y persistencia ORM:** Implementación de las entidades del Módulo 3 en SQLAlchemy respetando el Diagrama de clases E4:
  - `Torneo` (`torneos`): atributos `id`, `nombre`, `cantidad_participantes`, `codigo_acceso` (único e indexado), `contrasena_acceso` (opcional), `estado` (`EstadoTorneo`), `creador_id` (FK a `usuarios.id`) y `fecha_creacion`. Relaciones de composición con `cascade="all, delete-orphan"` hacia `ParticipanteTorneo` y `Cruce`. Métodos de dominio: `generar_codigo_acceso()` (generación segura de código alfanumérico de 6 caracteres) y `esta_completo()` (validación contra cupo). Métodos `unirse()` y `generar_cruces()` declarados para sub-tareas 3.1.3 y 3.2.
  - `ParticipanteTorneo` (`participantes_torneo`): atributos `id`, `usuario_id` (FK a `usuarios.id`), `torneo_id` (FK a `torneos.id`) y `fecha_ingreso` con default `func.now()`. Restricción de unicidad compuesta `(torneo_id, usuario_id)`.
  - `Cruce` (`cruces_torneo`): atributos `id`, `torneo_id` (FK a `torneos.id`), `ronda`, `jugador_a_id` y `jugador_b_id` (FKs a `participantes_torneo.id`), `ganador_id` (FK nullable a `participantes_torneo.id`) y `estado` (`EstadoCruce`). Método `determinar_ganador()` declarado para sub-tarea 3.2.
- **Enumeraciones de dominio:** Definición de `EstadoTorneo` (`ESPERANDO_JUGADORES`, `EN_CURSO`, `FINALIZADO`) y `EstadoCruce` (`PENDIENTE`, `JUGADO`) en `app/models/enumeraciones.py` con tipo `SQLEnum` nativo para PostgreSQL.
- **Esquemas Pydantic:** Creación de `TorneoBase`, `TorneoResponse` (serialización segura para frontend, protegiendo credenciales sensibles al nunca exponer `contrasena_acceso`), `ParticipanteTorneoResponse` y `CruceResponse` en `app/schemas/torneo_schema.py`.
- **Migración de base de datos:** Generación y aplicación de la migración de Alembic `50ca309bd94c_crear_tablas_torneos_participantes_cruces.py` para la creación de las tablas `torneos`, `participantes_torneo`, `cruces_torneo` e índices asociados en PostgreSQL (Supabase), con soporte de rollback para tipos enum.
- **Testing automatizado:** Suite de pruebas en `tests/test_torneo_model.py` (10 tests unitarios) cubriendo persistencia de entidades, valores por defecto, relación con creador, unicidad y generación de código de acceso, verificación de cupo (`esta_completo`), serialización segura sin exponer contraseñas y eliminación en cascada de composición.

## 23/9 [Refactorización] Estandarización de módulos y archivos 

## 21/9 [1.1.6] Endpoint de logout

- **Capa de presentación (API REST):** Implementación del endpoint `POST /api/auth/logout` en `app/routes/auth_router.py` (código `200 OK`), protegido con la dependencia `obtener_usuario_actual`. En un esquema JWT stateless, valida la existencia de una sesión activa antes de confirmar el cierre, siendo la invalidación efectiva responsabilidad del cliente al descartar el token.
- **Esquemas Pydantic comunes:** Creación de `app/schemas/common_schema.py` con `MensajeResponse` para respuestas informativas estándar (`{"mensaje": str}`) sin acoplar el logout a esquemas específicos de entidad.
- **Documentación OpenAPI y Swagger:** Configuración exhaustiva del endpoint con respuestas 200 y 401, y requerimiento de autorización `BearerAuth`.
- **Testing automatizado:** Suite de pruebas en `tests/test_logout.py` (5 tests de integración con `TestClient`) cubriendo logout exitoso (200), ausencia de token (401), token malformado (401), token expirado (401) y flujo integral login -> logout.

## 18/9 [1.1.5] Endpoint edición de perfil

- **Modelo de dominio y mutación:** Incorporación de los métodos de instancia `Usuario.actualizar_perfil(nombre, email)` y `Usuario.cambiar_password(nuevo_password_hash)` en `app/models/usuario.py` para mutación in-place, respetando el Diagrama de clases E4 y el encapsulamiento de datos sensibles.
- **Capa de persistencia:** Implementación de la función `actualizar` en `app/repositories/usuario_repository.py` con `db.commit()` y `db.refresh(usuario)` para sincronizar entidades modificadas.
- **Capa de lógica de negocio:** Creación de `actualizar_perfil_usuario` (soporte de cambio opcional de contraseña validando clave actual) y `cambiar_password_usuario` en `app/services/usuario_service.py` con validación de unicidad de email contra terceros (`EmailYaRegistradoError`, HTTP 409) y autenticación previa de clave actual (`CredencialesInvalidasError`, HTTP 401).
- **Esquemas Pydantic:** Creación de `UsuarioUpdate` (`nombre`, `email`, `password_actual`, `nueva_password`) con validación condicional de contraseña y `CambiarPasswordRequest` en `app/schemas/usuario_schema.py`, reutilizando `UsuarioResponse` para asegurar que nunca se expongan datos sensibles como contraseñas o hashes.
- **Capa de presentación (API REST):** Creación del controlador `app/routes/usuario_router.py` con los endpoints `PATCH /api/usuarios/me` (edición de perfil con cambio de clave opcional) y `PATCH /api/usuarios/me/password` (modal específico de cambio de clave), ambos protegidos mediante `obtener_usuario_actual`.
- **Integración de rutas y OpenAPI:** Registro de `usuario_router` en `app/main.py` y configuración del esquema de seguridad `BearerAuth` en OpenAPI para autorización en Swagger UI.
- **Testing automatizado:** Suite de pruebas en `tests/test_edicion_perfil.py` (14 tests unitarios y de integración con `TestClient`) cubriendo edición exitosa (200), cambio de contraseña opcional en perfil (200/401/422), modal de contraseña (200/401), ausencia de token (401), conflicto de email en uso por otro usuario (409), conservación del email propio (200), validación de esquemas (422), y pruebas de dominio y servicio.

## 18/9 [1.1.4] Middleware de autorización por rol

- **Middleware y dependencias de seguridad:** Creación de `app/core/seguridad.py` implementando el esquema `OAuth2PasswordBearer` (`tokenUrl="/api/auth/login"`), la dependencia `obtener_usuario_actual` (validación de JWT, extracción de identidad y verificación de usuario habilitado) y la fábrica de dependencias `requiere_rol` para autorización basada en roles (RBAC) según el enum `RolUsuario`.
- **Capa de persistencia:** Incorporación del método `obtener_por_id` en `app/repositories/usuario_repository.py` para consulta de usuarios por identificador único.
- **Manejo de excepciones de dominio:** Creación de `TokenInvalidoError` (código `TOKEN_INVALIDO`, HTTP 401) y `AccesoDenegadoError` (código `ACCESO_DENEGADO`, HTTP 403) en `app/core/exceptions.py`, preservando la estructura estándar `{ "code", "message", "detail" }`.
- **Testing automatizado:** Suite de pruebas exhaustiva en `tests/test_seguridad.py` (14 tests unitarios y de integración HTTP vía `TestClient`) validando autenticación Bearer, tokens inválidos/expirados, usuarios deshabilitados o inexistentes, y control de acceso estricto por rol (`JUGADOR` vs `ADMINISTRADOR`).

## 16/9 [1.1.3] Endpoint de login + JWT

- **Modelo de dominio y encapsulamiento:** Incorporación del método de instancia `Usuario.autenticar(password_ingresado)` en `app/models/usuario.py` para validar contraseñas de forma segura con `bcrypt.checkpw`, respetando el diagrama de clases E4 y el encapsulamiento de `password_hash`.
- **Capa de seguridad y tokens:** Creación de `app/services/auth_service.py` con generación de tokens JWT con algoritmo HS256 (`generar_token_jwt` con claims `sub`, `id`, `email`, `rol`, `iat`, `exp`), flujo de autenticación de negocio `autenticar_usuario` (delegando en `usuario.autenticar()`) y función de decodificación y verificación de tokens (`decodificar_token_jwt`).
- **Manejo de excepciones de dominio:** Incorporación de `CredencialesInvalidasError` en `app/core/exceptions.py` (código `CREDENCIALES_INVALIDAS`, HTTP 401) para responder de forma homogénea ante credenciales erróneas o usuarios inexistentes, previniendo ataques de enumeración.
- **Esquemas Pydantic:** Creación de `LoginRequest` (validación de `email` y `password`) y `TokenResponse` (`access_token` y `token_type="bearer"`) en `app/schemas/auth_schema.py`.
- **Capa de presentación (API REST):** Implementación del endpoint `POST /api/auth/login` (código `200 OK`) en `app/routes/auth_router.py`, con documentación exhaustiva para OpenAPI (respuestas 200, 401 y 422).
- **Configuración OpenAPI y Swagger UI:** Configuración de `BearerAuth` (`HTTPBearer`) en el esquema OpenAPI (`app/main.py`) para habilitar el botón interactivo **Authorize** en la documentación Swagger (`/docs`).
- **Configuración central:** Verificación de `JWT_SECRET` y `JWT_EXPIRATION_MIN`, y agregado de `JWT_ALGORITMO = "HS256"` en `app/core/config.py`.
- **Testing automatizado:** Suite de pruebas en `tests/test_login.py` y `tests/test_usuario_model.py` cubriendo login exitoso (200), rechazo uniforme ante credenciales inválidas (401), validación de claims del payload JWT, errores de validación de esquema (422), método `Usuario.autenticar()` y decodificación de tokens válidos, expirados e inválidos.
- **Dependencias:** Incorporación de `pyjwt>=2.8.0` en `requirements.txt`.

## 15/9 [1.1.2] Endpoint de registro

- **Capa de persistencia:** Creación de `app/repositories/usuario_repository.py` con métodos `obtener_por_email` y `crear` utilizando consultas desacopladas de SQLAlchemy.
- **Capa de lógica de negocio:** Creación de `app/services/usuario_service.py` con funciones criptográficas seguras (`hashear_password`, `verificar_password` con `bcrypt`) y flujo de registro `registrar_usuario` con verificación de unicidad de email y asignación automática del rol `JUGADOR`.
- **Manejo de excepciones de dominio:** Incorporación de `EmailYaRegistradoError` en `app/core/exceptions.py` (código `EMAIL_YA_REGISTRADO`, HTTP 409) con respuesta estandarizada `{ "code", "message", "detail" }`.
- **Capa de presentación (API REST):** Creación del router `app/routes/auth_router.py` con endpoint `POST /api/auth/registro` (código `201 Created`), validación con `UsuarioCreate`, respuesta segura vía `UsuarioResponse` y documentación OpenAPI detallada (respuestas 201, 409 y 422).
- **Integración de rutas:** Registro de `auth_router` en `app/main.py` con tag `"Autenticación"`.
- **Testing automatizado:** Suite de pruebas en `tests/test_registro.py` cubriendo registro exitoso (201), emails duplicados (409), validaciones de esquema (422) y verificación de contraseña hasheada en base de datos.
- **Dependencias:** Incorporación de `bcrypt>=4.0.0` en `requirements.txt`.

## 15/9 [1.1.1] Modelo de Usuario (roles)

- **Modelo de dominio:** Creación del modelo ORM `Usuario` en `app/models/usuario.py` mapeado a la tabla `usuarios`, con campos `id`, `nombre`, `email` (único e indexado), `password_hash`, `rol`, `puntaje_total`, `esta_habilitado` y `fecha_alta`.
- **Enumeración de roles:** Definición del enum `RolUsuario` (`JUGADOR`, `ADMINISTRADOR`) en `app/models/enums.py` con tipo `SQLEnum` nativo para PostgreSQL.
- **Esquemas Pydantic:** Creación de `UsuarioBase`, `UsuarioCreate` (recibe contraseña en texto plano para hashing interno en servicios) y `UsuarioResponse` (serialización segura para frontend, protegiendo credenciales sensibles) en `app/schemas/usuario_schema.py`.
- **Migración de base de datos:** Generación y aplicación de la migración de Alembic `d7518665d6ec_crear_tabla_usuarios.py` para la creación de la tabla `usuarios` e índices asociados en PostgreSQL (Supabase).
- **Testing unitario:** Suite de pruebas con Pytest para verificar persistencia del modelo, valores por defecto, unicidad de email, validación de esquemas y exclusión de `password_hash` (`tests/test_usuario_model.py`).
- **Dependencias:** Adición de `email-validator` en `requirements.txt` para la validación de correos con Pydantic.

## 14/9 [0.2.3] Setup inicial del backend (FastAPI + SQLAlchemy + Alembic + Swagger)

- **Arquitectura en capas:** Estructuración modular del backend en `core/`, `models/`, `schemas/`, `repositories/`, `services/` y `routes/`.
- **Configuración y variables de entorno:** Implementación de configuración centralizada con Pydantic Settings (`app/core/config.py`) y plantilla `.env.example`.
- **Base de datos:** Configuración de conexión única a PostgreSQL (Supabase) mediante SQLAlchemy y generador de sesión `get_db` (`app/core/database.py`).
- **Migraciones:** Inicialización y configuración de Alembic (`alembic.ini`, `alembic/env.py`) para control de versiones del esquema de base de datos.
- **Manejo global de excepciones:** Middleware / manejadores de errores con respuesta JSON unificada bajo la estructura `{ "error": { "code", "message", "detail" } }` (`app/core/exceptions.py`).
- **Endpoint de verificación:** Implementación de la ruta `GET /api/health` para comprobar el estado y conectividad del servicio (`app/routes/salud_router.py`).
- **Testing:** Configuración de suite de pruebas con Pytest, fixtures para el cliente de pruebas (`tests/conftest.py`) y tests automatizados para el endpoint de salud (`tests/test_salud.py`).
- **Gestión del proyecto:** Archivos de dependencias (`requirements.txt`), reglas de exclusión (`.gitignore`) y documentación base (`README.md`).