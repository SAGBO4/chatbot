from typing import Optional, Dict, Any
import httpx
from backend.config import settings


class BackendClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = (base_url or settings.BACKEND_URL).rstrip("/")
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        """Closes the underlying HTTP client session if owned by this instance."""
        if self._client is not None and not self._client.is_closed and self._owns_client:
            await self._client.aclose()

    def _headers(self) -> Dict[str, str]:
        # Authenticates this client to the backend API (see backend/main.py
        # verify_api_key). Sent even if empty/unset so a misconfigured bot
        # fails loudly (401/503) instead of silently talking to an unprotected
        # backend.
        return {"X-API-Key": settings.API_KEY} if settings.API_KEY else {}

    async def query(
        self, query: str, user_id: int, user_handle: Optional[str] = None
    ) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/query",
            json={"query": query, "user_id": user_id, "user_handle": user_handle},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def create_ticket(
        self,
        user_id: int,
        user_handle: Optional[str],
        question: str,
        automated_answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/tickets",
            json={
                "user_id": user_id,
                "user_handle": user_handle,
                "question": question,
                "automated_answer": automated_answer,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def resolve_ticket(
        self,
        ticket_id: int,
        solution: str,
        resolved_by: Optional[str] = None,
        add_to_knowledge_base: bool = True,
    ) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/tickets/{ticket_id}/resolve",
            json={
                "solution": solution,
                "resolved_by": resolved_by,
                "add_to_knowledge_base": add_to_knowledge_base,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def attach_support_card(self, ticket_id: int, message_id: int) -> Dict[str, Any]:
        """
        Records the Telegram message id of the ticket card posted to the
        Support Group, so a later agent reply can be resolved by message
        identity rather than by parsing the card's text.
        """
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/tickets/{ticket_id}/support-card",
            json={"message_id": message_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_ticket_by_support_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Looks up a ticket by the Telegram message id of its support-group
        card. Returns None if no ticket matches (rather than raising), since
        callers treat "not found" as an expected fallback path.
        """
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/api/tickets/by-support-message/{message_id}",
            headers=self._headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def create_warning(
        self,
        user_id: int,
        group_id: int,
        warned_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/moderation/warnings",
            json={
                "user_id": user_id,
                "group_id": group_id,
                "warned_by": warned_by,
                "reason": reason,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def list_warnings(self, user_id: int, group_id: int) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/api/moderation/warnings",
            params={"user_id": user_id, "group_id": group_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_crypto_price(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches market data for a crypto asset symbol.

        Raises httpx.HTTPStatusError with response.status_code == 404 for an
        unrecognized symbol, or 503 when the market-data provider is
        temporarily unavailable - callers distinguish the two to match the
        crypto-market-data spec's separate scenarios.
        """
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/api/crypto/{symbol}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_setting(self, key: str) -> Optional[str]:
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/api/admin/settings/{key}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json().get("value")

    async def set_setting(self, key: str, value: Optional[str], updated_by: Optional[str] = None) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.put(
            f"{self.base_url}/api/admin/settings/{key}",
            json={"value": value, "updated_by": updated_by},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def whitelist_add(self, user_id: int, added_by: str) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/admin/whitelist",
            json={"user_id": user_id, "added_by": added_by},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def whitelist_remove(self, user_id: int) -> bool:
        client = await self._get_client()
        resp = await client.delete(
            f"{self.base_url}/api/admin/whitelist/{user_id}",
            headers=self._headers(),
        )
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    async def is_whitelisted(self, user_id: int) -> bool:
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/api/admin/whitelist/{user_id}/check",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return bool(resp.json().get("is_whitelisted"))
