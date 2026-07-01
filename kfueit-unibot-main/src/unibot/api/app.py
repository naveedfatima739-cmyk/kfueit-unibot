from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
import structlog

from unibot.api.pipeline_factory import build_query_runtime
from unibot.settings import (
    Settings,
    get_settings,
    resolve_grounding_verifier_backend,
    retrieval_quality_warning,
)

logger = structlog.get_logger(__name__)


def _ensure_serving_generation(
    settings: Settings,
    qdrant_client: QdrantClient | None,
) -> None:
    from qdrant_client import models as _models
    from sqlalchemy import delete, select, update
    from unibot.db.models import CanonicalRecord, ServingGeneration
    from unibot.db.session import direct_session_scope
    from unibot.indexing.provider_factory import create_embedding_provider
    from unibot.indexing.qdrant_writer import QdrantWriter
    from unibot.indexing.serving_generation_builder import ServingGenerationBuilder

    resolved_qdrant = qdrant_client or QdrantClient(
        url=str(settings.qdrant_url),
        api_key=settings.qdrant_api_key,
        timeout=120,
    )

    with direct_session_scope() as session:
        active = session.execute(
            select(ServingGeneration).where(ServingGeneration.status == "active")
        ).scalar_one_or_none()

    if active is not None:
        logger.info("app.auto_build_skipped", reason="active_generation_exists")
        return

    # Full reset of stale state (DB + Qdrant)
    logger.info("app.auto_build_reset", detail="cleaning stale serving state")

    try:
        aliases = resolved_qdrant.get_aliases().aliases
        for alias in aliases:
            if alias.alias_name == "unibot-active":
                resolved_qdrant.update_collection_aliases(
                    [_models.DeleteAliasOperation(
                        delete_alias=_models.DeleteAlias(alias_name=alias.alias_name)
                    )]
                )
                break

        collections = [
            c.name for c in resolved_qdrant.get_collections().collections
            if c.name.startswith("unibot-generation")
        ]
        for name in collections:
            resolved_qdrant.delete_collection(name)
    except Exception:
        logger.exception("app.auto_build_qdrant_cleanup_failed")
        return

    with direct_session_scope() as session:
        session.execute(delete(ServingGeneration))
        session.execute(
            update(CanonicalRecord)
            .where(CanonicalRecord.serving_status == "indexed_active")
            .values(serving_status="eligible")
        )
        session.commit()

    logger.info("app.auto_build_start", detail="building serving generation v1")

    try:
        from unibot.db.repositories.serving_generations import (
            ServingGenerationRepository,
        )
        from unibot.db.session import get_direct_session_factory

        session_factory = get_direct_session_factory()
        embedding_provider = create_embedding_provider(settings=settings)
        builder = ServingGenerationBuilder(
            session_factory=session_factory,
            generation_repository=ServingGenerationRepository(session_factory=session_factory),
            qdrant_writer=QdrantWriter(resolved_qdrant),
            embedding_provider=embedding_provider,
            alias_name="unibot-active",
            collection_prefix="unibot-generation",
        )
        result = builder.build_and_activate(generation_label="v1")
        logger.info(
            "app.auto_build_done",
            generation_label="v1",
            active_count=len(result.record_version_ids),
        )
    except Exception:
        logger.exception("app.auto_build_failed")


