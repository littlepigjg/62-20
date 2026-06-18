import re
import time
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from ..config import settings, LOGS_DIR
from .search_engine import search_engine, SearchDocument
from .template import template_manager, ScriptTemplate
from .scheduler import scheduler


class SearchIndexer:
    def __init__(self):
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self._full_reindex()
        self._initialized = True

    def _full_reindex(self) -> None:
        search_engine.clear_index()
        self._index_servers()
        self._index_templates()
        self._index_task_history()
        self._index_log_files()

    def _index_servers(self) -> None:
        for server in settings.servers:
            doc = SearchDocument(
                doc_id=f"server:{server.id}",
                doc_type="server",
                title=server.name,
                content=f"{server.host}:{server.port}\nUsername: {server.username}\nTags: {', '.join(server.tags)}",
                metadata={
                    "id": server.id,
                    "host": server.host,
                    "port": server.port,
                    "username": server.username,
                },
                tags=list(server.tags),
                server_id=server.id,
                server_tags=list(server.tags),
            )
            search_engine.index_document(doc)

    def _index_templates(self) -> None:
        for template in template_manager.list_templates():
            self._index_template(template)

    def _index_template(self, template: ScriptTemplate) -> None:
        try:
            created_ts = datetime.fromisoformat(template.created_at).timestamp()
        except (ValueError, TypeError):
            created_ts = time.time()

        doc = SearchDocument(
            doc_id=f"template:{template.id}",
            doc_type="template",
            title=template.name,
            content=f"{template.description}\n\n{template.script_content}",
            metadata={
                "id": template.id,
                "description": template.description,
                "interpreter": template.interpreter,
                "created_at": template.created_at,
                "updated_at": template.updated_at,
            },
            tags=list(template.tags),
            timestamp=created_ts,
        )
        search_engine.index_document(doc)

    def _index_task_history(self) -> None:
        tasks = scheduler.list_tasks(limit=1000)
        for task in tasks:
            doc = SearchDocument(
                doc_id=f"task:{task.task_id}",
                doc_type="task",
                title=f"{task.command[:80]}{'...' if len(task.command) > 80 else ''}",
                content=f"Command: {task.command}\nScript: {task.script_name or 'N/A'}\n\nOutput:\n{task.stdout}\n{task.stderr}",
                metadata={
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "script_name": task.script_name,
                    "exit_code": task.exit_code,
                },
                tags=[task.status, task.task_type],
                timestamp=task.start_time.timestamp() if task.start_time else None,
                status=task.status,
                server_id=task.server_id,
                server_tags=self._get_server_tags(task.server_id),
            )
            search_engine.index_document(doc)

    def _get_server_tags(self, server_id: Optional[str]) -> List[str]:
        if not server_id:
            return []
        server = settings.get_server(server_id)
        if server:
            return list(server.tags)
        return []

    def _index_log_files(self) -> None:
        log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)
        
        for log_file in log_files[:30]:
            try:
                entries = self._parse_log_file(log_file)
                for entry in entries:
                    doc = SearchDocument(
                        doc_id=f"log:{entry['task_id']}",
                        doc_type="log",
                        title=f"{entry['command'][:80]}{'...' if len(entry['command']) > 80 else ''}",
                        content=f"Command: {entry['command']}\nScript: {entry.get('script_name') or 'N/A'}\n\nOutput:\n{entry['output']}",
                        metadata={
                            "task_id": entry["task_id"],
                            "script_name": entry.get("script_name"),
                            "exit_code": entry.get("exit_code"),
                            "log_file": entry.get("log_file"),
                        },
                        tags=[entry.get("status", "unknown")],
                        timestamp=self._parse_timestamp(entry.get("start_time", "")),
                        status=entry.get("status"),
                        server_id=entry.get("server_id"),
                        server_tags=self._get_server_tags(entry.get("server_id")),
                    )
                    search_engine.index_document(doc)
            except Exception:
                continue

    def _parse_log_file(self, file_path: Path) -> List[dict]:
        entries = []
        try:
            content = file_path.read_text(encoding="utf-8")
            pattern = r"={80}\nTask ID: (.*?)\nServer: (.*?) \((.*?)\)\nCommand: (.*?)\n(?:Script: (.*?)\n)?Start: (.*?)\nEnd: (.*?)\nStatus: (.*?), Exit Code: (.*?)\n-{40} OUTPUT -{40}\n(.*?)\n={80}"
            matches = re.findall(pattern, content, re.DOTALL)

            for m in matches:
                task_id, server_name, server_id, command, script_name, start_time, end_time, status, exit_code, output = m
                entries.append({
                    "task_id": task_id,
                    "server_name": server_name,
                    "server_id": server_id,
                    "command": command,
                    "script_name": script_name if script_name else None,
                    "start_time": start_time,
                    "end_time": end_time,
                    "status": status,
                    "exit_code": int(exit_code) if exit_code != "None" else None,
                    "output": output,
                    "log_file": file_path.name,
                })
        except Exception:
            pass
        return entries

    def _parse_timestamp(self, ts_str: str) -> Optional[float]:
        try:
            return datetime.fromisoformat(ts_str).timestamp()
        except (ValueError, TypeError):
            return None

    def reindex_all(self) -> dict:
        self._full_reindex()
        return {
            "total_docs": search_engine.doc_count,
            "status": "success",
        }

    def reindex_template(self, template_id: str) -> None:
        search_engine.remove_document(f"template:{template_id}")
        template = template_manager.get_template(template_id)
        if template:
            self._index_template(template)

    def reindex_task(self, task_id: str) -> None:
        search_engine.remove_document(f"task:{task_id}")
        task = scheduler.get_task(task_id)
        if task:
            doc = SearchDocument(
                doc_id=f"task:{task.task_id}",
                doc_type="task",
                title=f"{task.command[:80]}{'...' if len(task.command) > 80 else ''}",
                content=f"Command: {task.command}\nScript: {task.script_name or 'N/A'}\n\nOutput:\n{task.stdout}\n{task.stderr}",
                metadata={
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "script_name": task.script_name,
                    "exit_code": task.exit_code,
                },
                tags=[task.status, task.task_type],
                timestamp=task.start_time.timestamp() if task.start_time else None,
                status=task.status,
                server_id=task.server_id,
                server_tags=self._get_server_tags(task.server_id),
            )
            search_engine.index_document(doc)

    def reindex_servers(self) -> None:
        old_ids = [
            doc_id for doc_id in search_engine._documents
            if doc_id.startswith("server:")
        ]
        for doc_id in old_ids:
            search_engine.remove_document(doc_id)
        self._index_servers()

    def on_task_done(self, task_id: str) -> None:
        if not self._initialized:
            return
        try:
            self.reindex_task(task_id)
        except Exception:
            pass

    def on_template_changed(self, template_id: str) -> None:
        if not self._initialized:
            return
        try:
            self.reindex_template(template_id)
        except Exception:
            pass

    def on_servers_changed(self) -> None:
        if not self._initialized:
            return
        try:
            self.reindex_servers()
        except Exception:
            pass

    def get_stats(self) -> dict:
        type_counts = {}
        for doc in search_engine._documents.values():
            type_counts[doc.doc_type] = type_counts.get(doc.doc_type, 0) + 1

        return {
            "total_docs": search_engine.doc_count,
            "by_type": type_counts,
            "initialized": self._initialized,
        }


search_indexer = SearchIndexer()
