# FutbolQuiz Arena - Backend API

Backend para la plataforma de trivias y torneos de fútbol **FutbolQuiz Arena**, desarrollado con **FastAPI**, **SQLAlchemy**, **PostgreSQL** (Supabase), **Pydantic** y **Pytest**.

---

## Arquitectura del Proyecto

El sistema adopta una **arquitectura en 3 capas**, manteniendo desacoplada la presentación, las reglas de negocio y el acceso a datos.

```
app/
├── main.py              # Inicialización de FastAPI (título, versión, CORS, middlewares y routers)
├── core/
│   ├── configuracion.py # Configuración centralizada y lectura de variables de entorno (.env)
│   ├── base_datos.py    # Conexión única a PostgreSQL / Supabase, sesión y Base declarativa
│   ├── excepciones.py   # Manejadores globales de error con estructura fija {code, message, detail}
│   └── seguridad.py     # Dependencias de seguridad, extracción de JWT y RBAC
├── models/              # Modelos SQLAlchemy para la base de datos
├── schemas/             # Esquemas Pydantic para validación de entrada y serialización
├── repositories/        # Capa de persistencia y consultas a base de datos
├── services/            # Capa de lógica de negocio pura
└── routes/              # Controladores y endpoints REST (/api/...)
tests/                   # Pruebas unitarias y de integración con Pytest
alembic/                 # Migraciones de esquema de base de datos
.env.example             # Plantilla de variables de entorno requeridas
requirements.txt         # Dependencias del proyecto
```

---

## Convenciones de Nombres Oficiales

Para mantener coherencia estricta en el equipo, **todo el backend se codifica en español**:

- **Archivos y módulos**: `snake_case` en español (ej: `torneo_service.py`, `autenticacion_router.py`, `usuario_repository.py`).
- **Variables y funciones**: `snake_case` en español (ej: `obtener_usuario_por_id()`, `verificar_salud()`).
- **Clases (modelos, schemas)**: `PascalCase` en español (ej: `Usuario`, `Torneo`, `PreguntaSchema`).
- **Constantes**: `UPPER_SNAKE_CASE` en español (ej: `MAX_JUGADORES_TORNEO`, `CONFIGURACION`).
- **Endpoints REST**: `snake_case` minúscula en español con prefijo `/api` (ej: `/api/torneos`, `/api/partidas/{id}/resultado`).
- **Tablas en BD**: `snake_case` plural en español (ej: `usuarios`, `cruces_torneo`).
- **Columnas en BD**: `snake_case` en español (ej: `fecha_creacion`, `esta_habilitado`).
- **Booleanos**: Siempre con prefijo `es_` / `esta_` / `tiene_` (ej: `esta_habilitado`, `es_correcta`).
- **Estructura fija de errores**: Todas las respuestas con código HTTP $\ge 400$ devuelven:
  ```json
  {
    "code": "CODIGO_ERROR",
    "message": "Descripción amigable del error",
    "detail": "Detalle técnico o null"
  }
  ```

---

## Puesta en Marcha Local

### 1. Clonar el repositorio y posicionarse en la rama de trabajo

```bash
git clone <URL_DEL_REPOSITORIO>
cd Backend
git checkout feature/backend-setup
```

### 2. Crear y activar el entorno virtual

En **Windows (PowerShell)**:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

En **Windows (CMD)**:
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

En **Linux / macOS**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia el archivo `.env.example` a `.env`:

En **PowerShell**:
```powershell
Copy-Item .env.example .env
```

En **Bash**:
```bash
cp .env.example .env
```

Edita `.env` con las credenciales de tu base de datos de Supabase o PostgreSQL local:
```ini
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/[DATABASE]
JWT_SECRET=tu_clave_secreta_jwt
JWT_EXPIRATION_MIN=60
```

### 5. Iniciar el servidor local

```bash
uvicorn app.main:app --reload
```

El servidor quedará disponible en `http://127.0.0.1:8000`.

---

## 📖 Documentación Interactiva (Swagger / OpenAPI)

Con el servidor en ejecución, podés acceder a:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Esquema OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Ejecutar Pruebas Automatizadas

Las pruebas utilizan SQLite en memoria (`sqlite:///:memory:`) para aislar los tests de la base de datos remota:

```bash
pytest -v
```

Para ver la cobertura:
```bash
pytest --cov=app tests/
```

---

## Flujo de Trabajo GitFlow

El equipo trabaja bajo el modelo **GitFlow**:

1. `main`: Contiene el código en estado de producción o entregas aprobadas. No se commitea directamente.
2. `develop`: Rama principal de integración donde confluyen los desarrollos terminados.
3. `feature/<nombre-feature>`:
   - Se crea a partir de `develop`:
     ```bash
     git checkout develop
     git pull origin develop
     git checkout -b feature/nombre-de-la-funcionalidad
     ```
   - Al finalizar, se hace push y se abre un **Pull Request hacia `develop`** (nunca directo a `main`).
   - Requiere revisión de pares antes de ser fusionada en `develop`.
