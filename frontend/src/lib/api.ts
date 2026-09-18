import {
  QueryRequest,
  QueryResponse,
  TicketCreateRequest,
  TicketResolveRequest,
  TicketResponse,
  KnowledgeArticle,
  KnowledgeIngestRequest,
  CryptoPriceResponse,
  WarningResponse,
  WarningListResponse,
  BotSettingResponse,
  WhitelistCheckResponse,
  HealthResponse,
  ApiError,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

function getHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred';
    try {
      const data = await response.json();
      errorDetail = data.detail || data.message || JSON.stringify(data);
    } catch {
      errorDetail = response.statusText || errorDetail;
    }
    const error: ApiError = {
      message: errorDetail,
      status: response.status,
      detail: errorDetail,
    };
    throw error;
  }
  return response.json();
}

export const api = {
  /**
   * GET /health - Check backend health and database connectivity
   */
  async checkHealth(): Promise<HealthResponse> {
    try {
      const res = await fetch(`${API_URL}/health`, {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<HealthResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Could not connect to backend server on port 8000.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * POST /api/query - Submit question to knowledge base / AI
   */
  async querySupport(request: QueryRequest): Promise<QueryResponse> {
    try {
      const res = await fetch(`${API_URL}/api/query`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(request),
      });
      return await handleResponse<QueryResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to query knowledge base.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * POST /api/tickets - Create a new ticket (escalation)
   */
  async createTicket(request: TicketCreateRequest): Promise<TicketResponse> {
    try {
      const res = await fetch(`${API_URL}/api/tickets`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(request),
      });
      return await handleResponse<TicketResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to submit support ticket.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/tickets - List tickets with status or user_id filtering
   */
  async getTickets(userId?: number, statusFilter?: string): Promise<TicketResponse[]> {
    try {
      const url = new URL(`${API_URL}/api/tickets`);
      if (userId !== undefined && userId !== null) {
        url.searchParams.set('user_id', String(userId));
      }
      if (statusFilter) {
        url.searchParams.set('status_filter', statusFilter);
      }
      const res = await fetch(url.toString(), {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<TicketResponse[]>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to fetch tickets list.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/tickets/{ticket_id} - Single ticket detail
   */
  async getTicket(ticketId: number, userId?: number): Promise<TicketResponse> {
    try {
      const url = new URL(`${API_URL}/api/tickets/${ticketId}`);
      if (userId !== undefined && userId !== null) {
        url.searchParams.set('user_id', String(userId));
      }
      const res = await fetch(url.toString(), {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<TicketResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to fetch ticket #${ticketId}.`,
        status: 0,
      } as ApiError;
    }
  },

  /**
   * POST /api/tickets/{ticket_id}/resolve - Resolve a ticket
   */
  async resolveTicket(ticketId: number, request: TicketResolveRequest): Promise<TicketResponse> {
    try {
      const res = await fetch(`${API_URL}/api/tickets/${ticketId}/resolve`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(request),
      });
      return await handleResponse<TicketResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to resolve ticket #${ticketId}.`,
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/knowledge - List knowledge base articles
   */
  async getKnowledgeArticles(limit = 50, offset = 0): Promise<KnowledgeArticle[]> {
    try {
      const url = new URL(`${API_URL}/api/knowledge`);
      url.searchParams.set('limit', String(limit));
      url.searchParams.set('offset', String(offset));

      const res = await fetch(url.toString(), {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<KnowledgeArticle[]>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to fetch knowledge base articles.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * POST /api/knowledge/ingest - Ingest a new article into Knowledge Base
   */
  async ingestKnowledgeArticle(request: KnowledgeIngestRequest): Promise<KnowledgeArticle> {
    try {
      const res = await fetch(`${API_URL}/api/knowledge/ingest`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(request),
      });
      return await handleResponse<KnowledgeArticle>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to ingest knowledge article.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/crypto/{symbol} - Get live price for an asset symbol
   */
  async getCryptoPrice(symbol: string): Promise<CryptoPriceResponse> {
    try {
      const res = await fetch(`${API_URL}/api/crypto/${symbol.toLowerCase()}`, {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<CryptoPriceResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to fetch price for ${symbol}.`,
        status: 0,
      } as ApiError;
    }
  },

  /**
   * Get live market prices for all standard supported assets
   */
  async getCryptoPrices(symbols = ['btc', 'eth', 'firo', 'sol', 'ltc', 'doge', 'xrp']): Promise<CryptoPriceResponse[]> {
    const results = await Promise.allSettled(
      symbols.map((sym) => this.getCryptoPrice(sym))
    );
    const fulfilled: CryptoPriceResponse[] = [];
    for (const r of results) {
      if (r.status === 'fulfilled') {
        fulfilled.push(r.value);
      }
    }
    return fulfilled;
  },

  /**
   * POST /api/moderation/warnings - Issue a moderation warning
   */
  async createWarning(payload: {
    user_id: number;
    group_id: number;
    warned_by: string;
    reason?: string;
  }): Promise<WarningResponse> {
    try {
      const res = await fetch(`${API_URL}/api/moderation/warnings`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload),
      });
      return await handleResponse<WarningResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to create moderation warning.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/moderation/warnings - List moderation warnings for a user & group
   */
  async getWarnings(userId: number, groupId = -1001234567890): Promise<WarningListResponse> {
    try {
      const url = new URL(`${API_URL}/api/moderation/warnings`);
      url.searchParams.set('user_id', String(userId));
      url.searchParams.set('group_id', String(groupId));

      const res = await fetch(url.toString(), {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<WarningListResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to fetch warnings for user #${userId}.`,
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/admin/settings/{key} - Get a specific bot setting
   */
  async getAdminSetting(key: string): Promise<BotSettingResponse> {
    try {
      const res = await fetch(`${API_URL}/api/admin/settings/${key}`, {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<BotSettingResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to fetch setting ${key}.`,
        status: 0,
      } as ApiError;
    }
  },

  /**
   * PUT /api/admin/settings/{key} - Update a bot setting
   */
  async setAdminSetting(key: string, value: string, updatedBy = 'Admin Web'): Promise<BotSettingResponse> {
    try {
      const res = await fetch(`${API_URL}/api/admin/settings/${key}`, {
        method: 'PUT',
        headers: getHeaders(),
        body: JSON.stringify({ value, updated_by: updatedBy }),
      });
      return await handleResponse<BotSettingResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to update setting ${key}.`,
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/admin/whitelist - List all whitelisted admin user IDs
   */
  async listWhitelist(): Promise<{ entries: { user_id: number; added_by: string; created_at: string }[] }> {
    try {
      const res = await fetch(`${API_URL}/api/admin/whitelist`, {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<{ entries: { user_id: number; added_by: string; created_at: string }[] }>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to fetch whitelist entries.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * POST /api/admin/whitelist - Add a user to the whitelist
   */
  async addWhitelist(userId: number, addedBy = 'Admin Web'): Promise<{ user_id: number; added_by: string }> {
    try {
      const res = await fetch(`${API_URL}/api/admin/whitelist`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ user_id: userId, added_by: addedBy }),
      });
      return await handleResponse<{ user_id: number; added_by: string }>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: 'Failed to add user to whitelist.',
        status: 0,
      } as ApiError;
    }
  },

  /**
   * DELETE /api/admin/whitelist/{user_id} - Remove user from whitelist
   */
  async removeWhitelist(userId: number): Promise<{ removed: boolean; user_id: number }> {
    try {
      const res = await fetch(`${API_URL}/api/admin/whitelist/${userId}`, {
        method: 'DELETE',
        headers: getHeaders(),
      });
      return await handleResponse<{ removed: boolean; user_id: number }>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to remove user #${userId} from whitelist.`,
        status: 0,
      } as ApiError;
    }
  },

  /**
   * GET /api/admin/whitelist/{user_id}/check - Check if a user is whitelisted
   */
  async checkWhitelist(userId: number): Promise<WhitelistCheckResponse> {
    try {
      const res = await fetch(`${API_URL}/api/admin/whitelist/${userId}/check`, {
        method: 'GET',
        headers: getHeaders(),
        cache: 'no-store',
      });
      return await handleResponse<WhitelistCheckResponse>(res);
    } catch (err: unknown) {
      if ((err as ApiError)?.message) throw err;
      throw {
        message: `Failed to check whitelist status for user #${userId}.`,
        status: 0,
      } as ApiError;
    }
  },
};
