from typing import Optional, Dict, Any
import httpx
from app.config import settings


class BackendClient:
    """Async HTTP client the bot uses to call the backend API; each request carries `X-API-Key`."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = (base_url or settings.BACKEND_URL).rstrip("/")
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """The shared client, recreated if it was never opened or has been closed."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        """Closes the underlying HTTP client session if owned by this instance."""
        if self._client is not None and not self._client.is_closed and self._owns_client:
            await self._client.aclose()

    def _headers(self) -> Dict[str, str]:
        # Auth for the backend (see verify_api_key in app/security.py). With no API_KEY no header is sent,
        # so a misconfigured bot gets a 401/503 instead of silently working.
        return {"X-API-Key": settings.API_KEY} if settings.API_KEY else {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        not_found_ok: bool = False,
    ) -> Optional[httpx.Response]:
        """
        Call the backend and return the response, raising `httpx.HTTPStatusError` on an error status.

        With `not_found_ok`, a 404 returns None instead of raising, for lookups where "not found" is an
        expected outcome.
        """
        client = await self._get_client()
        options: Dict[str, Any] = {"headers": self._headers()}
        if json is not None:
            options["json"] = json
        if params is not None:
            options["params"] = params
        response = await getattr(client, method)(f"{self.base_url}{path}", **options)
        if not_found_ok and response.status_code == 404:
            return None
        response.raise_for_status()
        return response

    async def query(
        self, query: str, user_id: int, user_handle: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ask the knowledge base (`POST /api/query`)."""
        response = await self._request(
            "post", "/api/query", json={"query": query, "user_id": user_id, "user_handle": user_handle}
        )
        return response.json()

    async def create_ticket(
        self,
        user_id: int,
        user_handle: Optional[str],
        question: str,
        automated_answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Open a support ticket (`POST /api/tickets`)."""
        response = await self._request(
            "post",
            "/api/tickets",
            json={
                "user_id": user_id,
                "user_handle": user_handle,
                "question": question,
                "automated_answer": automated_answer,
            },
        )
        return response.json()

    async def resolve_ticket(
        self,
        ticket_id: int,
        solution: str,
        resolved_by: Optional[str] = None,
        add_to_knowledge_base: bool = True,
    ) -> Dict[str, Any]:
        """Resolve a ticket (`POST /api/tickets/{id}/resolve`)."""
        response = await self._request(
            "post",
            f"/api/tickets/{ticket_id}/resolve",
            json={
                "solution": solution,
                "resolved_by": resolved_by,
                "add_to_knowledge_base": add_to_knowledge_base,
            },
        )
        return response.json()

    async def attach_support_card(self, ticket_id: int, message_id: int) -> Dict[str, Any]:
        """
        Records the Telegram message id of the ticket card posted to the Support
        Group, so a later agent reply can be resolved by message identity
        rather than by parsing the card's text.
        """
        response = await self._request(
            "post", f"/api/tickets/{ticket_id}/support-card", json={"message_id": message_id}
        )
        return response.json()

    async def get_ticket_by_support_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Looks up a ticket by the Telegram message id of its support-group
        card. Returns None if no ticket matches (rather than raising), since
        callers treat "not found" as an expected fallback path.
        """
        response = await self._request(
            "get", f"/api/tickets/by-support-message/{message_id}", not_found_ok=True
        )
        return response.json() if response is not None else None

    async def create_warning(
        self,
        user_id: int,
        group_id: int,
        warned_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a moderation warning (`POST /api/moderation/warnings`)."""
        response = await self._request(
            "post",
            "/api/moderation/warnings",
            json={
                "user_id": user_id,
                "group_id": group_id,
                "warned_by": warned_by,
                "reason": reason,
            },
        )
        return response.json()

    async def list_warnings(self, user_id: int, group_id: int) -> Dict[str, Any]:
        """A user's warnings in a group, with their count (`GET /api/moderation/warnings`)."""
        response = await self._request(
            "get", "/api/moderation/warnings", params={"user_id": user_id, "group_id": group_id}
        )
        return response.json()

    async def get_crypto_price(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches market data for a crypto asset symbol.

        Raises httpx.HTTPStatusError: status 404 for an unknown symbol, 503 when the price provider
        is temporarily unavailable. Callers tell the two apart to show different messages.
        """
        response = await self._request("get", f"/api/crypto/{symbol}")
        return response.json()

    async def get_setting(self, key: str) -> Optional[str]:
        """The value of a persisted bot setting, or None if it was never set."""
        response = await self._request("get", f"/api/admin/settings/{key}")
        return response.json().get("value")

    async def set_setting(self, key: str, value: Optional[str], updated_by: Optional[str] = None) -> Dict[str, Any]:
        """Create or update a persisted bot setting."""
        response = await self._request(
            "put", f"/api/admin/settings/{key}", json={"value": value, "updated_by": updated_by}
        )
        return response.json()

    async def whitelist_add(self, user_id: int, added_by: str) -> Dict[str, Any]:
        """Add a user to the admin whitelist."""
        response = await self._request(
            "post", "/api/admin/whitelist", json={"user_id": user_id, "added_by": added_by}
        )
        return response.json()

    async def whitelist_remove(self, user_id: int) -> bool:
        """Remove a user from the whitelist; False if they were not listed."""
        response = await self._request("delete", f"/api/admin/whitelist/{user_id}", not_found_ok=True)
        return response is not None

    async def is_whitelisted(self, user_id: int) -> bool:
        """Whether the backend counts this user as admin (the bot owner, or whitelisted)."""
        response = await self._request("get", f"/api/admin/whitelist/{user_id}/check")
        return bool(response.json().get("is_whitelisted"))