def create_app(
    *,
    session_factory: Callable[[], Session] | None = None,
    qdrant_client: QdrantClient | None = None,
    close_sessions: bool = True,
    admin_api_key: str | None = None,
    enable_admin_auth: bool = True,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else get_settings()

    owns_qdrant_client = False
    if qdrant_client is None:
        qdrant_url = getattr(resolved_settings, "qdrant_url", None)
        if qdrant_url is not None:
            qdrant_client = QdrantClient(
                url=str(qdrant_url),
                api_key=getattr(resolved_settings, "qdrant_api_key", None),
            )
            owns_qdrant_client = True

    runtime = build_query_runtime(resolved_settings)

    if resolve_grounding_verifier_backend(resolved_settings) == "lettucedetect":
        from unibot.answering.grounding import warm_detector

        from unibot.answering.grounding import _DEFAULT_MODEL_PATH

        grounding_model = getattr(
            resolved_settings, "grounding_model", _DEFAULT_MODEL_PATH,
        )
        warm_detector(grounding_model)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        _ensure_serving_generation(resolved_settings, qdrant_client)
        yield
        if runtime.async_cleanup is not None:
            await runtime.async_cleanup()
        else:
            runtime.cleanup()
        if owns_qdrant_client and qdrant_client is not None:
            qdrant_client.close()

    app = FastAPI(title="UniBot API", lifespan=lifespan)

    @app.get("/")
    async def root():
        return {"status": "ok", "service": "UniBot API"}

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_ui():
        return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UniBot Chat</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; height: 100vh; display: flex; justify-content: center; align-items: center; }
  .chat-container { width: 700px; max-width: 95vw; height: 85vh; background: white; border-radius: 16px; box-shadow: 0 2px 20px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
  .header { background: #1a73e8; color: white; padding: 18px 24px; font-size: 18px; font-weight: 600; }
  .messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
  .message { max-width: 85%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 14px; white-space: pre-wrap; }
  .user { background: #1a73e8; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
  .bot { background: #f0f2f5; color: #1a1a1a; align-self: flex-start; border-bottom-left-radius: 4px; }
  .bot a { color: #1a73e8; }
  .input-area { display: flex; gap: 8px; padding: 16px 20px; border-top: 1px solid #e0e0e0; background: white; }
  .input-area input { flex: 1; padding: 12px 16px; border: 1px solid #e0e0e0; border-radius: 24px; font-size: 14px; outline: none; }
  .input-area input:focus { border-color: #1a73e8; }
  .input-area button { padding: 12px 24px; background: #1a73e8; color: white; border: none; border-radius: 24px; font-size: 14px; font-weight: 500; cursor: pointer; }
  .input-area button:disabled { opacity: 0.6; cursor: not-allowed; }
  .typing { color: #666; font-style: italic; }
  .error { background: #fdecea; color: #c62828; align-self: flex-start; border-bottom-left-radius: 4px; }
</style>
</head>
<body>
<div class="chat-container">
  <div class="header">KFUEIT UniBot</div>
  <div class="messages" id="messages"></div>
  <div class="input-area">
    <input type="text" id="input" placeholder="Ask about KFUEIT..." onkeydown="if(event.key==='Enter') send()">
    <button id="sendBtn" onclick="send()">Send</button>
  </div>
</div>
<script>
const api = "/query";
const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");

function addMessage(text, cls) {
  const div = document.createElement("div");
  div.className = "message " + cls;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "message bot typing";
  div.id = "typing";
  div.textContent = "Thinking...";
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById("typing");
  if (el) el.remove();
}

async function send() {
  const q = inputEl.value.trim();
  if (!q) return;
  addMessage(q, "user");
  inputEl.value = "";
  sendBtn.disabled = true;
  showTyping();
  try {
    const res = await fetch(api, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query_text: q }) });
    const data = await res.json();
    hideTyping();
    if (data.status === "answered") {
      addMessage(data.answer_text, "bot");
    } else {
      addMessage("Sorry, I couldn't find an answer.", "bot");
    }
  } catch (e) {
    hideTyping();
    addMessage("Network error: " + e.message, "error");
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}
</script>
</body>
</html>"""

    app.state.session_factory = session_factory
    app.state.qdrant_client = qdrant_client
    app.state.close_sessions = close_sessions
    app.state.enable_admin_auth = enable_admin_auth
    if admin_api_key is None:
        admin_api_key = getattr(resolved_settings, "admin_api_key", None)
    app.state.admin_api_key = admin_api_key
    app.state.settings = resolved_settings
    app.state.embedding_provider = runtime.embedding_provider
    app.state.reranker = runtime.reranker
    app.state.answering_service = runtime.answering_service
    app.state.semantic_classifier = runtime.semantic_classifier
    app.state.query_rewriter = runtime.query_rewriter

    if warning := retrieval_quality_warning(resolved_settings):
        logger.warning("runtime.retrieval_quality", warning=warning)

    from unibot.api.routes.admin import router as admin_router
    from unibot.api.routes.query import router as query_router

    app.include_router(query_router)
    app.include_router(admin_router)
    return app
