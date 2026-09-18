# Changelog

## 18/9 [1.1.5] Endpoint edición de perfil

- **Modelo de dominio y mutación:** Incorporación del método de instancia `Usuario.actualizar_perfil(nombre, email)` en `app/models/usuario.py` para actualizar datos in-place, respetando el Diagrama de clases E4 y manteniendo la encapsulación en la entidad.
- **Capa de persistencia:** Implementación de la función `actualizar` en `app/repositories/usuario_repository.py` con `db.commit()` y `db.refresh(usuario)` para sincronizar entidades modificadas.
- **Capa de lógica de negocio:** Creación de `actualizar_perfil_usuario` en `app/services/usuario_service.py` con validación de unicidad de email contra terceros (`EmailYaRegistradoError`, HTTP 409), soporte de conservación del email propio y delegación en el modelo.
- **Esquemas Pydantic:** Creación de `UsuarioUpdate` (`nombre`, `email`) en `app/schemas/usuario_schema.py` y reutilización de `UsuarioResponse` para asegurar que nunca se expongan datos sensibles como contraseñas o hashes.
- **Capa de presentación (API REST):** Creación del controlador `app/routes/usuario_router.py` con el endpoint `PATCH /api/usuarios/me` (código `200 OK`), protegido mediante la inyección de dependencias con `obtener_usuario_actual`.
- **Integración de rutas y OpenAPI:** Registro de `usuario_router` en `app/main.py` y configuración refinada del esquema de seguridad `BearerAuth` en OpenAPI para permitir autorización fluida con token JWT en Swagger UI.
- **Testing automatizado:** Suite de pruebas en `tests/test_edicion_perfil.py` (8 tests unitarios y de integración con `TestClient`) cubriendo edición exitosa (200), ausencia de token (401), conflicto de email en uso por otro usuario (409), conservación del email propio (200), validación de esquemas (422), y pruebas de dominio y servicio.

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