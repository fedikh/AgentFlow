"""
Data Agent Service — LangChain Pandas Agent with Spaces.
Same architecture as RAG: Spaces → Files → Chat

Storage: filesystem (no database tables needed)
  uploads/data_agent/{user_id}/{space_id}/
    ├── space.json
    ├── {file_id}.csv
    └── {file_id}.meta.json
"""
import os
import json
import uuid
import shutil
import logging
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
            # Count files
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
# Files
# ══════════════════════════════════════════

async def upload_file(user, space_id: str, file: UploadFile) -> dict:
    _get_space(user, space_id)  # verify space exists

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
# Query — LangChain Pandas Agent
# ══════════════════════════════════════════

def query_data(user, space_id: str, question: str) -> dict:
    """Query ALL files in the space using LangChain Pandas Agent."""
    _get_space(user, space_id)
    files = list_files(user, space_id)

    if not files:
        raise HTTPException(400, "No files in this space. Upload a CSV or Excel first.")

    # Load all DataFrames in the space
    dfs = []
    file_names = []
    for f in files:
        try:
            df = _load_df(f["file_path"])
            dfs.append(df)
            file_names.append(f["file_name"])
        except Exception as e:
            logger.warning(f"[DATA_AGENT] Failed to load {f['file_name']}: {e}")

    if not dfs:
        raise HTTPException(500, "Could not load any files")

    logger.info(f"[DATA_AGENT] Query: \"{question}\" on {len(dfs)} file(s): {file_names}")

    try:
        from langchain_groq import ChatGroq
        from langchain_experimental.agents import create_pandas_dataframe_agent
        from langchain_experimental.agents.agent_toolkits.pandas.base import AgentType
        from app.config import settings

        llm = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            temperature=0,
        )
        # Single file → single df, multiple files → list of dfs
        df_input = dfs[0] if len(dfs) == 1 else dfs

        agent = create_pandas_dataframe_agent(
            llm=llm,
            df=df_input,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            allow_dangerous_code=True,
            prefix=f"""You are a data analyst. You have access to pandas DataFrame(s).
Files loaded: {', '.join(file_names)}
{"The DataFrame is called `df`." if len(dfs) == 1 else f"DataFrames are called df1, df2, ... df{len(dfs)}."}

Rules:
- Use pandas operations for exact answers
- For numbers, give the exact result
- For listings, show relevant rows
- Be concise and clear
""",
        )

        response = agent.invoke({"input": question})
        output = response.get("output", str(response))

        logger.info(f"[DATA_AGENT] Answer: {str(output)[:200]}")

        answer = _parse_output(output)

        return {
            "question": question,
            "answer": answer["text"],
            "data": answer.get("data"),
            "type": answer["type"],
            "files": file_names,
        }

    except ImportError as e:
        raise HTTPException(500, f"Missing: {e}. Run: pip install langchain langchain-experimental langchain-groq")
    except Exception as e:
        logger.error(f"[DATA_AGENT] Query failed: {e}")
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


def _parse_output(output: str) -> dict:
    try:
        num = float(output.strip().replace(",", ""))
        return {"type": "number", "text": str(num), "data": None}
    except (ValueError, AttributeError):
        pass
    if "|" in output and "---" in output:
        return {"type": "dataframe", "text": output, "data": None}
    return {"type": "text", "text": output, "data": None}