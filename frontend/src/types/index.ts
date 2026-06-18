export interface ServerConfig {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  password: string;
  private_key: string;
  tags: string[];
}

export interface ExecutionResult {
  task_id: string;
  server_id: string;
  server_name: string;
  command: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  start_time: string;
  end_time: string | null;
  status: 'pending' | 'running' | 'success' | 'failed' | 'error';
}

export interface StreamMessage {
  type: 'output' | 'status';
  task_id: string;
  server_id: string;
  server_name: string;
  stream: 'stdout' | 'stderr' | '';
  content: string;
  exit_code: number | null;
  status: string;
  timestamp: string;
}

export interface ScriptTemplate {
  id: string;
  name: string;
  description: string;
  script_content: string;
  interpreter: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface LogEntry {
  task_id: string;
  server_name: string;
  server_id: string;
  command: string;
  script_name: string | null;
  start_time: string;
  end_time: string;
  status: string;
  exit_code: number | null;
  output: string;
  log_file: string;
}

export interface CommandExecuteRequest {
  server_ids: string[];
  command: string;
  timeout?: number;
  env?: Record<string, string>;
}

export interface ScriptExecuteRequest {
  server_ids: string[];
  script_content: string;
  script_name?: string;
  interpreter?: string;
  args?: string[];
  timeout?: number;
}

export interface SearchResultItem {
  doc_id: string;
  doc_type: string;
  title: string;
  content: string;
  metadata: Record<string, any>;
  tags: string[];
  timestamp: string | null;
  status: string | null;
  server_id: string | null;
  server_tags: string[];
  score: number;
  highlights: string[];
  matched_terms: string[];
}

export interface SearchSuggestion {
  text: string;
  type: string;
  count?: number;
  similarity?: number;
}

export interface SearchHistoryItem {
  query: string;
  filters: Record<string, any>;
  timestamp: string;
}

export interface SearchShortcut {
  id: string;
  name: string;
  query: string;
  filters: Record<string, any>;
  created_at: string;
  updated_at: string;
  usage_count: number;
}

export interface SearchStats {
  total_docs: number;
  by_type: Record<string, number>;
  initialized: boolean;
}

export interface SearchRequest {
  query: string;
  doc_types?: string[];
  statuses?: string[];
  server_ids?: string[];
  server_tags?: string[];
  tags?: string[];
  start_time?: string;
  end_time?: string;
  limit: number;
  offset: number;
  fuzzy: boolean;
  expand_synonyms: boolean;
  record_history: boolean;
}

export interface SearchResponse {
  results: SearchResultItem[];
  total: number;
  offset: number;
  limit: number;
  query: string;
}

export interface SearchShortcutCreateRequest {
  name: string;
  query: string;
  filters: Record<string, any>;
}
