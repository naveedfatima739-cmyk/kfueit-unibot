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

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KFUEIT UniBot</title>
<link rel="icon" href="https://kfueit.edu.pk/uploads/1/favicon.png">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%); height: 100vh; display: flex; justify-content: center; align-items: center; padding: 16px; }
  .chat-container { width: 720px; max-width: 100%; height: 90vh; background: #fff; border-radius: 12px; box-shadow: 0 8px 32px rgba(21,57,128,0.12); display: flex; flex-direction: column; overflow: hidden; position: relative; }
  .header { background: linear-gradient(135deg, #153980 0%, #0e9856 100%); color: #fff; padding: 18px 24px; display: flex; align-items: center; gap: 14px; }
  .header img { height: 40px; }
  .header-text { flex: 1; }
  .header-text h1 { font-size: 17px; font-weight: 700; letter-spacing: 0.3px; }
  .header-text p { font-size: 11px; opacity: 0.85; margin-top: 2px; }
  .welcome { text-align: center; padding: 40px 24px 32px; border-bottom: 1px solid #f0f0f0; }
  .welcome img { height: 56px; margin-bottom: 14px; }
  .welcome h2 { font-size: 20px; color: #153980; font-weight: 700; }
  .welcome p { font-size: 13px; color: #666; margin-top: 6px; line-height: 1.5; }
  .welcome .suggestions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 18px; }
  .welcome .suggestions button { background: #f0f4f8; border: 1px solid #dce4ec; color: #153980; padding: 8px 16px; border-radius: 20px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
  .welcome .suggestions button:hover { background: #153980; color: #fff; border-color: #153980; }
  .messages { flex: 1; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 12px; }
  .message { max-width: 88%; padding: 13px 18px; line-height: 1.6; font-size: 14px; white-space: pre-wrap; animation: fadeIn 0.25s ease; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  .user { background: linear-gradient(135deg, #153980 0%, #1a4a9e 100%); color: #fff; align-self: flex-end; border-radius: 18px 18px 4px 18px; }
  .bot { background: #f0f4f8; color: #2b2b2b; align-self: flex-start; border-radius: 18px 18px 18px 4px; border-left: 3px solid #22b24c; }
  .bot a { color: #153980; text-decoration: underline; }
  .error { background: #fff0f0; color: #c62828; align-self: flex-start; border-radius: 18px 18px 18px 4px; border-left: 3px solid #c62828; }
  .input-area { display: flex; gap: 10px; padding: 16px 24px; border-top: 1px solid #e8ecf1; background: #fff; }
  .input-area input { flex: 1; padding: 13px 18px; border: 2px solid #e0e4e8; border-radius: 26px; font-size: 14px; outline: none; transition: border-color 0.2s; font-family: inherit; }
  .input-area input:focus { border-color: #153980; }
  .input-area button { padding: 13px 28px; background: linear-gradient(135deg, #22b24c 0%, #1a9a40 100%); color: #fff; border: none; border-radius: 26px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; box-shadow: 0 2px 8px rgba(34,178,76,0.3); white-space: nowrap; }
  .input-area button:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(34,178,76,0.4); }
  .input-area button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
  .footer { text-align: center; padding: 10px 24px; font-size: 11px; color: #999; border-top: 1px solid #f0f0f0; background: #fafafa; }

  .spinner { display: inline-flex; align-items: center; gap: 5px; padding: 6px 0; }
  .spinner .dot { width: 8px; height: 8px; border-radius: 50%; animation: bounce 1.2s infinite; }
  .spinner .dot:nth-child(1) { background: #153980; animation-delay: 0s; }
  .spinner .dot:nth-child(2) { background: #22b24c; animation-delay: 0.2s; }
  .spinner .dot:nth-child(3) { background: #153980; animation-delay: 0.4s; }
  @keyframes bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #d0d4d8; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #b0b4b8; }
</style>
</head>
<body>
<div class="chat-container">
  <div class="header">
    <img src="https://kfueit.edu.pk/uploads/4/ueit-logo-w.png" alt="KFUEIT">
    <div class="header-text">
      <h1>KFUEIT UniBot</h1>
      <p>Khwaja Fareed University of Engineering &amp; Information Technology</p>
    </div>
  </div>
  <div class="messages" id="messages">
    <div class="welcome" id="welcome">
      <img src="https://kfueit.edu.pk/uploads/4/ueit-logo-r.png" alt="KFUEIT">
      <h2>Welcome to KFUEIT UniBot</h2>
      <p>Ask me anything about admissions, programs,<br>fee structure, and more.</p>
      <div class="suggestions">
        <button onclick="quickAsk('What programs does the university offer?')">Programs offered</button>
        <button onclick="quickAsk('What is the admission criteria?')">Admission criteria</button>
        <button onclick="quickAsk('Does the university offer scholarships?')">Scholarships</button>
        <button onclick="quickAsk('What are the research areas?')">Research areas</button>
      </div>
    </div>
  </div>
  <div class="input-area">
    <input type="text" id="input" placeholder="Type your question..." onkeydown="if(event.key==='Enter') send()">
    <button id="sendBtn" onclick="send()">Ask</button>
  </div>
  <div class="footer">&copy; KFUEIT UniBot &mdash; Khwaja Fareed University of Engineering &amp; Information Technology</div>
</div>
<script>
const api = "/query";
const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const welcomeEl = document.getElementById("welcome");

function addMessage(text, cls) {
  welcomeEl.style.display = "none";
  const div = document.createElement("div");
  div.className = "message " + cls;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showSpinner() {
  welcomeEl.style.display = "none";
  const div = document.createElement("div");
  div.className = "message bot";
  div.id = "spinnerMsg";
  div.innerHTML = '<div class="spinner"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideSpinner() {
  const el = document.getElementById("spinnerMsg");
  if (el) el.remove();
}

function quickAsk(q) {
  inputEl.value = q;
  send();
}

async function send() {
  const q = inputEl.value.trim();
  if (!q) return;
  addMessage(q, "user");
  inputEl.value = "";
  sendBtn.disabled = true;
  showSpinner();
  try {
    const res = await fetch(api, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query_text: q }) });
    const data = await res.json();
    hideSpinner();
    if (data.status === "answered") {
      addMessage(data.answer_text, "bot");
    } else if (data.status === "abstained") {
      addMessage("I couldn't verify that answer. Please try rephrasing your question.", "bot");
    } else {
      addMessage("I couldn't find an answer. Please try a different question.", "bot");
    }
  } catch (e) {
    hideSpinner();
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
