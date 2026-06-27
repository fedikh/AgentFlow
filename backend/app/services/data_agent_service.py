"""
Data Agent Service — LangChain Agents for CSV/Excel + Database.

CSV/Excel: LangChain Pandas Agent (reads DataFrame, writes Python)
Database:  LangChain SQL Agent (connects to DB, writes SQL)
Charts:    matplotlib → base64 image → displayed in frontend

Storage: filesystem (no database tables needed)
  uploads/data_agent/{user_id}/{space_id}/
    ├── space.json
    ├── database.json (if connected)
    ├── {file_id}.csv
    └── {file_id}.meta.json
"""
import os
import json
import uuid
import shutil
import logging
import base64
import pandas as pd
from datetime import datetime
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join("uploads", "data_agent")
os.makedirs(DATA_DIR, exist_ok=True)

SUPPORTED = {".csv", ".xlsx", ".xls"}


# ══════════════════════════════════════════
# Spaces
# ══════════════════════════════════════════

def create_space(user, name: str, description: str, department_id: str) -> dict:
    space_id = str(uuid.uuid4())
    space_dir = _space_dir(user, space_id)
    os.makedirs(space_dir, exist_ok=True)

    space = {
        "id": space_id,
        "name": name,
        "description": description,
        "department_id": department_id,
        "user_id": str(user.id),
        "created_at": datetime.utcnow().isoformat(),
        "num_files": 0,
    }

    with open(os.path.join(space_dir, "space.json"), "w") as f:
        json.dump(space, f, ensure_ascii=False, indent=2)

    logger.info(f"[DATA_AGENT] Space created: {name}")
    return space


def list_spaces(user) -> list:
    user_dir = os.path.join(DATA_DIR, str(user.id))
    if not os.path.exists(user_dir):
        return []

    spaces = []
    for name in os.listdir(user_dir):
        space_file = os.path.join(user_dir, name, "space.json")
        if os.path.isfile(space_file):
            with open(space_file) as f:
                space = json.load(f)
            space["num_files"] = len([fn for fn in os.listdir(os.path.join(user_dir, name)) if fn.endswith(".meta.json")])
            spaces.append(space)

    spaces.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return spaces


def delete_space(user, space_id: str) -> dict:
    space_dir = _space_dir(user, space_id)
    space = _get_space(user, space_id)
    if os.path.exists(space_dir):
        shutil.rmtree(space_dir)
    logger.info(f"[DATA_AGENT] Space deleted: {space['name']}")
    return {"message": f"Deleted space '{space['name']}'"}


# ══════════════════════════════════════════
# Files (CSV/Excel)
# ══════════════════════════════════════════

