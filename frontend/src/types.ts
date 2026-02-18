export type AgentName = "yapper" | "definer" | "redditor" | "engager" | "auditor";
export type SaveBucket = "journal" | "definitions" | "threads" | "drafts" | "audit_logs";

export interface ChatRequest {
  message: string;
  active_agent: AgentName;
  enabled_agents: AgentName[];
  model_name: string;
  search_query?: string;
  save_to?: SaveBucket;
}

export interface SearchResult {
  score: number;
  title: string;
  url: string;
  ups: number;
  comments: number;
}

export interface ChatResponse {
  active_agent: AgentName;
  response: string;
  tool_results: SearchResult[];
}
