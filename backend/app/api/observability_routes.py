from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.observability import store

router = APIRouter(prefix="/api")

_TIME_WINDOWS = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _time_bounds(time_range: str, start: Optional[str], end: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    def parse(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Time filters must use ISO 8601 timestamps.") from error
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()

    end_value = parse(end) if end else datetime.now(timezone.utc).isoformat()
    if start:
        start_value = parse(start)
        if start_value > end_value:
            raise HTTPException(status_code=422, detail="start must not be later than end.")
        return start_value, end_value
    delta = _TIME_WINDOWS.get(time_range, _TIME_WINDOWS["30d"])
    return (datetime.now(timezone.utc) - delta).isoformat(), end_value


def _filters(
    timestamp_column: str = "timestamp",
    *,
    time_range: str = "30d",
    start: Optional[str] = None,
    end: Optional[str] = None,
    environment: Optional[str] = None,
    extra: Optional[dict[str, Optional[str]]] = None,
) -> tuple[str, list[Any]]:
    clauses = []
    params: list[Any] = []
    lower, upper = _time_bounds(time_range, start, end)
    if lower:
        clauses.append(f"{timestamp_column} >= ?")
        params.append(lower)
    if upper:
        clauses.append(f"{timestamp_column} <= ?")
        params.append(upper)
    if environment:
        clauses.append("environment = ?")
        params.append(environment.upper())
    for column, value in (extra or {}).items():
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def _page(
    sql: str,
    params: list[Any],
    page: int,
    per_page: int,
    sort: str,
    order: str,
    allowed_sorts: set[str],
) -> dict[str, Any]:
    safe_sort = sort if sort in allowed_sorts else "timestamp"
    safe_order = "ASC" if order.lower() == "asc" else "DESC"
    count_sql = f"SELECT COUNT(*) AS count FROM ({sql}) AS result_count"
    count = store.execute(count_sql, tuple(params))[0]["count"]
    data = store.execute(
        f"{sql} ORDER BY {safe_sort} {safe_order} LIMIT ? OFFSET ?",
        tuple(params + [per_page, (page - 1) * per_page]),
    )
    return {"items": data, "page": page, "per_page": per_page, "total": count}


def _percentile(values: list[float], percent: float) -> Optional[float]:
    if not values:
        return None
    values.sort()
    position = (len(values) - 1) * percent
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return round(values[low], 2)
    return round(values[low] * (high - position) + values[high] * (position - low), 2)


def _latency_summary(table: str, column: str, where: str, params: list[Any]) -> dict[str, Any]:
    rows = store.execute(f"SELECT {column} AS value FROM {table}{where}", tuple(params))
    values = [float(row["value"]) for row in rows if row["value"] is not None]
    return {
        "average": round(sum(values) / len(values), 2) if values else None,
        "p50": _percentile(values.copy(), 0.50),
        "p75": _percentile(values.copy(), 0.75),
        "p90": _percentile(values.copy(), 0.90),
        "p95": _percentile(values.copy(), 0.95),
        "p99": _percentile(values.copy(), 0.99),
        "maximum": max(values) if values else None,
    }


def _timeseries(
    table: str, metric: str, time_range: str, environment: Optional[str],
    start: Optional[str] = None, end: Optional[str] = None,
) -> list[dict[str, Any]]:
    where, params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    return store.execute(
        f"SELECT substr(timestamp,1,13) AS bucket, {metric} FROM {table}{where} GROUP BY bucket ORDER BY bucket",
        tuple(params),
    )


@router.get("/logs")
def logs(
    time_range: str = "30d", start: Optional[str] = None, end: Optional[str] = None,
    environment: Optional[str] = None, level: Optional[str] = None, service: Optional[str] = None,
    agent: Optional[str] = None, tool: Optional[str] = None, model: Optional[str] = None,
    status: Optional[str] = None, request_id: Optional[str] = None, trace_id: Optional[str] = None,
    session_id: Optional[str] = None, endpoint: Optional[str] = None, q: Optional[str] = None,
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    sort: str = "timestamp", order: str = "desc",
) -> dict[str, Any]:
    where, params = _filters(
        time_range=time_range, start=start, end=end, environment=environment,
        extra={
            "level": level.upper() if level else None, "service": service,
            "agent_name": agent, "tool_name": tool, "model_name": model,
            "status": status.upper() if status else None, "request_id": request_id,
            "trace_id": trace_id, "session_id": session_id, "endpoint": endpoint,
        },
    )
    if q:
        where += " AND " if where else " WHERE "
        where += "(message LIKE ? OR error_type LIKE ? OR endpoint LIKE ?)"
        params.extend([f"%{q[:100]}%"] * 3)
    sql = f"SELECT * FROM application_logs{where}"
    return _page(sql, params, page, per_page, sort, order, {
        "id", "timestamp", "level", "service", "environment", "latency_ms", "status",
    })


@router.get("/logs/{log_id}")
def log_detail(log_id: int) -> dict[str, Any]:
    rows = store.execute("SELECT * FROM application_logs WHERE id=?", (log_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Log not found.")
    item = rows[0]
    try:
        item["structured"] = json.loads(item.pop("structured_json") or "{}")
    except json.JSONDecodeError:
        item["structured"] = {}
    return item


@router.get("/observability/overview")
def overview(
    time_range: str = "24h", environment: Optional[str] = None,
    start: Optional[str] = None, end: Optional[str] = None,
) -> dict[str, Any]:
    req_where, req_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    request_row = store.execute(
        f"""SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successful,
                   SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed,
                   AVG(latency_ms) AS avg_latency
            FROM request_metrics{req_where}""", tuple(req_params),
    )[0]
    llm_where, llm_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    llm = store.execute(
        f"SELECT COUNT(*) AS calls,COALESCE(SUM(total_tokens),0) AS tokens,COALESCE(SUM(estimated_cost),0) AS cost,AVG(latency_ms) AS avg_latency FROM llm_metrics{llm_where}",
        tuple(llm_params),
    )[0]
    agent_where, agent_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    agents = store.execute(
        f"SELECT COUNT(*) AS runs,SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successful FROM agent_metrics{agent_where}",
        tuple(agent_params),
    )[0]
    tool_where, tool_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    tools = store.execute(
        f"SELECT COUNT(*) AS calls,SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed FROM tool_metrics{tool_where}",
        tuple(tool_params),
    )[0]
    rag_where, rag_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    rag = store.execute(
        f"SELECT COUNT(*) AS calls,AVG(similarity_score) AS avg_similarity,SUM(CASE WHEN documents_retrieved=0 THEN 1 ELSE 0 END) AS empty FROM rag_metrics{rag_where}",
        tuple(rag_params),
    )[0]
    guard_where, guard_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    blocks = store.execute(
        f"SELECT COUNT(*) AS total FROM guardrail_events{guard_where}{' AND ' if guard_where else ' WHERE '}decision='BLOCK'",
        tuple(guard_params),
    )[0]["total"]
    drift_where, drift_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    drift = store.execute(
        f"SELECT MAX(drift_score) AS max_score FROM drift_observations{drift_where}", tuple(drift_params)
    )[0]["max_score"]
    store.evaluate_alerts()
    system = store.execute("SELECT * FROM system_metrics ORDER BY timestamp DESC LIMIT 1")
    total = request_row["total"] or 0
    return {
        "requests": {**request_row, "success_rate": round((request_row["successful"] or 0) * 100 / total, 2) if total else 0},
        "llm": llm,
        "agents": agents,
        "tools": tools,
        "rag": rag,
        "active_alerts": store.execute("SELECT COUNT(*) AS count FROM alerts WHERE status!='NORMAL'")[0]["count"],
        "guardrail_blocks": blocks,
        "drift_score": drift,
        "system": system[0] if system else {},
        "series": {
            "requests": _timeseries("request_metrics", "COUNT(*) AS value", time_range, environment, start, end),
            "latency": _timeseries("request_metrics", "AVG(latency_ms) AS value", time_range, environment, start, end),
            "tokens": _timeseries("token_metrics", "SUM(total_tokens) AS value", time_range, environment, start, end),
            "cost": _timeseries("cost_metrics", "SUM(estimated_cost) AS value", time_range, environment, start, end),
            "drift": _timeseries("drift_observations", "AVG(drift_score) AS value", time_range, environment, start, end),
        },
    }


def _metrics(
    table: str, *, time_range: str, start: Optional[str], end: Optional[str],
    environment: Optional[str], page: int, per_page: int,
) -> dict[str, Any]:
    where, params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    rows = _page(
        f"SELECT * FROM {table}{where}", params, page, per_page, "timestamp", "desc",
        {"id", "timestamp", "latency_ms", "duration_ms", "estimated_cost", "total_tokens", "status"},
    )
    summary: dict[str, Any] = {}
    if table == "request_metrics":
        summary = _latency_summary(table, "latency_ms", where, params)
        counts = store.execute(
            f"SELECT COUNT(*) AS total,SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successful,"
            f"SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed FROM {table}{where}", tuple(params)
        )[0]
        total = counts["total"] or 0
        summary.update(counts)
        summary["success_rate"] = round((counts["successful"] or 0) * 100 / total, 2) if total else 0
    elif table == "llm_metrics":
        summary = _latency_summary(table, "latency_ms", where, params)
        summary.update(store.execute(
            f"SELECT COUNT(*) AS calls,COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,"
            f"COALESCE(SUM(completion_tokens),0) AS completion_tokens,"
            f"COALESCE(SUM(total_tokens),0) AS total_tokens,"
            f"COALESCE(SUM(estimated_cost),0) AS total_cost,"
            f"SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successful,"
            f"SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed FROM {table}{where}",
            tuple(params),
        )[0])
    elif table == "agent_metrics":
        summary = _latency_summary(table, "duration_ms", where, params)
        summary.update(store.execute(
            f"SELECT COUNT(*) AS runs,AVG(steps) AS avg_steps,AVG(tool_calls) AS avg_tool_calls,"
            f"SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed,"
            f"SUM(human_approval_required) AS approvals FROM {table}{where}", tuple(params),
        )[0])
    elif table == "tool_metrics":
        summary = _latency_summary(table, "latency_ms", where, params)
        summary.update(store.execute(
            f"SELECT COUNT(*) AS calls,SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successful,"
            f"SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed FROM {table}{where}", tuple(params),
        )[0])
        summary["by_tool"] = store.execute(
            f"SELECT tool_name,COUNT(*) AS calls,SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed,"
            f"AVG(latency_ms) AS avg_latency FROM {table}{where} GROUP BY tool_name ORDER BY calls DESC",
            tuple(params),
        )
    elif table == "rag_metrics":
        summary = store.execute(
            f"SELECT COUNT(*) AS retrievals,AVG(retrieval_latency_ms) AS avg_latency,"
            f"AVG(similarity_score) AS avg_similarity,AVG(documents_retrieved) AS avg_documents,"
            f"AVG(context_tokens) AS avg_context_tokens,"
            f"SUM(CASE WHEN documents_retrieved=0 THEN 1 ELSE 0 END) AS no_documents FROM {table}{where}",
            tuple(params),
        )[0]
    elif table == "cost_metrics":
        summary = store.execute(
            f"SELECT COALESCE(SUM(estimated_cost),0) AS total_cost,COUNT(*) AS requests,"
            f"AVG(estimated_cost) AS avg_cost FROM {table}{where}", tuple(params),
        )[0]
    return {**rows, "summary": summary}


def _common_metric_params(
    time_range: str, start: Optional[str], end: Optional[str], environment: Optional[str],
    page: int, per_page: int,
) -> dict[str, Any]:
    return {"time_range": time_range, "start": start, "end": end,
            "environment": environment, "page": page, "per_page": per_page}


for _endpoint, _table in (
    ("requests", "request_metrics"), ("llm", "llm_metrics"), ("agents", "agent_metrics"),
    ("tools", "tool_metrics"), ("rag", "rag_metrics"),
):
    def _make_metrics_handler(table: str):
        def handler(
            time_range: str = "24h", start: Optional[str] = None, end: Optional[str] = None,
            environment: Optional[str] = None, page: int = Query(1, ge=1),
            per_page: int = Query(100, ge=1, le=500),
        ) -> dict[str, Any]:
            return _metrics(table, **_common_metric_params(time_range, start, end, environment, page, per_page))
        handler.__name__ = f"metrics_{table}"
        return handler
    router.add_api_route(f"/metrics/{_endpoint}", _make_metrics_handler(_table), methods=["GET"])


@router.get("/metrics/system")
def system_metrics(
    time_range: str = "24h", environment: Optional[str] = None,
    start: Optional[str] = None, end: Optional[str] = None,
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    where, params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    return _page(
        f"SELECT * FROM system_metrics{where}", params, page, per_page,
        "timestamp", "desc", {"id", "timestamp", "cpu_percent", "memory_percent"},
    )


@router.get("/metrics/database")
def database_metrics(time_range: str = "24h", environment: Optional[str] = None) -> dict[str, Any]:
    store.initialize()
    size = store.db_path.stat().st_size if store.db_path.exists() else 0
    tables = store.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    counts = {row["name"]: store.execute(f"SELECT COUNT(*) AS count FROM {row['name']}")[0]["count"] for row in tables}
    where, params = _filters(time_range=time_range, environment=environment)
    query_summary = store.execute(
        f"SELECT COUNT(*) AS queries,SUM(CASE WHEN status!='SUCCESS' THEN 1 ELSE 0 END) AS failed,"
        f"AVG(duration_ms) AS average_latency,SUM(CASE WHEN error_type='OperationalError' THEN 1 ELSE 0 END) AS lock_errors "
        f"FROM query_metrics{where}", tuple(params),
    )[0]
    return {
        "database": store.db_path.name, "size_bytes": size, "journal_mode": "WAL",
        "foreign_keys": True, "busy_timeout_ms": 5000, "connection_model": "per-operation",
        "table_counts": counts, "queries": query_summary,
        "query_latency": _latency_summary("query_metrics", "duration_ms", where, params),
        "slow_queries": store.execute(
            f"SELECT timestamp,query_type,query_name,duration_ms,status,error_type FROM query_metrics"
            f"{where}{' AND ' if where else ' WHERE '}duration_ms >= 100 ORDER BY timestamp DESC LIMIT 50",
            tuple(params),
        ),
    }


@router.get("/metrics/cost")
def cost_metrics(
    time_range: str = "30d", environment: Optional[str] = None,
    start: Optional[str] = None, end: Optional[str] = None,
) -> dict[str, Any]:
    where, params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    totals = store.execute(
        f"SELECT COALESCE(SUM(estimated_cost),0) AS total_cost,COUNT(*) AS requests FROM cost_metrics{where}",
        tuple(params),
    )[0]
    by_model_where, by_model_params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    by_model = store.execute(
        f"SELECT model_name,SUM(estimated_cost) AS cost,COUNT(*) AS calls FROM cost_metrics{by_model_where} GROUP BY model_name ORDER BY cost DESC",
        tuple(by_model_params),
    )
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    date_costs = {}
    for label, cutoff in (("today", today), ("this_week", week), ("this_month", month)):
        date_where, date_params = _filters(start=cutoff, environment=environment)
        date_costs[label] = store.execute(
            f"SELECT COALESCE(SUM(estimated_cost),0) AS total FROM cost_metrics{date_where}",
            tuple(date_params),
        )[0]["total"]
    by_agent = store.execute(
        f"SELECT COALESCE(agent_name,'unspecified') AS agent_name,SUM(estimated_cost) AS cost,"
        f"COUNT(*) AS calls FROM cost_metrics{by_model_where} GROUP BY agent_name ORDER BY cost DESC",
        tuple(by_model_params),
    )
    return {
        "totals": totals, "by_model": by_model, "by_agent": by_agent, **date_costs,
        "series": _timeseries("cost_metrics", "SUM(estimated_cost) AS value", time_range, environment, start, end),
    }


@router.get("/traces")
def traces(
    time_range: str = "24h", start: Optional[str] = None, end: Optional[str] = None,
    environment: Optional[str] = None, status: Optional[str] = None,
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    where, params = _filters(
        "started_at", time_range=time_range, start=start, end=end,
        environment=environment, extra={"status": status.upper() if status else None},
    )
    return _page(f"SELECT * FROM traces{where}", params, page, per_page, "started_at", "desc", {"trace_id", "started_at", "duration_ms", "status", "endpoint"})


@router.get("/traces/{trace_id}")
def trace_detail(trace_id: str) -> dict[str, Any]:
    trace = store.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,))
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found.")
    correlated = {}
    for key, table in (
        ("spans", "spans"), ("logs", "application_logs"), ("llm_calls", "llm_metrics"),
        ("agent_runs", "agent_metrics"), ("tool_calls", "tool_metrics"), ("retrievals", "rag_metrics"),
        ("errors", "error_events"), ("guardrails", "guardrail_events"),
    ):
        correlated[key] = store.execute(f"SELECT * FROM {table} WHERE trace_id=? ORDER BY timestamp" if table != "spans" else "SELECT * FROM spans WHERE trace_id=? ORDER BY started_at", (trace_id,))
    return {"trace": trace[0], **correlated}


@router.get("/drift")
def drift(
    time_range: str = "30d", environment: Optional[str] = None,
    start: Optional[str] = None, end: Optional[str] = None,
) -> dict[str, Any]:
    where, params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    grouped = store.execute(
        f"SELECT category,AVG(drift_score) AS score,MAX(drift_score) AS max_score,COUNT(*) AS observations FROM drift_observations{where} GROUP BY category",
        tuple(params),
    )
    categories = {row["category"]: row for row in grouped}
    maximum = max((row["max_score"] or 0 for row in grouped), default=0)
    overall = "NORMAL" if maximum < 0.1 else ("WARNING" if maximum <= 0.25 else "CRITICAL")
    return {"overall_status": overall, "categories": categories, "series": _timeseries("drift_observations", "AVG(drift_score) AS value", time_range, environment, start, end)}


def _drift_category(
    category: str, time_range: str, environment: Optional[str], page: int, per_page: int,
    start: Optional[str] = None, end: Optional[str] = None,
) -> dict[str, Any]:
    where, params = _filters(time_range=time_range, start=start, end=end, environment=environment, extra={"category": category})
    return _page(f"SELECT * FROM drift_observations{where}", params, page, per_page, "timestamp", "desc", {"id", "timestamp", "category", "feature_name", "drift_score", "status"})


for _endpoint, _category in (
    ("data", "data"), ("model", "model"), ("prediction", "prediction"),
    ("concept", "concept"), ("prompt", "prompt"), ("retrieval", "retrieval"),
):
    def _make_drift_handler(category: str):
        def handler(
            time_range: str = "30d", environment: Optional[str] = None,
            start: Optional[str] = None, end: Optional[str] = None,
            page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
        ) -> dict[str, Any]:
            return _drift_category(category, time_range, environment, page, per_page, start, end)
        handler.__name__ = f"drift_{category}"
        return handler
    router.add_api_route(f"/drift/{_endpoint}", _make_drift_handler(_category), methods=["GET"])


for _endpoint, _table in (
    ("errors", "error_events"), ("security", "security_events"),
    ("guardrails", "guardrail_events"), ("approvals", "human_approval_events"),
):
    def _make_records_handler(table: str):
        def handler(
            time_range: str = "30d", start: Optional[str] = None, end: Optional[str] = None,
            environment: Optional[str] = None, page: int = Query(1, ge=1),
            per_page: int = Query(50, ge=1, le=200),
        ) -> dict[str, Any]:
            return _metrics(table, **_common_metric_params(time_range, start, end, environment, page, per_page))
        handler.__name__ = f"observability_{table}"
        return handler
    router.add_api_route(f"/{_endpoint}", _make_records_handler(_table), methods=["GET"])


@router.get("/alerts")
def alerts(
    time_range: str = "30d", start: Optional[str] = None, end: Optional[str] = None,
    environment: Optional[str] = None, page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    store.evaluate_alerts()
    where, params = _filters(time_range=time_range, start=start, end=end, environment=environment)
    result = _page(f"SELECT * FROM alerts{where}", params, page, per_page, "timestamp", "desc", {"id", "timestamp", "rule_name", "status", "value"})
    result["active_count"] = store.execute("SELECT COUNT(*) AS count FROM alerts WHERE status!='NORMAL'")[0]["count"]
    return result


@router.get("/alert-rules")
def alert_rules() -> dict[str, Any]:
    return {"items": store.execute("SELECT * FROM alert_rules ORDER BY name")}