async def upload_file(user, space_id: str, file: UploadFile) -> dict:
    _get_space(user, space_id)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED:
        raise HTTPException(400, f"Supported: {', '.join(SUPPORTED)}")

    content = await file.read()
    file_id = str(uuid.uuid4())
    space_dir = _space_dir(user, space_id)
    file_path = os.path.join(space_dir, f"{file_id}{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        df = _load_df(file_path)
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(400, f"Cannot read file: {e}")

    meta = {
        "id": file_id,
        "space_id": space_id,
        "file_name": file.filename,
        "file_type": ext.replace(".", "").upper(),
        "file_path": os.path.abspath(file_path),
        "file_size": len(content),
        "num_rows": len(df),
        "num_cols": len(df.columns),
        "columns": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "uploaded_at": datetime.utcnow().isoformat(),
    }

    with open(os.path.join(space_dir, f"{file_id}.meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    logger.info(f"[DATA_AGENT] Uploaded {file.filename}: {len(df)}×{len(df.columns)} to space {space_id}")
    return meta


def list_files(user, space_id: str) -> list:
    _get_space(user, space_id)
    space_dir = _space_dir(user, space_id)
    files = []
    for fname in os.listdir(space_dir):
        if fname.endswith(".meta.json"):
            with open(os.path.join(space_dir, fname)) as f:
                files.append(json.load(f))
    files.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
    return files


def preview_file(user, space_id: str, file_id: str) -> dict:
    meta = _get_file_meta(user, space_id, file_id)
    df = _load_df(meta["file_path"])
    preview_df = df.head(10)
    return {
        "file_name": meta["file_name"],
        "num_rows": meta["num_rows"],
        "num_cols": meta["num_cols"],
        "columns": meta["columns"],
        "preview": json.loads(preview_df.to_json(orient="records", default_handler=str)),
    }


def get_schema(user, space_id: str, file_id: str) -> dict:
    meta = _get_file_meta(user, space_id, file_id)
    df = _load_df(meta["file_path"])
    schema = []
    for col in df.columns:
        info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "non_null": int(df[col].count()),
            "null_count": int(df[col].isnull().sum()),
            "unique": int(df[col].nunique()),
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            info["min"] = round(float(df[col].min()), 2) if not df[col].empty else None
            info["max"] = round(float(df[col].max()), 2) if not df[col].empty else None
            info["mean"] = round(float(df[col].mean()), 2) if not df[col].empty else None
        else:
            info["sample_values"] = [str(v) for v in df[col].dropna().head(3).tolist()]
        schema.append(info)
    return {
        "file_name": meta["file_name"],
        "num_rows": meta["num_rows"],
        "num_cols": meta["num_cols"],
        "columns": schema,
    }


def delete_file(user, space_id: str, file_id: str) -> dict:
    meta = _get_file_meta(user, space_id, file_id)
    space_dir = _space_dir(user, space_id)
    if os.path.exists(meta["file_path"]):
        os.unlink(meta["file_path"])
    meta_path = os.path.join(space_dir, f"{file_id}.meta.json")
    if os.path.exists(meta_path):
        os.unlink(meta_path)
    return {"message": f"Deleted {meta['file_name']}"}


# ══════════════════════════════════════════
# Query CSV/Excel — LangChain Pandas Agent + Charts
# ══════════════════════════════════════════

def query_data(user, space_id: str, question: str) -> dict:
    """Query files using LangChain Pandas Agent. Supports charts."""
    _get_space(user, space_id)
    files = list_files(user, space_id)

    if not files:
        raise HTTPException(400, "No files in this space. Upload a CSV or Excel first.")

    dfs = []
    file_names = []
    for f in files:
        try:
            dfs.append(_load_df(f["file_path"]))
            file_names.append(f["file_name"])
        except Exception as e:
            logger.warning(f"[DATA_AGENT] Failed to load {f['file_name']}: {e}")

    if not dfs:
        raise HTTPException(500, "Could not load any files")

    logger.info(f"[DATA_AGENT] Query: \"{question}\" on {len(dfs)} file(s): {file_names}")

    is_chart = _is_chart_request(question)

    try:
        from langchain_groq import ChatGroq
        from langchain_experimental.agents import create_pandas_dataframe_agent
        from app.config import settings

        llm = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            temperature=0,
        )

        df_input = dfs[0] if len(dfs) == 1 else dfs

        prefix = f"""You are a data analyst. You have access to pandas DataFrame(s).
Files loaded: {', '.join(file_names)}
{"The DataFrame is called `df`." if len(dfs) == 1 else f"DataFrames are called df1, df2, ... df{len(dfs)}."}

Rules:
- Use pandas operations for exact answers
- For numbers, give the exact result
- For listings, show relevant rows
- Be concise and clear
"""
        if is_chart:
            prefix += """
The user wants a CHART. You MUST:
1. Use matplotlib to create the chart
2. Save it with: import tempfile; plt.savefig(os.path.join(tempfile.gettempdir(), 'agent_chart.png'), dpi=100, bbox_inches='tight')
3. Call plt.close()
4. Then say "Chart saved successfully"
Use clear labels, title, and colors. Use a clean style.
"""

        agent = create_pandas_dataframe_agent(
            llm=llm,
            df=df_input,
            agent_type="zero-shot-react-description",
            verbose=True,
            allow_dangerous_code=True,
            prefix=prefix,
        )

        response = agent.invoke({"input": question})
        output = response.get("output", str(response))

        # Check if a chart was generated
        chart_base64 = None
        import tempfile
        chart_path = os.path.join(tempfile.gettempdir(), "agent_chart.png")
        if os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                chart_base64 = base64.b64encode(f.read()).decode("utf-8")
            os.unlink(chart_path)
            logger.info("[DATA_AGENT] Chart generated")

        answer = _parse_output(output)
        if chart_base64:
            answer["type"] = "chart"
            answer["chart"] = chart_base64

        logger.info(f"[DATA_AGENT] Answer: {str(output)[:200]}")

        return {
            "question": question,
            "answer": answer["text"],
            "data": answer.get("data"),
            "type": answer["type"],
            "chart": answer.get("chart"),
            "files": file_names,
        }

    except ImportError as e:
        raise HTTPException(500, f"Missing: {e}. Run: pip install langchain langchain-experimental langchain-groq")
    except Exception as e:
        logger.error(f"[DATA_AGENT] Query failed: {e}")
        raise HTTPException(500, f"Query failed: {str(e)}")


# ══════════════════════════════════════════
# Database Connector
# ══════════════════════════════════════════

def connect_database(user, space_id: str, conn_info: dict) -> dict:
    """Connect to a database, list tables, save connection info."""
    _get_space(user, space_id)
    space_dir = _space_dir(user, space_id)

    db_type = conn_info.get("db_type", "postgresql")
    host = conn_info.get("host", "localhost")
    port = conn_info.get("port", "5432")
    database = conn_info.get("database", "")
    username = conn_info.get("username", "")
    password = conn_info.get("password", "")

    if db_type == "sqlite":
        db_url = f"sqlite:///{database}"
    else:
        db_url = f"{db_type}://{username}:{password}@{host}:{port}/{database}"

    try:
        from sqlalchemy import create_engine, inspect
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        engine.dispose()
    except Exception as e:
        raise HTTPException(400, f"Connection failed: {str(e)}")

    db_info = {
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "db_url": db_url,
        "tables": tables,
        "connected": True,
    }

    with open(os.path.join(space_dir, "database.json"), "w") as f:
        json.dump(db_info, f, ensure_ascii=False, indent=2)

    logger.info(f"[DATA_AGENT] Connected to {db_type}://{host}:{port}/{database} — {len(tables)} tables")

    return {
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "tables": tables,
        "connected": True,
    }


def get_database_info(user, space_id: str) -> dict:
    """Get saved database connection info."""
    _get_space(user, space_id)
    space_dir = _space_dir(user, space_id)
    db_path = os.path.join(space_dir, "database.json")

    if not os.path.exists(db_path):
        return {"connected": False}

    with open(db_path) as f:
        return json.load(f)


def disconnect_database(user, space_id: str) -> dict:
    """Remove database connection."""
    _get_space(user, space_id)
    space_dir = _space_dir(user, space_id)
    db_path = os.path.join(space_dir, "database.json")

    if os.path.exists(db_path):
        os.unlink(db_path)

    return {"message": "Database disconnected"}


def get_table_preview(user, space_id: str, table_name: str) -> dict:
    """Preview first 10 rows of a database table."""
    db_info = get_database_info(user, space_id)
    if not db_info.get("connected"):
        raise HTTPException(400, "No database connected")

    if table_name not in db_info.get("tables", []):
        raise HTTPException(404, f"Table '{table_name}' not found")

    try:
        df = _load_table(db_info["db_url"], table_name, limit=10)
        return {
            "table_name": table_name,
            "num_rows": _count_rows(db_info["db_url"], table_name),
            "num_cols": len(df.columns),
            "columns": df.columns.tolist(),
            "preview": json.loads(df.to_json(orient="records", default_handler=str)),
        }
    except Exception as e:
        raise HTTPException(500, f"Preview failed: {str(e)}")


def get_table_schema(user, space_id: str, table_name: str) -> dict:
    """Get column names, types for a table."""
    db_info = get_database_info(user, space_id)
    if not db_info.get("connected"):
        raise HTTPException(400, "No database connected")

    try:
        from sqlalchemy import create_engine, inspect
        engine = create_engine(db_info["db_url"])
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        engine.dispose()

        schema = []
        for col in columns:
            schema.append({
                "name": col["name"],
                "dtype": str(col["type"]),
                "nullable": col.get("nullable", True),
            })

        return {
            "table_name": table_name,
            "num_rows": _count_rows(db_info["db_url"], table_name),
            "num_cols": len(schema),
            "columns": schema,
        }
    except Exception as e:
        raise HTTPException(500, f"Schema failed: {str(e)}")


def get_database_schema(user, space_id: str) -> dict:
    """Get full database schema with tables, columns, and relationships."""
    db_info = get_database_info(user, space_id)
    if not db_info.get("connected"):
        raise HTTPException(400, "No database connected")

    try:
        from sqlalchemy import create_engine, inspect
        engine = create_engine(db_info["db_url"])
        inspector = inspect(engine)

        tables = []
        relationships = []

        for table_name in inspector.get_table_names():
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": False,
                })

            pk = inspector.get_pk_constraint(table_name)
            pk_cols = pk.get("constrained_columns", []) if pk else []
            for col in columns:
                if col["name"] in pk_cols:
                    col["primary_key"] = True

            for fk in inspector.get_foreign_keys(table_name):
                for i, col_name in enumerate(fk.get("constrained_columns", [])):
                    ref_table = fk.get("referred_table", "")
                    ref_col = fk["referred_columns"][i] if i < len(fk.get("referred_columns", [])) else ""
                    relationships.append({
                        "from_table": table_name,
                        "from_column": col_name,
                        "to_table": ref_table,
                        "to_column": ref_col,
                    })

            row_count = _count_rows(db_info["db_url"], table_name)

            tables.append({
                "name": table_name,
                "columns": columns,
                "row_count": row_count,
                "pk_columns": pk_cols,
            })

        engine.dispose()

        return {
            "database": db_info.get("database", ""),
            "db_type": db_info.get("db_type", ""),
            "tables": tables,
            "relationships": relationships,
            "total_tables": len(tables),
            "total_relationships": len(relationships),
        }
    except Exception as e:
        raise HTTPException(500, f"Schema failed: {str(e)}")


