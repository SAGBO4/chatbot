from typing import Optional, Dict, Any
import httpx
from backend.config import settings


class BackendClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.BACKEND_URL).rstrip("/")

    async def query(
        self, query: str, user_id: int, user_handle: Optional[str] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/query",
                json={"query": query, "user_id": user_id, "user_handle": user_handle},
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/tickets",
                json={
                    "user_id": user_id,
                    "user_handle": user_handle,
                    "question": question,
                    "automated_answer": automated_answer,
                },
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/tickets/{ticket_id}/resolve",
                json={
                    "solution": solution,
                    "resolved_by": resolved_by,
                    "add_to_knowledge_base": add_to_knowledge_base,
                },
            )
            resp.raise_for_status()
            return resp.json()
