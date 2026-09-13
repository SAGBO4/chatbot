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
