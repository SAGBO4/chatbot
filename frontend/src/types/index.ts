export interface QueryRequest {
  query: string;
  user_id?: number | null;
  user_handle?: string | null;
}

export interface QueryResponse {
  query: string;
  found: boolean;
  confidence: number;
  answer: string;
  article_id?: number | null;
  requires_resolution_confirmation?: boolean;
}

export interface TicketCreateRequest {
  user_id: number;
  user_handle?: string | null;
  question: string;
  automated_answer?: string | null;
}

export type TicketStatus = 'OPEN' | 'PENDING' | 'RESOLVED' | 'CLOSED';

export interface TicketResponse {
  id: number;
  user_id: number;
  user_handle?: string | null;
  question: string;
  status: TicketStatus | string;
  automated_answer?: string | null;
  solution?: string | null;
  resolved_by?: string | null;
  resolution_channel?: string | null;
  created_at: string;
  resolved_at?: string | null;
  support_group_message_id?: number | null;
  is_newly_resolved?: boolean | null;
}

export interface TicketResolveRequest {
  solution: string;
  resolved_by?: string | null;
  resolution_channel?: string | null;
  add_to_knowledge_base?: boolean;
}

export interface KnowledgeArticle {
  id: number;
  question: string;
  solution: string;
  keywords?: string | null;
  source_ticket_id?: number | null;
  created_at: string;
}

export interface KnowledgeIngestRequest {
  question: string;
  solution: string;
  keywords?: string | null;
  source_ticket_id?: number | null;
}

export interface KnowledgeStatsResponse {
  total_articles: number;
  resolved_tickets_indexed?: number;
  status?: string;
}

export interface CryptoPriceResponse {
  symbol: string;
  price_usd: number;
  change_24h_pct: number;
  market_cap_usd: number;
  volume_24h_usd: number;
}

export interface WarningResponse {
  id: number;
  user_id: number;
  group_id: number;
  reason?: string | null;
  warned_by: string;
  created_at: string;
}

export interface WarningListResponse {
  count: number;
  warnings: WarningResponse[];
}

export interface BotSettingResponse {
  key: string;
  value?: string | null;
}

export interface WhitelistCheckResponse {
  user_id: number;
  is_whitelisted: boolean;
}

export interface HealthResponse {
  status: string;
  database?: string;
  service?: string;
}

export interface ApiError {
  message: string;
  status?: number;
  detail?: string;
}