def query_database(user, space_id: str, question: str, tables: list = None) -> dict:
    """Query database using LangChain SQL Agent."""
    db_info = get_database_info(user, space_id)
    if not db_info.get("connected"):
        raise HTTPException(400, "No database connected")

    logger.info(f"[DATA_AGENT] DB Query: \"{question}\"")

    try:
        from langchain_groq import ChatGroq
        from langchain_community.utilities import SQLDatabase
        from langchain_community.agent_toolkits import create_sql_agent
        from app.config import settings

        llm = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            temperature=0,
        )

        if tables:
            sql_db = SQLDatabase.from_uri(db_info["db_url"], include_tables=tables)
        else:
            sql_db = SQLDatabase.from_uri(db_info["db_url"])

        agent = create_sql_agent(
            llm=llm,
            db=sql_db,
            agent_type="zero-shot-react-description",
            verbose=True,
            handle_parsing_errors=True,
        )

        response = agent.invoke({"input": question})
        output = response.get("output", str(response))

        logger.info(f"[DATA_AGENT] DB Answer: {str(output)[:200]}")

        return {
            "question": question,
            "answer": output,
            "type": "text",
            "source": "database",
            "database": db_info.get("database", ""),
        }

    except ImportError as e:
        raise HTTPException(500, f"Missing: {e}. Run: pip install langchain-community")
    except Exception as e:
        logger.error(f"[DATA_AGENT] DB query failed: {e}")
        raise HTTPException(500, f"Query failed: {str(e)}")


