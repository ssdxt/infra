import logging
from typing import Any
from urllib.parse import quote_plus

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, text

from src.config.agents import AGENT_LLM_MAP
from src.config.loader import get_str_env
from src.llms.llm import get_llm_by_type
from src.subagents.rag.retriever import Resource
from src.subagents.tabular.toolkit import SQLDatabaseToolkit

logger = logging.getLogger(__name__)


PROVIDER_DICT = {
    "sqlite": "sqlite:///{database}",
    "mysql": "mysql+pymysql://{user}:{password}@{host}:{port}/{database}",
    "postgresql": "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}",
}

def _normalize_agent_name(agent) -> str:
    if isinstance(agent, str):
        return agent.strip().lower()
    if isinstance(agent, dict):
        for key in ("name", "type", "key", "id"):
            value = agent.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return ""


def _select_tabular_resource(resources: list[Resource]) -> Resource:
    if not resources:
        raise ValueError("No resources provided for tabular execution.")

    for resource in resources:
        agent_name = _normalize_agent_name(resource.agent)
        if agent_name in {"tabular", "tabuler"}:
            return resource

    for resource in resources:
        if resource.uri:
            return resource

    raise ValueError("No tabular resource with a usable uri was found.")


def _build_uri(
    provider: str,
    *,
    host: str = "",
    port: str = "",
    user: str = "",
    password: str = "",
    database: str = "",
) -> str:
    provider = (provider or "mysql").strip().lower()
    uri_template = PROVIDER_DICT.get(provider)
    if not uri_template:
        raise ValueError(f"Unsupported TABULAR_PROVIDER: {provider}")

    if provider == "sqlite":
        if not database:
            raise ValueError("SQLite connection requires a database path.")
        return uri_template.format(database=database)

    uri = uri_template.format(
        user=quote_plus(user),
        password=quote_plus(password),
        host=host,
        port=port,
        database=database,
    )
    if provider == "mysql":
        uri = f"{uri}?charset=utf8mb4"
    return uri


def _build_registry_uri() -> str:
    return _build_uri(
        get_str_env("TABULAR_PROVIDER", "mysql"),
        host=get_str_env("TABULAR_HOST", "127.0.0.1"),
        port=get_str_env("TABULAR_PORT", "3306"),
        user=get_str_env("TABULAR_USER", "root"),
        password=get_str_env("TABULAR_PASSWORD", ""),
        database=get_str_env("TABULAR_DATABASE", ""),
    )


def _get_registry_table() -> str:
    table_name = get_str_env("TABULAR_TABLE", "tabuler_connector").strip()
    if not table_name:
        raise ValueError("TABULAR_TABLE is empty.")
    return table_name


def _resolve_target_uri(record: dict[str, Any]) -> str:
    provider = str(record.get("provider") or "mysql")
    host = str(record.get("host") or "")
    port = str(record.get("port") or "")
    user = str(record.get("user") or "")
    password = str(record.get("password") or "")
    database = str(record.get("database") or "")
    if not database:
        raise ValueError(
            "Resolved tabular connector record is missing database information."
        )
    return _build_uri(
        provider,
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


def _lookup_connector_record(token: str) -> tuple[dict[str, Any], str]:
    registry_uri = _build_registry_uri()
    table_name = _get_registry_table()
    engine = create_engine(registry_uri, pool_pre_ping=True, pool_recycle=3600)

    with engine.connect() as conn:
        sql = text(f"SELECT * FROM `{table_name}` WHERE `token`= '{token}' LIMIT 1")
        row = conn.execute(sql, {"token": token}).mappings().first()
        if not row:
            raise LookupError(
                f"Token '{token}' was not found in tabular registry table '{table_name}'."
            )
        return dict(row), table_name


def get_sql_toolkit(resources: list[Resource]) -> list:
    """Build SQL tools from the tabular resource token."""
    resource = _select_tabular_resource(resources)
    token = resource.uri.strip()
    if not token:
        raise ValueError("Tabular resource uri is empty.")

    connector_record, table_name = _lookup_connector_record(token)
    uri = _resolve_target_uri(connector_record)

    db = SQLDatabase.from_uri(uri)
    toolkit = SQLDatabaseToolkit(db=db, llm=get_llm_by_type(AGENT_LLM_MAP["tabular"]))
    sql_tools = toolkit.get_tools()
    logger.info(
        "Loaded %d SQL tools from tabular resource '%s' via connector table '%s'.",
        len(sql_tools),
        resource.title,
        table_name,
    )
    return sql_tools
