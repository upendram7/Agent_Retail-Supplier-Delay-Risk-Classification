from __future__ import annotations

import json
import logging
import math
import os
import random
import resource
import sqlite3
import threading
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)
_init_lock = threading.Lock()
_trace_context: ContextVar[dict[str, Any]] = ContextVar("trace_context", default={})


def current_trace_context() -> dict[str, Any]:
    return _trace_context.get()


def set_trace_context(context: dict[str, Any]) -> Any:
    return _trace_context.set(context)


def reset_trace_context(token: Any) -> None:
    _trace_context.reset(token)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, session_id TEXT NOT NULL,
    conversation_id TEXT, user_id TEXT, endpoint TEXT NOT NULL, environment TEXT NOT NULL,
    started_at TEXT NOT NULL, ended_at TEXT, duration_ms REAL, status TEXT, error_type TEXT
);
CREATE TABLE IF NOT EXISTS spans (
    span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, parent_span_id TEXT,
    request_id TEXT NOT NULL, session_id TEXT NOT NULL, agent_run_id TEXT,
    span_name TEXT NOT NULL, span_type TEXT NOT NULL, service_name TEXT NOT NULL,
    agent_name TEXT, model_name TEXT, tool_name TEXT, started_at TEXT NOT NULL,
    ended_at TEXT, duration_ms REAL, status TEXT NOT NULL, input_json TEXT,
    output_json TEXT, error TEXT, metadata_json TEXT,
    FOREIGN KEY(trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS application_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, level TEXT NOT NULL,
    service TEXT NOT NULL, environment TEXT NOT NULL, request_id TEXT, trace_id TEXT,
    session_id TEXT, agent_name TEXT, tool_name TEXT, model_name TEXT, endpoint TEXT,
    message TEXT NOT NULL, latency_ms REAL, status TEXT, error_type TEXT,
    structured_json TEXT
);
CREATE TABLE IF NOT EXISTS request_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT NOT NULL,
    trace_id TEXT NOT NULL, session_id TEXT NOT NULL, endpoint TEXT NOT NULL, method TEXT NOT NULL,
    status_code INTEGER NOT NULL, status TEXT NOT NULL, latency_ms REAL NOT NULL,
    environment TEXT NOT NULL, error_type TEXT
);
CREATE TABLE IF NOT EXISTS llm_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, agent_run_id TEXT, agent_name TEXT,
    provider TEXT NOT NULL, model_name TEXT NOT NULL, prompt_version TEXT,
    system_prompt_version TEXT, prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0, reasoning_tokens INTEGER,
    latency_ms REAL NOT NULL DEFAULT 0, time_to_first_token_ms REAL,
    tokens_per_second REAL, retry_count INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
    error TEXT, estimated_cost REAL NOT NULL DEFAULT 0, environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, agent_run_id TEXT NOT NULL, agent_name TEXT NOT NULL,
    start_time TEXT NOT NULL, end_time TEXT NOT NULL, duration_ms REAL NOT NULL,
    status TEXT NOT NULL, steps INTEGER NOT NULL DEFAULT 1, llm_calls INTEGER NOT NULL DEFAULT 0,
    tool_calls INTEGER NOT NULL DEFAULT 0, retry_count INTEGER NOT NULL DEFAULT 0,
    planning_time_ms REAL, execution_time_ms REAL, human_approval_required INTEGER NOT NULL DEFAULT 0,
    environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, agent_run_id TEXT, tool_name TEXT NOT NULL,
    tool_type TEXT NOT NULL, agent_name TEXT, input_json TEXT, output_json TEXT,
    start_time TEXT NOT NULL, end_time TEXT NOT NULL, latency_ms REAL NOT NULL,
    status TEXT NOT NULL, retry_count INTEGER NOT NULL DEFAULT 0, error TEXT,
    environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, query_hash TEXT NOT NULL, rewritten_query TEXT,
    documents_retrieved INTEGER NOT NULL, top_k INTEGER NOT NULL, retrieval_latency_ms REAL NOT NULL,
    vector_search_latency_ms REAL, reranking_latency_ms REAL, context_size INTEGER NOT NULL DEFAULT 0,
    context_tokens INTEGER NOT NULL DEFAULT 0, similarity_score REAL, top_similarity_score REAL,
    average_similarity_score REAL, chunk_ids_json TEXT, document_ids_json TEXT,
    source_documents_json TEXT, status TEXT NOT NULL, environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, environment TEXT NOT NULL,
    cpu_percent REAL, memory_percent REAL, process_memory_bytes INTEGER, process_cpu_seconds REAL,
    thread_count INTEGER, disk_usage_percent REAL, disk_io_read_bytes INTEGER,
    disk_io_write_bytes INTEGER, network_io_sent_bytes INTEGER, network_io_recv_bytes INTEGER,
    active_connections INTEGER, database_size_bytes INTEGER, database_connections INTEGER
);
CREATE TABLE IF NOT EXISTS query_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, query_type TEXT NOT NULL, query_name TEXT NOT NULL,
    duration_ms REAL NOT NULL, status TEXT NOT NULL, error_type TEXT, environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drift_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, trace_id TEXT,
    request_id TEXT, category TEXT NOT NULL, feature_name TEXT, baseline_value REAL,
    current_value REAL, drift_score REAL, method TEXT, status TEXT NOT NULL,
    metadata_json TEXT, environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, event_type TEXT NOT NULL, severity TEXT NOT NULL, decision TEXT NOT NULL,
    endpoint TEXT, details_json TEXT, environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS guardrail_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, guardrail_name TEXT NOT NULL, guardrail_type TEXT NOT NULL,
    decision TEXT NOT NULL, reason TEXT, severity TEXT NOT NULL, action_taken TEXT,
    input_hash TEXT, environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS human_approval_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, workflow_id TEXT, decision TEXT NOT NULL,
    reason TEXT, reviewer TEXT, duration_ms REAL, environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_states (
    workflow_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, request_id TEXT, trace_id TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, state_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cost_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, agent_name TEXT, model_name TEXT NOT NULL,
    estimated_cost REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'USD',
    environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS token_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, model_name TEXT NOT NULL, prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL, total_tokens INTEGER NOT NULL, cached_tokens INTEGER NOT NULL DEFAULT 0,
    environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS error_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, request_id TEXT,
    trace_id TEXT, session_id TEXT, error_type TEXT NOT NULL, message TEXT NOT NULL,
    stack_trace TEXT, endpoint TEXT, agent_name TEXT, tool_name TEXT, severity TEXT NOT NULL,
    environment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, metric TEXT NOT NULL,
    operator TEXT NOT NULL, threshold REAL NOT NULL, severity TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, rule_name TEXT NOT NULL,
    status TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL, threshold REAL NOT NULL,
    message TEXT NOT NULL, environment TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_time ON application_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_trace ON application_logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_logs_request ON application_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_logs_session ON application_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_logs_filters ON application_logs(environment, service, level, status);
CREATE INDEX IF NOT EXISTS idx_requests_time ON request_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_requests_trace ON request_metrics(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(parent_span_id);
CREATE INDEX IF NOT EXISTS idx_llm_time ON llm_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_agents_time ON agent_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_tools_time ON tool_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_rag_time ON rag_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_drift_time ON drift_observations(timestamp, category);
CREATE INDEX IF NOT EXISTS idx_errors_trace ON error_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_security_time ON security_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_guardrails_trace ON guardrail_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_queries_time ON query_metrics(timestamp);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return "{}"


class ObservabilityStore:
    def __init__(self) -> None:
        configured = os.getenv("OBSERVABILITY_DB_PATH", "")
        self.db_path = Path(configured) if configured else Path(__file__).resolve().parents[2] / "observability.db"
        self.environment = settings.app_env.upper()
        self._initialized = False
        self._last_cleanup = 0.0
        self._last_process_cpu: Optional[float] = None
        self._last_cpu_sample = time.monotonic()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        if self._initialized:
            return
        with _init_lock:
            if self._initialized:
                return
            with self._connect() as connection:
                connection.executescript(_SCHEMA)
                connection.execute("BEGIN IMMEDIATE")
                self._seed(connection)
                connection.commit()
            self._initialized = True

    def _seed(self, connection: sqlite3.Connection) -> None:
        if connection.execute("SELECT 1 FROM application_logs LIMIT 1").fetchone():
            self._seed_alert_rules(connection)
            return
        rng = random.Random(20261007)
        now = datetime.now(timezone.utc)
        environments = ["DEVELOPMENT", "QA", "STAGING", "PRODUCTION"]
        status_choices = ["SUCCESS", "SUCCESS", "SUCCESS", "ERROR"]
        traces = []
        for index in range(100):
            trace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"seed-trace-{index}"))
            request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"seed-request-{index}"))
            session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"seed-session-{index % 20}"))
            start = now - timedelta(minutes=rng.randint(5, 60 * 24 * 30))
            duration = round(rng.uniform(120, 2800), 2)
            status = rng.choice(status_choices)
            environment = environments[index % len(environments)]
            endpoint = "/api/risk/classify"
            connection.execute(
                "INSERT INTO traces(trace_id,request_id,session_id,endpoint,environment,started_at,ended_at,duration_ms,status) VALUES(?,?,?,?,?,?,?,?,?)",
                (trace_id, request_id, session_id, endpoint, environment, start.isoformat(), (start + timedelta(milliseconds=duration)).isoformat(), duration, status),
            )
            traces.append((trace_id, request_id, session_id, start, duration, status, environment))

        # Seeded records are illustrative demo data only; production metrics are recorded from actual requests.
        for index in range(500):
            trace_id, request_id, session_id, start, duration, status, environment = traces[index % len(traces)]
            level = "ERROR" if index % 17 == 0 else ("WARNING" if index % 8 == 0 else "INFO")
            message = "Demo request failed" if level == "ERROR" else "Demo observability event"
            connection.execute(
                "INSERT INTO application_logs(timestamp,level,service,environment,request_id,trace_id,session_id,endpoint,message,latency_ms,status,structured_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                ((start + timedelta(milliseconds=index)).isoformat(), level, "supplier-risk-api", environment, request_id, trace_id, session_id, "/api/risk/classify", message, duration, status, _json({"demo": True, "sequence": index})),
            )

        for index in range(300):
            trace_id, request_id, session_id, start, duration, status, environment = traces[index % len(traces)]
            code = 500 if status == "ERROR" else 200
            connection.execute(
                "INSERT INTO request_metrics(timestamp,request_id,trace_id,session_id,endpoint,method,status_code,status,latency_ms,environment,error_type) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ((start + timedelta(seconds=index)).isoformat(), request_id, trace_id, session_id, "/api/risk/classify", "POST", code, status, duration, environment, "HTTPError" if code >= 500 else None),
            )

        for index in range(300):
            trace_id, request_id, session_id, start, _, _, environment = traces[index % len(traces)]
            prompt = rng.randint(100, 1800)
            completion = rng.randint(80, 600)
            latency = round(rng.uniform(120, 3500), 2)
            cost = round((prompt * 0.00000015) + (completion * 0.0000006), 8)
            connection.execute(
                "INSERT INTO llm_metrics(timestamp,request_id,trace_id,session_id,provider,model_name,prompt_version,system_prompt_version,prompt_tokens,completion_tokens,total_tokens,latency_ms,time_to_first_token_ms,tokens_per_second,status,estimated_cost,environment) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ((start + timedelta(seconds=index)).isoformat(), request_id, trace_id, session_id, "demo", "gpt-4o-mini", "v1", "v1", prompt, completion, prompt + completion, latency, latency * 0.2, round(completion / max(latency / 1000, 0.01), 2), "SUCCESS", cost, environment),
            )
            connection.execute(
                "INSERT INTO cost_metrics(timestamp,request_id,trace_id,session_id,model_name,estimated_cost,environment) VALUES(?,?,?,?,?,?,?)",
                ((start + timedelta(seconds=index)).isoformat(), request_id, trace_id, session_id, "gpt-4o-mini", cost, environment),
            )
            connection.execute(
                "INSERT INTO token_metrics(timestamp,request_id,trace_id,session_id,model_name,prompt_tokens,completion_tokens,total_tokens,environment) VALUES(?,?,?,?,?,?,?,?,?)",
                ((start + timedelta(seconds=index)).isoformat(), request_id, trace_id, session_id, "gpt-4o-mini", prompt, completion, prompt + completion, environment),
            )

        for index in range(200):
            trace_id, request_id, session_id, start, _, status, environment = traces[index % len(traces)]
            agent_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"seed-agent-{index}"))
            name = ["triage", "supplier_data", "performance", "shipment", "inventory", "risk_classification"][index % 6]
            duration = round(rng.uniform(5, 400), 2)
            connection.execute(
                "INSERT INTO agent_metrics(timestamp,request_id,trace_id,session_id,agent_run_id,agent_name,start_time,end_time,duration_ms,status,steps,llm_calls,tool_calls,environment) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (start.isoformat(), request_id, trace_id, session_id, agent_id, name, start.isoformat(), (start + timedelta(milliseconds=duration)).isoformat(), duration, status, rng.randint(1, 4), rng.randint(0, 2), rng.randint(0, 3), environment),
            )

        for index in range(500):
            trace_id, request_id, session_id, start, _, status, environment = traces[index % len(traces)]
            duration = round(rng.uniform(1, 250), 2)
            tool_status = "ERROR" if index % 29 == 0 else "SUCCESS"
            connection.execute(
                "INSERT INTO tool_metrics(timestamp,request_id,trace_id,session_id,tool_name,tool_type,agent_name,input_json,output_json,start_time,end_time,latency_ms,status,environment) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (start.isoformat(), request_id, trace_id, session_id, ["get_supplier", "get_purchase_order", "get_shipment", "get_inventory"][index % 4], "database_read", "supplier_risk", "{}", "{}", start.isoformat(), (start + timedelta(milliseconds=duration)).isoformat(), duration, tool_status, environment),
            )

        for index in range(200):
            trace_id, request_id, session_id, start, _, _, environment = traces[index % len(traces)]
            docs = index % 4
            score = round(rng.uniform(0.35, 0.99), 3) if docs else None
            connection.execute(
                "INSERT INTO rag_metrics(timestamp,request_id,trace_id,session_id,query_hash,documents_retrieved,top_k,retrieval_latency_ms,context_tokens,similarity_score,top_similarity_score,average_similarity_score,document_ids_json,status,environment) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (start.isoformat(), request_id, trace_id, session_id, f"demo-{index:04d}", docs, 3, round(rng.uniform(10, 300), 2), rng.randint(0, 900), score, score, score, _json([f"policy-{x}" for x in range(docs)]), "SUCCESS" if docs else "NO_DOCUMENTS", environment),
            )

        span_types = ["api", "guardrail", "agent", "retrieval", "tool"]
        for index in range(500):
            trace_id, request_id, session_id, start, duration, status, environment = traces[index % len(traces)]
            span_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"seed-span-{index}"))
            parent_id = None if index % 5 == 0 else str(uuid.uuid5(uuid.NAMESPACE_URL, f"seed-span-{index - 1}"))
            span_type = span_types[index % len(span_types)]
            connection.execute(
                "INSERT INTO spans(span_id,trace_id,parent_span_id,request_id,session_id,span_name,span_type,service_name,started_at,ended_at,duration_ms,status,input_json,output_json,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (span_id, trace_id, parent_id, request_id, session_id, f"demo.{span_type}", span_type, "supplier-risk-api", start.isoformat(), (start + timedelta(milliseconds=duration / 5)).isoformat(), round(duration / 5, 2), status, "{}", "{}", _json({"demo": True, "environment": environment})),
            )

        drift_categories = ["data", "model", "prediction", "concept", "prompt", "retrieval"]
        for index in range(100):
            trace_id, request_id, _, start, _, _, environment = traces[index % len(traces)]
            score = round(rng.random() * 0.35, 4)
            status = "CRITICAL" if score > 0.25 else ("WARNING" if score >= 0.1 else "NORMAL")
            connection.execute(
                "INSERT INTO drift_observations(timestamp,trace_id,request_id,category,feature_name,baseline_value,current_value,drift_score,method,status,metadata_json,environment) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (start.isoformat(), trace_id, request_id, drift_categories[index % len(drift_categories)], "risk_score", 0.5, round(rng.random(), 3), score, "PSI", status, _json({"demo": True}), environment),
            )

        for index in range(50):
            trace_id, request_id, session_id, start, _, _, environment = traces[index % len(traces)]
            connection.execute(
                "INSERT INTO guardrail_events(timestamp,request_id,trace_id,session_id,guardrail_name,guardrail_type,decision,reason,severity,action_taken,input_hash,environment) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (start.isoformat(), request_id, trace_id, session_id, "supplier_risk_input", "input", "BLOCK" if index % 7 == 0 else "ALLOW", "Demo policy check", "WARNING" if index % 7 == 0 else "INFO", "rejected" if index % 7 == 0 else "continued", str(index), environment),
            )

        for index in range(30):
            trace_id, request_id, _, start, _, _, environment = traces[index % len(traces)]
            connection.execute(
                "INSERT INTO security_events(timestamp,request_id,trace_id,event_type,severity,decision,endpoint,details_json,environment) VALUES(?,?,?,?,?,?,?,?,?)",
                (start.isoformat(), request_id, trace_id, "prompt_injection_attempt" if index % 4 == 0 else "request_validation", "WARNING" if index % 4 == 0 else "INFO", "BLOCKED" if index % 4 == 0 else "ALLOWED", "/api/risk/classify", _json({"demo": True}), environment),
            )
        for index in range(30):
            trace_id, request_id, session_id, start, _, _, environment = traces[index % len(traces)]
            connection.execute(
                "INSERT INTO error_events(timestamp,request_id,trace_id,session_id,error_type,message,severity,endpoint,environment) VALUES(?,?,?,?,?,?,?,?,?)",
                (start.isoformat(), request_id, trace_id, session_id, "HTTPError", "Demo error; no credentials stored.", "ERROR", "/api/risk/classify", environment),
            )
        for index in range(12):
            timestamp = (now - timedelta(days=index * 2)).isoformat()
            connection.execute(
                "INSERT INTO system_metrics(timestamp,environment,cpu_percent,memory_percent,process_memory_bytes,thread_count,database_size_bytes,database_connections) VALUES(?,?,?,?,?,?,?,?)",
                (timestamp, "DEVELOPMENT", round(rng.uniform(10, 78), 2), round(rng.uniform(20, 80), 2), rng.randint(50, 200) * 1024 * 1024, rng.randint(4, 24), 0, 1),
            )
        self._seed_alert_rules(connection)

    def _seed_alert_rules(self, connection: sqlite3.Connection) -> None:
        defaults = [
            ("LLM P95 latency", "llm_p95_latency_ms", ">", 5000, "WARNING"),
            ("Error rate", "error_rate", ">", 5, "CRITICAL"),
            ("Agent failure rate", "agent_failure_rate", ">", 5, "CRITICAL"),
            ("Tool failure rate", "tool_failure_rate", ">", 10, "WARNING"),
            ("CPU usage", "cpu_percent", ">", 85, "CRITICAL"),
            ("Memory usage", "memory_percent", ">", 90, "CRITICAL"),
            ("Data drift PSI", "data_drift_psi", ">", 0.25, "CRITICAL"),
            ("Retrieval no-result rate", "rag_no_result_rate", ">", 10, "WARNING"),
            ("Daily cost budget", "daily_cost", ">", 25, "WARNING"),
        ]
        for name, metric, operator, threshold, severity in defaults:
            connection.execute(
                "INSERT OR IGNORE INTO alert_rules(name,metric,operator,threshold,severity,enabled,created_at) VALUES(?,?,?,?,?,?,?)",
                (name, metric, operator, threshold, severity, 1, utc_now()),
            )
        if not connection.execute("SELECT 1 FROM alerts LIMIT 1").fetchone():
            timestamp = utc_now()
            connection.executemany(
                """INSERT INTO alerts(timestamp,rule_name,status,metric,value,threshold,message,environment)
                   VALUES(?,?,?,?,?,?,?,?)""",
                [
                    (timestamp, "Error rate", "CRITICAL", "error_rate", 8.3, 5, "Seeded demonstration alert: error rate exceeded threshold.", "DEVELOPMENT"),
                    (timestamp, "Data drift PSI", "WARNING", "data_drift_psi", 0.18, 0.1, "Seeded demonstration alert: moderate feature drift observed.", "DEVELOPMENT"),
                ],
            )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self.initialize()
        for attempt in range(3):
            started = time.perf_counter()
            try:
                with self._connect() as connection:
                    rows = connection.execute(sql, params).fetchall()
                    context = current_trace_context()
                    connection.execute(
                        """INSERT INTO query_metrics(timestamp,request_id,trace_id,query_type,query_name,
                           duration_ms,status,environment) VALUES(?,?,?,?,?,?,?,?)""",
                        (utc_now(), context.get("request_id"), context.get("trace_id"), "READ",
                         self._query_name(sql), (time.perf_counter() - started) * 1000,
                         "SUCCESS", self.environment),
                    )
                    return [dict(row) for row in rows]
            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower() or attempt == 2:
                    self._record_query_failure(sql, started, error)
                    raise
                time.sleep(0.05 * (attempt + 1))
        return []

    def write(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        self.initialize()
        for attempt in range(3):
            started = time.perf_counter()
            try:
                with self._connect() as connection:
                    cursor = connection.execute(sql, params)
                    context = current_trace_context()
                    connection.execute(
                        """INSERT INTO query_metrics(timestamp,request_id,trace_id,query_type,query_name,
                           duration_ms,status,environment) VALUES(?,?,?,?,?,?,?,?)""",
                        (utc_now(), context.get("request_id"), context.get("trace_id"), "WRITE",
                         self._query_name(sql), (time.perf_counter() - started) * 1000,
                         "SUCCESS", self.environment),
                    )
                    return int(cursor.lastrowid or 0)
            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower() or attempt == 2:
                    self._record_query_failure(sql, started, error)
                    logger.exception("Observability database write failed")
                    raise
                time.sleep(0.05 * (attempt + 1))
        return 0

    def persist_workflow_state(self, state: dict[str, Any]) -> None:
        timestamp = utc_now()
        self.write(
            """INSERT INTO workflow_states(workflow_id,session_id,request_id,trace_id,
               created_at,updated_at,state_json) VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(workflow_id) DO UPDATE SET
                   session_id=excluded.session_id,request_id=excluded.request_id,
                   trace_id=excluded.trace_id,updated_at=excluded.updated_at,
                   state_json=excluded.state_json""",
            (
                state["workflow_id"],
                state["session_id"],
                state.get("request_id"),
                state.get("trace_id"),
                timestamp,
                timestamp,
                json.dumps(state, ensure_ascii=True, separators=(",", ":"), default=str),
            ),
        )

    def get_workflow_state(self, workflow_id: str) -> Optional[dict[str, Any]]:
        rows = self.execute(
            "SELECT state_json FROM workflow_states WHERE workflow_id=?",
            (workflow_id,),
        )
        if not rows:
            return None
        state = json.loads(rows[0]["state_json"])
        if not isinstance(state, dict):
            raise ValueError(f"Persisted workflow state {workflow_id!r} is not a JSON object.")
        return state

    def record_workflow_approval_decision(
        self, workflow_id: str, decision: str, notes: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        self.initialize()
        timestamp = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state_json FROM workflow_states WHERE workflow_id=?",
                (workflow_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None

            state = json.loads(row["state_json"])
            if not isinstance(state, dict):
                raise ValueError(f"Persisted workflow state {workflow_id!r} is not a JSON object.")
            human_approval = state.get("human_approval", {})
            state["human_approval"] = {
                **human_approval,
                "decision": {
                    "APPROVE": "APPROVED",
                    "REJECT": "REJECTED",
                    "MODIFY": "MODIFIED",
                }[decision],
                "notes": notes,
                "decided_at": timestamp,
            }
            guardrails = state.get("guardrails", {})
            state["guardrails"] = {
                **guardrails,
                "approval_decisions_persisted": True,
            }
            connection.execute(
                """UPDATE workflow_states SET updated_at=?,state_json=?
                   WHERE workflow_id=?""",
                (
                    timestamp,
                    json.dumps(state, ensure_ascii=True, separators=(",", ":"), default=str),
                    workflow_id,
                ),
            )
            connection.execute(
                """INSERT INTO human_approval_events(timestamp,request_id,trace_id,session_id,
                   workflow_id,decision,reason,environment) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    timestamp,
                    state.get("request_id"),
                    state.get("trace_id"),
                    state.get("session_id"),
                    workflow_id,
                    decision,
                    notes,
                    self.environment,
                ),
            )
            connection.commit()
        return state

    @staticmethod
    def _query_name(sql: str) -> str:
        words = sql.strip().split()
        if not words:
            return "unknown"
        operation = words[0].upper()
        table = next((word for word in words if word.upper() in {"FROM", "INTO", "UPDATE", "TABLE"}), None)
        if table:
            words_upper = [word.upper() for word in words]
            index = words_upper.index(table.upper())
            return f"{operation}:{words[index + 1].strip('(),')}" if index + 1 < len(words) else operation
        return operation

    def _record_query_failure(self, sql: str, started: float, error: sqlite3.Error) -> None:
        context = current_trace_context()
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO query_metrics(timestamp,request_id,trace_id,query_type,query_name,
                       duration_ms,status,error_type,environment) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (utc_now(), context.get("request_id"), context.get("trace_id"), "WRITE",
                     self._query_name(sql), (time.perf_counter() - started) * 1000, "ERROR",
                     type(error).__name__, self.environment),
                )
        except sqlite3.Error:
            logger.exception("Unable to persist database query failure telemetry")

    def record_log(
        self, level: str, message: str, *, request_id: Optional[str] = None,
        trace_id: Optional[str] = None, session_id: Optional[str] = None,
        endpoint: Optional[str] = None, service: str = "supplier-risk-api",
        status: Optional[str] = None, latency_ms: Optional[float] = None,
        error_type: Optional[str] = None, agent_name: Optional[str] = None,
        tool_name: Optional[str] = None, model_name: Optional[str] = None,
        structured: Optional[dict[str, Any]] = None,
    ) -> int:
        return self.write(
            """INSERT INTO application_logs(timestamp,level,service,environment,request_id,trace_id,session_id,
               agent_name,tool_name,model_name,endpoint,message,latency_ms,status,error_type,structured_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (utc_now(), level.upper(), service, self.environment, request_id, trace_id, session_id,
             agent_name, tool_name, model_name, endpoint, message[:1000], latency_ms, status,
             error_type, _json(structured or {})),
        )

    def record_span(
        self, *, trace_id: str, request_id: str, session_id: str, span_name: str,
        span_type: str, started_at: str, duration_ms: float, status: str = "SUCCESS",
        parent_span_id: Optional[str] = None, agent_run_id: Optional[str] = None,
        input_data: Any = None, output_data: Any = None, error: Optional[str] = None,
        agent_name: Optional[str] = None, metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        span_id = str(uuid.uuid4())
        ended_at = (datetime.fromisoformat(started_at) + timedelta(milliseconds=duration_ms)).isoformat()
        self.write(
            """INSERT INTO spans(span_id,trace_id,parent_span_id,request_id,session_id,agent_run_id,
               span_name,span_type,service_name,agent_name,started_at,ended_at,duration_ms,status,
               input_json,output_json,error,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (span_id, trace_id, parent_span_id, request_id, session_id, agent_run_id, span_name,
             span_type, "supplier-risk-api", agent_name, started_at, ended_at, duration_ms,
             status, _json(input_data), _json(output_data), error, _json(metadata or {})),
        )
        return span_id

    def record_agent_run(
        self, agent_name: str, operation: Any, *, input_summary: Any = None,
        approval_required: bool = False,
    ) -> Any:
        context = current_trace_context()
        if not context.get("trace_id"):
            return operation()
        started_at = utc_now()
        started = time.perf_counter()
        agent_run_id = str(uuid.uuid4())
        try:
            result = operation()
        except Exception as error:
            duration_ms = (time.perf_counter() - started) * 1000
            self.write(
                """INSERT INTO agent_metrics(timestamp,request_id,trace_id,session_id,agent_run_id,
                   agent_name,start_time,end_time,duration_ms,status,steps,human_approval_required,environment)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (started_at, context["request_id"], context["trace_id"], context["session_id"],
                 agent_run_id, agent_name, started_at, utc_now(), duration_ms, "ERROR", 1,
                 int(approval_required), self.environment),
            )
            self.record_span(
                trace_id=context["trace_id"], request_id=context["request_id"],
                session_id=context["session_id"], span_name=agent_name, span_type="agent",
                started_at=started_at, duration_ms=duration_ms, status="ERROR",
                parent_span_id=context.get("parent_span_id"), agent_run_id=agent_run_id,
                agent_name=agent_name, input_data=input_summary,
                error=type(error).__name__,
            )
            self.record_log("ERROR", f"agent_failed:{agent_name}", request_id=context["request_id"],
                            trace_id=context["trace_id"], session_id=context["session_id"],
                            agent_name=agent_name, status="ERROR", latency_ms=duration_ms,
                            error_type=type(error).__name__)
            self.record_error(type(error).__name__, f"Agent {agent_name} failed.",
                              context.get("endpoint"), context["request_id"], context["trace_id"],
                              context["session_id"])
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        ended_at = utc_now()
        self.write(
            """INSERT INTO agent_metrics(timestamp,request_id,trace_id,session_id,agent_run_id,
               agent_name,start_time,end_time,duration_ms,status,steps,human_approval_required,environment)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (started_at, context["request_id"], context["trace_id"], context["session_id"],
             agent_run_id, agent_name, started_at, ended_at, duration_ms, "SUCCESS", 1,
             int(approval_required), self.environment),
        )
        self.record_span(
            trace_id=context["trace_id"], request_id=context["request_id"],
            session_id=context["session_id"], span_name=agent_name, span_type="agent",
            started_at=started_at, duration_ms=duration_ms, parent_span_id=context.get("parent_span_id"),
            agent_run_id=agent_run_id, agent_name=agent_name, input_data=input_summary,
            output_data={"result_type": type(result).__name__},
        )
        self.record_log("INFO", f"agent_completed:{agent_name}", request_id=context["request_id"],
                        trace_id=context["trace_id"], session_id=context["session_id"],
                        agent_name=agent_name, status="SUCCESS", latency_ms=duration_ms)
        return result

    def record_tool_call(
        self, tool_name: str, operation: Any, *, agent_name: Optional[str] = None,
        input_summary: Any = None,
    ) -> Any:
        context = current_trace_context()
        started_at = utc_now()
        started = time.perf_counter()
        try:
            result = operation()
        except Exception as error:
            duration_ms = (time.perf_counter() - started) * 1000
            if context.get("trace_id"):
                self.write(
                    """INSERT INTO tool_metrics(timestamp,request_id,trace_id,session_id,tool_name,
                       tool_type,agent_name,input_json,start_time,end_time,latency_ms,status,error,environment)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (started_at, context["request_id"], context["trace_id"], context["session_id"],
                     tool_name, "database_read", agent_name, _json(input_summary), started_at,
                     utc_now(), duration_ms, "ERROR", type(error).__name__, self.environment),
                )
                self.record_span(trace_id=context["trace_id"], request_id=context["request_id"],
                                 session_id=context["session_id"], span_name=tool_name, span_type="tool",
                                 started_at=started_at, duration_ms=duration_ms, status="ERROR",
                                 parent_span_id=context.get("parent_span_id"), agent_name=agent_name,
                                 input_data=input_summary, error=type(error).__name__)
                self.record_error(type(error).__name__, f"Tool {tool_name} failed.",
                                  context.get("endpoint"), context["request_id"], context["trace_id"],
                                  context["session_id"])
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        if context.get("trace_id"):
            self.write(
                """INSERT INTO tool_metrics(timestamp,request_id,trace_id,session_id,tool_name,
                   tool_type,agent_name,input_json,output_json,start_time,end_time,latency_ms,status,environment)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (started_at, context["request_id"], context["trace_id"], context["session_id"],
                 tool_name, "database_read", agent_name, _json(input_summary),
                 _json({"result_type": type(result).__name__}), started_at, utc_now(),
                 duration_ms, "SUCCESS", self.environment),
            )
            self.record_span(trace_id=context["trace_id"], request_id=context["request_id"],
                             session_id=context["session_id"], span_name=tool_name, span_type="tool",
                             started_at=started_at, duration_ms=duration_ms,
                             parent_span_id=context.get("parent_span_id"), agent_name=agent_name,
                             input_data=input_summary, output_data={"result_type": type(result).__name__})
        return result

    def record_rag_call(
        self, *, query_hash: str, documents: list[dict[str, Any]], latency_ms: float,
        context_size: int = 0, context_tokens: int = 0, request_id: Optional[str] = None,
        trace_id: Optional[str] = None, session_id: Optional[str] = None,
    ) -> None:
        scores = [float(item["similarity_score"]) for item in documents if item.get("similarity_score") is not None]
        self.write(
            """INSERT INTO rag_metrics(timestamp,request_id,trace_id,session_id,query_hash,
               documents_retrieved,top_k,retrieval_latency_ms,context_size,context_tokens,
               similarity_score,top_similarity_score,average_similarity_score,document_ids_json,
               source_documents_json,status,environment)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (utc_now(), request_id, trace_id, session_id, query_hash, len(documents), 3,
             latency_ms, context_size, context_tokens,
             sum(scores) / len(scores) if scores else None, max(scores) if scores else None,
             sum(scores) / len(scores) if scores else None,
             _json([item.get("id") for item in documents]),
             _json([item.get("title") for item in documents]),
             "SUCCESS" if documents else "NO_DOCUMENTS", self.environment),
        )
        if scores:
            self.record_drift(
                "retrieval", "similarity_score", 0.7, max(scores),
                abs(0.7 - max(scores)), "baseline_similarity_delta",
                request_id, trace_id,
            )

    def record_llm_call(
        self, *, model_name: str, provider: str, prompt_tokens: int,
        completion_tokens: int, latency_ms: float, status: str,
        estimated_cost: float = 0, error: Optional[str] = None,
        prompt_version: str = "v1", system_prompt_version: str = "v1",
    ) -> None:
        context = current_trace_context()
        total = prompt_tokens + completion_tokens
        timestamp = utc_now()
        self.write(
            """INSERT INTO llm_metrics(timestamp,request_id,trace_id,session_id,provider,model_name,
               prompt_version,system_prompt_version,prompt_tokens,completion_tokens,total_tokens,
               latency_ms,tokens_per_second,status,error,estimated_cost,environment)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (timestamp, context.get("request_id"), context.get("trace_id"), context.get("session_id"),
             provider, model_name, prompt_version, system_prompt_version, prompt_tokens,
             completion_tokens, total, latency_ms,
             completion_tokens / max(latency_ms / 1000, 0.001), status, error,
             estimated_cost, self.environment),
        )
        self.write(
            """INSERT INTO token_metrics(timestamp,request_id,trace_id,session_id,model_name,
               prompt_tokens,completion_tokens,total_tokens,environment) VALUES(?,?,?,?,?,?,?,?,?)""",
            (timestamp, context.get("request_id"), context.get("trace_id"), context.get("session_id"),
             model_name, prompt_tokens, completion_tokens, total, self.environment),
        )
        self.write(
            """INSERT INTO cost_metrics(timestamp,request_id,trace_id,session_id,model_name,
               estimated_cost,environment) VALUES(?,?,?,?,?,?,?)""",
            (timestamp, context.get("request_id"), context.get("trace_id"), context.get("session_id"),
             model_name, estimated_cost, self.environment),
        )

    def record_guardrail(
        self, *, guardrail_name: str, guardrail_type: str, decision: str,
        reason: str = "", request_id: Optional[str] = None, trace_id: Optional[str] = None,
        session_id: Optional[str] = None, severity: str = "INFO", action_taken: str = "",
        input_hash: Optional[str] = None,
    ) -> None:
        context = current_trace_context()
        request_id = request_id or context.get("request_id")
        trace_id = trace_id or context.get("trace_id")
        session_id = session_id or context.get("session_id")
        self.write(
            """INSERT INTO guardrail_events(timestamp,request_id,trace_id,session_id,guardrail_name,
               guardrail_type,decision,reason,severity,action_taken,input_hash,environment)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (utc_now(), request_id, trace_id, session_id, guardrail_name, guardrail_type,
             decision, reason[:300], severity, action_taken[:100], input_hash, self.environment),
        )

    def record_security(
        self, event_type: str, decision: str, endpoint: Optional[str] = None,
        request_id: Optional[str] = None, trace_id: Optional[str] = None,
        severity: str = "INFO", details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.write(
            """INSERT INTO security_events(timestamp,request_id,trace_id,event_type,severity,decision,
               endpoint,details_json,environment) VALUES(?,?,?,?,?,?,?,?,?)""",
            (utc_now(), request_id, trace_id, event_type, severity, decision, endpoint,
             _json(details or {}), self.environment),
        )

    def record_error(
        self, error_type: str, message: str, endpoint: Optional[str] = None,
        request_id: Optional[str] = None, trace_id: Optional[str] = None,
        session_id: Optional[str] = None, severity: str = "ERROR",
    ) -> None:
        self.write(
            """INSERT INTO error_events(timestamp,request_id,trace_id,session_id,error_type,message,
               endpoint,severity,environment) VALUES(?,?,?,?,?,?,?,?,?)""",
            (utc_now(), request_id, trace_id, session_id, error_type, message[:1000],
             endpoint, severity, self.environment),
        )

    def record_drift(
        self, category: str, feature_name: str, baseline: Optional[float],
        current: Optional[float], score: Optional[float], method: str,
        request_id: Optional[str] = None, trace_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        status = "NORMAL" if score is None or score < 0.1 else ("WARNING" if score <= 0.25 else "CRITICAL")
        self.write(
            """INSERT INTO drift_observations(timestamp,trace_id,request_id,category,feature_name,
               baseline_value,current_value,drift_score,method,status,metadata_json,environment)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (utc_now(), trace_id, request_id, category, feature_name, baseline, current,
             score, method, status, _json(metadata or {}), self.environment),
        )

    def start_request(
        self, request_id: str, trace_id: str, session_id: str, endpoint: str,
        method: str, started_at: str,
    ) -> str:
        self.write(
            """INSERT INTO traces(trace_id,request_id,session_id,endpoint,environment,started_at,status)
               VALUES(?,?,?,?,?,?,?)""",
            (trace_id, request_id, session_id, endpoint, self.environment, started_at, "RUNNING"),
        )
        span_id = str(uuid.uuid4())
        self.write(
            """INSERT INTO spans(span_id,trace_id,request_id,session_id,span_name,span_type,
               service_name,started_at,status,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (span_id, trace_id, request_id, session_id, "API Request", "api",
             "supplier-risk-api", started_at, "RUNNING", "{}"),
        )
        self.record_log("INFO", "request_received", request_id=request_id, trace_id=trace_id,
                        session_id=session_id, endpoint=endpoint, status="RUNNING")
        return span_id

    def end_request(
        self, request_id: str, trace_id: str, session_id: str, endpoint: str,
        method: str, status_code: int, latency_ms: float, started_at: str,
    ) -> None:
        timestamp = utc_now()
        status = "SUCCESS" if status_code < 400 else "ERROR"
        error_type = f"HTTP{status_code}" if status_code >= 400 else None
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO request_metrics(timestamp,request_id,trace_id,session_id,endpoint,method,
                   status_code,status,latency_ms,environment,error_type) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (timestamp, request_id, trace_id, session_id, endpoint, method, status_code,
                 status, latency_ms, self.environment, error_type),
            )
            connection.execute(
                "UPDATE traces SET ended_at=?,duration_ms=?,status=?,error_type=? WHERE trace_id=?",
                (timestamp, latency_ms, status, error_type, trace_id),
            )
            connection.execute(
                """UPDATE spans SET ended_at=?,duration_ms=?,status=? WHERE trace_id=?
                   AND span_type='api' AND span_name='API Request'""",
                (timestamp, latency_ms, status, trace_id),
            )
        self.record_log("INFO" if status == "SUCCESS" else "ERROR",
                        "request_completed" if status == "SUCCESS" else "request_failed",
                        request_id=request_id, trace_id=trace_id, session_id=session_id,
                        endpoint=endpoint, status=status, latency_ms=latency_ms,
                        error_type=error_type)
        if status == "ERROR":
            self.record_error(error_type or "HTTPError", f"Request returned HTTP {status_code}.",
                              endpoint, request_id, trace_id, session_id)
        self.collect_system_metrics()

    def collect_system_metrics(self) -> None:
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            process_memory = int(usage.ru_maxrss * 1024)
            process_cpu = float(usage.ru_utime + usage.ru_stime)
            stat = os.statvfs(self.db_path.parent)
            disk_used = 1 - (stat.f_bavail / stat.f_blocks) if stat.f_blocks else 0
            database_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            sample_time = time.monotonic()
            elapsed = sample_time - self._last_cpu_sample
            cpu_percent = None
            if self._last_process_cpu is not None and elapsed > 0:
                cpu_percent = min(
                    100.0,
                    max(0.0, (process_cpu - self._last_process_cpu) / elapsed)
                    * 100 / max(os.cpu_count() or 1, 1),
                )
            self._last_process_cpu = process_cpu
            self._last_cpu_sample = sample_time
            memory_percent = None
            if Path("/proc/meminfo").exists():
                memory_values: dict[str, int] = {}
                with open("/proc/meminfo", "r", encoding="ascii") as memory_file:
                    for line in memory_file:
                        key, _, rest = line.partition(":")
                        if key in {"MemTotal", "MemAvailable"}:
                            memory_values[key] = int(rest.strip().split()[0]) * 1024
                total_memory = memory_values.get("MemTotal", 0)
                available_memory = memory_values.get("MemAvailable", 0)
                if total_memory:
                    memory_percent = round((total_memory - available_memory) * 100 / total_memory, 2)
            disk_read = disk_write = network_sent = network_recv = active_connections = None
            proc_io = Path("/proc/self/io")
            if proc_io.exists():
                with open(proc_io, "r", encoding="ascii") as io_file:
                    io_values = dict(line.split(": ", 1) for line in io_file if ": " in line)
                disk_read = int(io_values.get("read_bytes", "0"))
                disk_write = int(io_values.get("write_bytes", "0"))
            net_dev = Path("/proc/net/dev")
            if net_dev.exists():
                with open(net_dev, "r", encoding="ascii") as network_file:
                    network_rows = [line.split() for line in network_file.readlines()[2:] if ":" in line]
                if network_rows:
                    network_recv = sum(int(row[1]) for row in network_rows)
                    network_sent = sum(int(row[9]) for row in network_rows)
            tcp_file = Path("/proc/net/tcp")
            if tcp_file.exists():
                with open(tcp_file, "r", encoding="ascii") as tcp_stream:
                    active_connections = max(len(tcp_stream.readlines()) - 1, 0)
            thread_count = threading.active_count()
            self.write(
                """INSERT INTO system_metrics(timestamp,environment,cpu_percent,memory_percent,
                   process_memory_bytes,process_cpu_seconds,thread_count,disk_usage_percent,
                   disk_io_read_bytes,disk_io_write_bytes,network_io_sent_bytes,network_io_recv_bytes,
                   active_connections,database_size_bytes,database_connections) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (utc_now(), self.environment, cpu_percent, memory_percent, process_memory,
                 process_cpu, thread_count, round(disk_used * 100, 2), disk_read, disk_write,
                 network_sent, network_recv, active_connections, database_size, 1),
            )
        except (OSError, ValueError, sqlite3.Error, IndexError, KeyError):
            logger.exception("Unable to record infrastructure metrics")

    def cleanup(self, retention_days: int = 90) -> dict[str, int]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        removed: dict[str, int] = {}
        tables = {
            "application_logs": "timestamp",
            "request_metrics": "timestamp",
            "llm_metrics": "timestamp",
            "agent_metrics": "timestamp",
            "tool_metrics": "timestamp",
            "rag_metrics": "timestamp",
            "system_metrics": "timestamp",
            "drift_observations": "timestamp",
            "security_events": "timestamp",
            "guardrail_events": "timestamp",
            "human_approval_events": "timestamp",
            "cost_metrics": "timestamp",
            "token_metrics": "timestamp",
            "error_events": "timestamp",
            "workflow_states": "updated_at",
            "spans": "started_at",
            "traces": "started_at",
            "alerts": "timestamp",
            "query_metrics": "timestamp",
        }
        with self._connect() as connection:
            for table, time_column in tables.items():
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE {time_column} < ?",
                    (cutoff,),
                )
                removed[table] = cursor.rowcount
            connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
        self._last_cleanup = time.monotonic()
        return removed

    def maybe_cleanup(self, retention_days: int = 90) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < 3600:
            return
        self.cleanup(retention_days)
        self._last_cleanup = now

    def evaluate_alerts(self) -> list[dict[str, Any]]:
        self.initialize()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        measurements: dict[str, Optional[float]] = {}
        count = self.execute(
            "SELECT COUNT(*) AS total,SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed FROM request_metrics WHERE timestamp>=?",
            (cutoff,),
        )[0]
        measurements["error_rate"] = (count["failed"] or 0) * 100 / count["total"] if count["total"] else 0
        for metric, table in (("agent_failure_rate", "agent_metrics"), ("tool_failure_rate", "tool_metrics")):
            totals = self.execute(
                f"SELECT COUNT(*) AS total,SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed FROM {table} WHERE timestamp>=?",
                (cutoff,),
            )[0]
            measurements[metric] = (totals["failed"] or 0) * 100 / totals["total"] if totals["total"] else 0
        llm_latencies = [
            float(row["latency_ms"]) for row in self.execute(
                "SELECT latency_ms FROM llm_metrics WHERE timestamp>=? ORDER BY latency_ms", (cutoff,)
            ) if row["latency_ms"] is not None
        ]
        measurements["llm_p95_latency_ms"] = (
            llm_latencies[min(int((len(llm_latencies) - 1) * 0.95), len(llm_latencies) - 1)]
            if llm_latencies else 0
        )
        system = self.execute("SELECT cpu_percent,memory_percent FROM system_metrics ORDER BY timestamp DESC LIMIT 1")
        measurements["cpu_percent"] = system[0]["cpu_percent"] if system else 0
        measurements["memory_percent"] = system[0]["memory_percent"] if system else 0
        drift = self.execute(
            "SELECT MAX(drift_score) AS value FROM drift_observations WHERE timestamp>=? AND category='data'",
            (cutoff,),
        )
        measurements["data_drift_psi"] = drift[0]["value"] if drift and drift[0]["value"] is not None else 0
        retrieval = self.execute(
            "SELECT COUNT(*) AS total,SUM(CASE WHEN documents_retrieved=0 THEN 1 ELSE 0 END) AS empty FROM rag_metrics WHERE timestamp>=?",
            (cutoff,),
        )[0]
        measurements["rag_no_result_rate"] = (
            (retrieval["empty"] or 0) * 100 / retrieval["total"] if retrieval["total"] else 0
        )
        cost = self.execute("SELECT COALESCE(SUM(estimated_cost),0) AS value FROM cost_metrics WHERE timestamp>=?", (cutoff,))
        measurements["daily_cost"] = cost[0]["value"]
        rules = self.execute("SELECT * FROM alert_rules WHERE enabled=1")
        evaluated = []
        operators = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}
        with self._connect() as connection:
            for rule in rules:
                value = measurements.get(rule["metric"])
                if value is None:
                    status = "NORMAL"
                    value = 0.0
                else:
                    status = rule["severity"] if operators[rule["operator"]](float(value), float(rule["threshold"])) else "NORMAL"
                message = (
                    f"{rule['metric']} measured {float(value):.3f}; threshold {rule['operator']} {rule['threshold']:.3f}."
                )
                current = connection.execute(
                    "SELECT id FROM alerts WHERE rule_name=? ORDER BY id DESC LIMIT 1", (rule["name"],)
                ).fetchone()
                if current:
                    connection.execute(
                        "UPDATE alerts SET timestamp=?,status=?,metric=?,value=?,threshold=?,message=?,environment=? WHERE id=?",
                        (utc_now(), status, rule["metric"], value, rule["threshold"], message, self.environment, current["id"]),
                    )
                else:
                    connection.execute(
                        "INSERT INTO alerts(timestamp,rule_name,status,metric,value,threshold,message,environment) VALUES(?,?,?,?,?,?,?,?)",
                        (utc_now(), rule["name"], status, rule["metric"], value, rule["threshold"], message, self.environment),
                    )
                evaluated.append({"rule_name": rule["name"], "status": status, "metric": rule["metric"], "value": value, "threshold": rule["threshold"], "message": message})
        return evaluated


store = ObservabilityStore()
