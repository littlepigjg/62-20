from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

from ..core.search_engine import search_engine, SearchFilter
from ..core.search_indexer import search_indexer
from ..core.search_shortcuts import shortcut_manager, history_manager


router = APIRouter(prefix="/search", tags=["Search"])


class SearchRequest(BaseModel):
    query: str = ""
    doc_types: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    server_ids: Optional[List[str]] = None
    server_tags: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 50
    offset: int = 0
    fuzzy: bool = True
    expand_synonyms: bool = True
    record_history: bool = True


class SearchShortcutCreate(BaseModel):
    id: str
    name: str
    query: str
    filters: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str
    usage_count: int


class SearchShortcutCreateRequest(BaseModel):
    name: str
    query: str
    filters: dict = Field(default_factory=dict)


class SearchShortcutUpdateRequest(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[dict] = None


def _parse_time_range(
    start_time: Optional[str],
    end_time: Optional[str],
) -> Optional[tuple]:
    start_ts = None
    end_ts = None

    if start_time:
        try:
            start_ts = datetime.fromisoformat(start_time).timestamp()
        except (ValueError, TypeError):
            pass

    if end_time:
        try:
            end_ts = datetime.fromisoformat(end_time).timestamp()
        except (ValueError, TypeError):
            pass

    if start_ts is not None or end_ts is not None:
        return (start_ts or 0, end_ts or datetime.now().timestamp())
    return None


def _build_search_filter(req: SearchRequest) -> Optional[SearchFilter]:
    time_range = _parse_time_range(req.start_time, req.end_time)

    has_filters = any([
        req.doc_types,
        req.statuses,
        req.server_ids,
        req.server_tags,
        req.tags,
        time_range,
    ])

    if not has_filters:
        return None

    return SearchFilter(
        doc_types=req.doc_types,
        statuses=req.statuses,
        server_ids=req.server_ids,
        server_tags=req.server_tags,
        tags=req.tags,
        time_range=time_range,
    )


def _result_to_dict(result) -> dict:
    return {
        "doc_id": result.doc.doc_id,
        "doc_type": result.doc.doc_type,
        "title": result.doc.title,
        "content": result.doc.content[:500] if len(result.doc.content) > 500 else result.doc.content,
        "metadata": result.doc.metadata,
        "tags": result.doc.tags,
        "timestamp": result.doc.timestamp,
        "status": result.doc.status,
        "server_id": result.doc.server_id,
        "server_tags": result.doc.server_tags,
        "score": result.score,
        "highlights": result.highlights,
        "matched_terms": result.matched_terms,
    }


@router.post("")
async def search(req: SearchRequest):
    if not search_indexer._initialized:
        search_indexer.initialize()

    search_filter = _build_search_filter(req)

    results, total = search_engine.search(
        query=req.query,
        search_filter=search_filter,
        limit=req.limit,
        offset=req.offset,
        fuzzy=req.fuzzy,
        expand_synonyms=req.expand_synonyms,
    )

    if req.record_history and req.query.strip():
        history_manager.add_search(
            query=req.query,
            filters={
                "doc_types": req.doc_types,
                "statuses": req.statuses,
                "server_ids": req.server_ids,
                "server_tags": req.server_tags,
                "tags": req.tags,
                "start_time": req.start_time,
                "end_time": req.end_time,
            },
        )
        search_engine.record_search(req.query)

    return {
        "results": [_result_to_dict(r) for r in results],
        "total": total,
        "offset": req.offset,
        "limit": req.limit,
        "query": req.query,
    }


@router.get("/suggestions")
async def get_suggestions(
    query: str = Query("", description="搜索关键词"),
    limit: int = Query(10, description="返回数量"),
):
    if not search_indexer._initialized:
        search_indexer.initialize()

    suggestions = search_engine.get_suggestions(query, limit=limit)
    return {"suggestions": suggestions}


@router.get("/history")
async def get_search_history(limit: int = Query(20, description="返回数量")):
    history = history_manager.get_history(limit=limit)
    return {"history": history}


@router.delete("/history")
async def clear_search_history():
    history_manager.clear_history()
    return {"message": "Search history cleared"}


@router.delete("/history/{query:path}")
async def remove_history_item(query: str):
    success = history_manager.remove_from_history(query)
    if not success:
        raise HTTPException(status_code=404, detail="History item not found")
    return {"message": "History item removed"}


@router.get("/popular")
async def get_popular_searches(limit: int = Query(10, description="返回数量")):
    if not search_indexer._initialized:
        search_indexer.initialize()

    popular = search_engine.get_popular_searches(limit=limit)
    return {"popular": popular}


@router.get("/shortcuts")
async def list_shortcuts():
    shortcuts = shortcut_manager.list_shortcuts()
    return {
        "shortcuts": [
            {
                "id": s.id,
                "name": s.name,
                "query": s.query,
                "filters": s.filters,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "usage_count": s.usage_count,
            }
            for s in shortcuts
        ]
    }


@router.post("/shortcuts", status_code=201)
async def create_shortcut(req: SearchShortcutCreateRequest):
    shortcut = shortcut_manager.create_shortcut(
        name=req.name,
        query=req.query,
        filters=req.filters,
    )
    return {
        "id": shortcut.id,
        "name": shortcut.name,
        "query": shortcut.query,
        "filters": shortcut.filters,
        "created_at": shortcut.created_at,
        "updated_at": shortcut.updated_at,
        "usage_count": shortcut.usage_count,
    }


@router.put("/shortcuts/{shortcut_id}")
async def update_shortcut(shortcut_id: str, req: SearchShortcutUpdateRequest):
    shortcut = shortcut_manager.update_shortcut(
        shortcut_id=shortcut_id,
        name=req.name,
        query=req.query,
        filters=req.filters,
    )
    if not shortcut:
        raise HTTPException(status_code=404, detail="Shortcut not found")
    return {
        "id": shortcut.id,
        "name": shortcut.name,
        "query": shortcut.query,
        "filters": shortcut.filters,
        "created_at": shortcut.created_at,
        "updated_at": shortcut.updated_at,
        "usage_count": shortcut.usage_count,
    }


@router.delete("/shortcuts/{shortcut_id}")
async def delete_shortcut(shortcut_id: str):
    success = shortcut_manager.delete_shortcut(shortcut_id)
    if not success:
        raise HTTPException(status_code=404, detail="Shortcut not found")
    return {"message": "Shortcut deleted successfully"}


@router.post("/shortcuts/{shortcut_id}/execute")
async def execute_shortcut(
    shortcut_id: str,
    limit: int = Query(50),
    offset: int = Query(0),
):
    shortcut = shortcut_manager.get_shortcut(shortcut_id)
    if not shortcut:
        raise HTTPException(status_code=404, detail="Shortcut not found")

    if not search_indexer._initialized:
        search_indexer.initialize()

    filters = shortcut.filters or {}

    search_filter = SearchFilter(
        doc_types=filters.get("doc_types"),
        statuses=filters.get("statuses"),
        server_ids=filters.get("server_ids"),
        server_tags=filters.get("server_tags"),
        tags=filters.get("tags"),
        time_range=_parse_time_range(
            filters.get("start_time"),
            filters.get("end_time"),
        ),
    )

    results, total = search_engine.search(
        query=shortcut.query,
        search_filter=search_filter,
        limit=limit,
        offset=offset,
    )

    shortcut_manager.increment_usage(shortcut_id)

    return {
        "results": [_result_to_dict(r) for r in results],
        "total": total,
        "offset": offset,
        "limit": limit,
        "query": shortcut.query,
        "shortcut_id": shortcut_id,
    }


@router.post("/reindex")
async def reindex():
    result = search_indexer.reindex_all()
    return result


@router.get("/stats")
async def get_search_stats():
    if not search_indexer._initialized:
        search_indexer.initialize()
    return search_indexer.get_stats()