# ══════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════

def _space_dir(user, space_id: str) -> str:
    return os.path.join(DATA_DIR, str(user.id), space_id)


def _get_space(user, space_id: str) -> dict:
    space_file = os.path.join(_space_dir(user, space_id), "space.json")
    if not os.path.exists(space_file):
        raise HTTPException(404, "Space not found")
    with open(space_file) as f:
        return json.load(f)


def _get_file_meta(user, space_id: str, file_id: str) -> dict:
    space_dir = _space_dir(user, space_id)
    meta_path = os.path.join(space_dir, f"{file_id}.meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(404, "File not found")
    with open(meta_path) as f:
        return json.load(f)


def _load_df(file_path: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found on disk")
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path, engine="openpyxl")
    raise HTTPException(400, f"Unsupported: {ext}")


def _load_table(db_url: str, table_name: str, limit: int = None) -> pd.DataFrame:
    from sqlalchemy import create_engine
    engine = create_engine(db_url)
    query = f"SELECT * FROM {table_name}"
    if limit:
        query += f" LIMIT {limit}"
    df = pd.read_sql(query, engine)
    engine.dispose()
    return df


def _count_rows(db_url: str, table_name: str) -> int:
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        count = result.scalar()
    engine.dispose()
    return count


def _parse_output(output: str) -> dict:
    try:
        num = float(output.strip().replace(",", ""))
        return {"type": "number", "text": str(num), "data": None}
    except (ValueError, AttributeError):
        pass
    if "|" in output and "---" in output:
        return {"type": "dataframe", "text": output, "data": None}
    return {"type": "text", "text": output, "data": None}


def _is_chart_request(question: str) -> bool:
    chart_words = {
        "plot", "chart", "graph", "histogram", "bar chart", "pie chart",
        "line chart", "scatter", "visualize", "visualization", "draw",
        "graphique", "diagramme", "tracer", "courbe",
    }
    q = question.lower()
    return any(w in q for w in chart_words)