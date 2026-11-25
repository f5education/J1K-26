ShopAI chat handoff: architecture and rebuild guide
This document specifies the current ShopAI chat so another agent can recreate it in a different application or hosting system. Preserve the browser contract, provider-specific authentication and request formats, conversation behavior, and security boundaries described here. Provider credentials belong on the server, never in browser code.
1. Components to rebuild
File
Responsibility
public/index.html & public/css/styles.css
Minimal, responsive "<SHOP_NAME> — ShopAI" storefront (`<SHOP_NAME>` chosen by the admin when running the prompt): sticky top navbar (brand mark + `<SHOP_NAME>`, live search input, Full Chat link, and Bag button with item counter) directly above the category filter pills, sort control, 8-item sports product grid, quick-view size modal, slide-over shopping bag drawer, and demo checkout (no hero/promotional banner).
public/chat.html & public/css/chat.css
Accessible chat page and ?widget=1 iframe layout, compact single-line header, ARIA message log with minimal greeting banner ("How can I help gear up your next session?"—no prompt-chip list or filler paragraph), typing indicator, error alert, character counter, and aligned 44px auto-expanding composer form.
public/js/chat.js
Browser chat behavior (documented block-by-block with what each function/section does and why): load server config once, post text/plain JSON messages, render replies safely via textContent, keep an opaque conversation ID, and clear/cancel a session via AbortController.
public/js/app.js
Storefront behavior (documented block-by-block with what each function/section does and why): catalog filters, search/sort, product modal, localStorage shopping bag (shopai_sports_bag_v1), and demo checkout. It is not the chat API client.
public/js/products.js, public/js/widget.js, public/js/catalog-guide.js
Local 8-product sports catalog data; floating chat launcher that keeps the /chat.html?widget=1 iframe mounted while minimized and syncs mobile visualViewport height; optional local catalog suggestion cards matched after assistant replies (skipped on policy blocks).
app/main.py
FastAPI server (documented block-by-block with docstrings and section comments explaining what each block does and why): validated configuration (including localhost-only SSL_VERIFY dev toggle), request validation, provider selection/authentication, bounded conversation state, normalized replies, explicit static routes, and /healthz + /api/client-config routes.
requirements.txt & Dockerfile
Pinned Python dependencies and non-root port-80 container build, both commented inline by default to explain the purpose and necessity of every package, environment flag, Linux capability, and build layer.
2. Architecture
~mermaid
flowchart LR
U[Browser user] -->|HTTPS page request| W[Azure Web App / container]
W -->|pull selected image tag| R[ACR or Docker Hub]
R -->|container image| C[FastAPI plus public files]
U -->|same-origin POST /api/proxy| C
C -->|CHAT_BACKEND selects one| B{Backend}
B -->|f5 bearer token| F[F5 Guardrails connection]
B -->|foundry_agent managed identity token| A[Foundry project agent]
B -->|foundry_openai API key| M[Azure OpenAI or Foundry model]
F -->|provider result| C
A -->|Responses API result| C
M -->|Chat Completions result| C
C -->|normalized JSON and optional opaque conversationId| U
~
The registry supplies the image when the host deploys or restarts the container. It is not involved in each chat request. The container serves both the web assets and the API. It must receive settings at runtime; do not bake the real .env or credentials into the image.
3. Browser/server API contract
Configuration & Active Backend Indicator
`GET /api/client-config` returns the same-origin `chatPath` plus the safe active-backend mode and human-readable label (so both the storefront home page navbar `#backend-status-pill` and chat header `#chat-backend-pill` show at a glance whether the user is chatting with `F5 AI Guardrails (CAI)`, `Azure AI Foundry Agent`, or `Azure OpenAI (Direct)`—and the server also logs `ShopAI startup: active_backend=...` on boot):
~json
{"chatPath":"/api/proxy","backendMode":"f5","backendLabel":"F5 AI Guardrails (CAI)"}
~
The browser validates that `chatPath` begins with one slash and is not a protocol-relative URL, caches it for that page, and renders the active backend badge safely via `textContent`. Do not expose upstream URLs/endpoints, CAI project names, Foundry agent names, model names, tokens, or identity details in this response.
Chat request
The browser POSTs JSON text using Content-Type: text/plain to the discovered same-origin chatPath:
~json
{"input":"I want to buy a ball","lang":"en"}
~
Follow-up includes the opaque ID returned by the server:
~json
{"input":"For outdoor play","lang":"en","conversationId":"opaque-id-issued-by-this-app"}
~
Fields:
input: required string, 1–500 characters; reject whitespace-only.
lang: optional string, default en, max 32. Currently accepted but does not change the prompt.
conversationId: optional string, max 1024. This is an app-issued lookup key, not an upstream provider ID.
Ignore unknown fields. Never accept browser overrides for backend, endpoint, model, agent, system prompt, or provider response pointer.
Normalize successful responses to:
~json
{"response":"Assistant reply text"}
~
F5 and Foundry agent mode also return a new opaque conversationId. Direct foundry_openai currently returns no conversation ID and is stateless. Errors are non-2xx JSON such as {"error":"Chat service unavailable"}. Do not pass raw provider diagnostics to the browser.
Browser behavior
chat.js handles form submission, Enter-to-send, Shift+Enter newline, auto-sizing input height (44px single-line default without an inner scrollbar, growing smoothly up to 132px), empty-input checks, serialization of sends, typing state, and New conversation. It fetches chatPath once, sends only the user message, lang, and optional opaque conversationId, then displays response. It uses AbortController to cancel a pending request on New. It does not stream: the complete response appears when the request finishes.
Render all user/provider text with textContent or an equivalent safe text API. Never insert messages as HTML. The iframe reports same-origin reply/browse events to its parent. widget.js owns the floating launcher, keeps the iframe mounted while minimized, and handles mobile viewport/keyboard behavior. app.js owns shopping state and does not call a model or provider.
4. The three backends
CHAT_BACKEND allows exactly f5, foundry_agent, or foundry_openai. Default CHAT_BACKEND to f5 (so chat requests go through F5 AI Guardrails out of the box, and admins can switch CHAT_BACKEND later if needed). There is no automatic/silent fallback between backends.
F5 Guardrails: f5
Required settings:
Variable
Purpose
F5_GUARDRAILS_API_TOKEN
F5 API token. Secret.
F5_GUARDRAILS_BASE_URL
SaaS origin only, e.g. https://us2.calypsoai.app (default) or https://us1.calypsoai.app. No connection or API path.
F5_GUARDRAILS_CONNECTION_NAME
Exact F5 CAI Project / Connection name configured in the F5 AI Guardrails console (e.g. your-cai-project-name). Dynamically URL-encoded into `/openai/{connection}/chat/completions` so any CAI project name set by the admin works automatically.
F5_GUARDRAILS_MODEL
Model name expected by that connection, e.g. your-AI-model-on-CAI (such as gpt-4.1).
Request:
POST {F5_GUARDRAILS_BASE_URL}/openai/{URL-encoded connection name}/chat/completions
Authorization: Bearer {F5_GUARDRAILS_API_TOKEN}
Content-Type: application/json
Body: model plus messages array. First turn has the user message; follow-up adds retained user/assistant turns.
Parse OpenAI Chat Completions at choices[0].message.content.
The app retains at most 40 messages (20 turns) per F5 session, expires sessions after 30 minutes, and caps the in-memory session map at 1,000. Every response gives the browser a newly generated opaque ID; keep provider state and message history server-side.
A policy block is recognized only when the F5 response is HTTP 400 and error.cai_error.outcome equals blocked. Note that on F5's OpenAI-compatible endpoint (`/openai/{connection}/chat/completions`), top-level `error.message` is always the generic wrapper `"CAI guardrails blocked the prompt"` (or `"CAI guardrails blocked the response"`), while the actual per-guardrail responses live inside `error.cai_error.scanner_results` (array of scanner objects with `outcome`, `scanner_name`, and `message`):
- If `error.cai_error.response` / `custom_response` is a non-empty custom string, return it.
- Otherwise inspect failed scanners in `error.cai_error.scanner_results` (`outcome` in `("failed", "blocked")`): if one or more failed scanners carry a non-empty `message` (set when an admin saves a custom guardrail response in F5, e.g. `"This topic is blocked by company policy via F5 CAI"`), return those unique custom message(s); if failed scanners have `message: null` (F5's unedited default), construct F5's exact default guardrail response `"This message has been blocked by {scanner_name}"` (e.g. `"This message has been blocked by Financial advice guardrail"` or `"This message has been blocked by f5"`).
- Fall back to non-generic `error.message`, or `"This subject is blocked by your company's chat policy. I can help with sports products, gear, sizing, and training instead."` only if F5 provides no message or scanner name at all.
Return HTTP 200 with that extracted `response` and rotated opaque `conversationId`, strip internal `cai_error` scanner IDs/metadata, and do not add the blocked prompt to history. Other errors are not policy blocks.
Saved Azure AI Foundry agent: foundry_agent
Required settings:
Variable
Purpose
FOUNDRY_PROJECT_ENDPOINT
Project URL, e.g. https://raceweekeastus-resource.services.ai.azure.com/api/projects/raceweekeastus.
FOUNDRY_AGENT_NAME
Saved agent name, e.g. shopAI-Agent; not its model deployment or full URL.
AZURE_CLIENT_ID
Optional client ID when using a user-assigned managed identity. Omit for system-assigned identity.
Setup/authentication:
Enable system-assigned or attach user-assigned managed identity to the actual hosting resource.
Give that identity permission to invoke the agent at the Foundry project/resource scope. Use the Azure AI User role where applicable.
In the server, use Azure Identity ManagedIdentityCredential to obtain a token for https://ai.azure.com/.default. Do not use F5 or model API keys in this mode.
A Web App's identity does not automatically exist inside a local Docker container or an unrelated VM. Configure an appropriate local credential mechanism for development; never place identity tokens in browser code.
Request:
POST {FOUNDRY_PROJECT_ENDPOINT}/agents/{FOUNDRY_AGENT_NAME}/endpoint/protocols/openai/responses?api-version=v1
Authorization: Bearer {Entra token}; Content-Type: application/json
First-turn body: input array with one user role/content item.
Follow-up body adds previous_response_id, resolved from the app's session map.
Require status completed. Extract assistant output_text parts from assistant message output items. This is the Responses API shape, not Chat Completions.
Keep the Foundry response id private. Map it to a random opaque browser ID; accept only IDs issued by this server and still present in the session map. Current TTL and capacity are 30 minutes and 1,000. This is in-memory state; restarts clear it.
Direct Azure OpenAI/Foundry model: foundry_openai
This calls a model deployment directly. It does not use the saved agent's instructions, tools, or knowledge.
Required settings:
Variable
Purpose
AZURE_OPENAI_ENDPOINT
Base URL ending /openai/v1/, e.g. https://your-resource.openai.azure.com/openai/v1/.
FOUNDRY_API_KEY
Model endpoint API key. Secret.
FOUNDRY_AGENT_MODEL
Deployed model name sent as the model field. This variable is for direct-model mode; the saved agent selects its model in Foundry.
Request:
POST {AZURE_OPENAI_ENDPOINT}chat/completions
api-key: {FOUNDRY_API_KEY}; Content-Type: application/json
Body: model and messages containing only the current user turn.
Parse choices[0].message.content.
Current direct-model mode is stateless; it neither sends prior messages nor returns conversationId. Add history only if intentionally changing this behavior.
5. Environment configuration
Exact `.env.example` template (keep Option 1 active/uncommented by default, and keep **every** line of Option 2 and Option 3 commented out with `#` so admins are never confused about which variables are active):
~dotenv
# Shared application settings
PUBLIC_ORIGIN=http://localhost
CHAT_PATH=/api/proxy
CHAT_TIMEOUT_SECONDS=60
PORT=80

# Local Docker dev default (allowed ONLY when PUBLIC_ORIGIN is localhost or 127.0.0.1 so laptop VPN/TLS inspection doesn't block outbound HTTPS).
# IMPORTANT: Set SSL_VERIFY=true whenever PUBLIC_ORIGIN is a real public HTTPS domain (Cloud VM / Azure Web App)—both to verify upstream TLS certificates in production and because startup validation rejects SSL_VERIFY=false on non-localhost origins.
SSL_VERIFY=false

# Explicitly select one backend: f5 | foundry_agent | foundry_openai
CHAT_BACKEND=f5

# --- Option 1: F5 AI Guardrails (default: CHAT_BACKEND=f5) ---
F5_GUARDRAILS_API_TOKEN=your-API-token-generated-on-CAI
F5_GUARDRAILS_BASE_URL=https://us2.calypsoai.app
F5_GUARDRAILS_CONNECTION_NAME=your-cai-project-name
F5_GUARDRAILS_MODEL=your-AI-model-on-CAI
# Option 1 notes / alternate endpoint:
# - F5_GUARDRAILS_CONNECTION_NAME: Exact F5 CAI Project / Connection name configured in the F5 AI Guardrails console
# - F5_GUARDRAILS_MODEL: Model configured on your CAI connection (e.g. gpt-4.1)
# F5_GUARDRAILS_BASE_URL=https://us1.calypsoai.app

# --- Option 2: Saved Azure AI Foundry Agent (keep commented unless CHAT_BACKEND=foundry_agent) ---
# CHAT_BACKEND=foundry_agent
# FOUNDRY_PROJECT_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project
# FOUNDRY_AGENT_NAME=shopAI-Agent
# Optional: set only when using a user-assigned managed identity
# AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000

# --- Option 3: Direct Azure OpenAI / Foundry Model (keep commented unless CHAT_BACKEND=foundry_openai) ---
# CHAT_BACKEND=foundry_openai
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/openai/v1/
# FOUNDRY_API_KEY=replace-with-model-api-key
# FOUNDRY_AGENT_MODEL=your-deployment-name
~
PUBLIC_ORIGIN is the exact public HTTPS origin, including a nonstandard port if used; for local browser/Docker testing only, http://localhost and http://127.0.0.1 (with optional port) are permitted. In .env.example, set PUBLIC_ORIGIN=http://localhost and PORT=80 so running `docker run -p 80:80 --env-file .env` works at http://localhost out of the box without port mismatches. Normalize AZURE_OPENAI_ENDPOINT if the trailing slash after `/openai/v1` is omitted so `{AZURE_OPENAI_ENDPOINT}chat/completions` always resolves to `.../openai/v1/chat/completions`.
Optional local-dev TLS setting: `SSL_VERIFY` defaults to `true` in `Settings` (`verify=settings.ssl_verify` on the shared HTTPX client), while `.env.example` (which sets `PUBLIC_ORIGIN=http://localhost`) sets `SSL_VERIFY=false` uncommented by default so local Docker on laptops behind VPN/TLS inspection works out of the box, accompanied by a clear comment explaining why and when it must be `SSL_VERIFY=true` (required for real TLS verification in production AND enforced by startup validation, which rejects `SSL_VERIFY=false` whenever `PUBLIC_ORIGIN` is not `localhost` or `127.0.0.1`).
CHAT_PATH is an /api/... path other than /api/client-config. CHAT_TIMEOUT_SECONDS defaults to 60 and is capped at 120. PORT defaults to 80. Azure App Service WEBSITES_PORT is routing metadata; Python listens on PORT. Configure the App Service container port as 80.
Read settings from process environment and optionally an untracked local .env. Process environment should override the file. Validate HTTPS endpoints, reject embedded URL credentials/query/fragments, validate the chat path, and require only the settings for the selected backend. Keep .env out of Git and Docker layers; inject secrets at runtime from a secret store or host configuration.
6. Server & frontend code-block documentation (`app/main.py`, `public/js/chat.js`, `public/js/app.js`)
By default, `app/main.py`, `public/js/chat.js`, and `public/js/app.js` MUST include clear inline section headers, docstrings, and JSDoc comments explaining **what** each block of code does and **why** it exists. (Important static-asset comment rule: inside `public/js/*.js` comments, never include forbidden test markers such as `innerHTML`, provider domain names like `calypsoai.app` / `openai.azure.com` / `services.ai.azure.com`, secret env var names, or—inside `app.js`—strings like `fetch(`, `/api/proxy`, or `/api/client-config` so frontend security contract tests remain clean.)

`app/main.py` — Backend blocks (what & why)
- Module docstring & hard bounds (`MAX_REQUEST_BYTES=64 KiB`, `MAX_RESPONSE_BYTES=2 MiB`, `BODY_READ_TIMEOUT_SECONDS=15.0`, `SESSION_TTL_SECONDS=1800.0`, `SESSION_CAPACITY=1000`, `MAX_F5_MESSAGES=40`, `FOUNDRY_SCOPE`, `PUBLIC_DIR`): Documents the gateway responsibilities and caps payloads, slow-body reads, and in-memory state so a single client or upstream fault cannot exhaust container RAM or sockets, while isolating static serving strictly to `public/`.
- Sentinel exceptions (`StartupConfigurationError`, `_BodyTooLargeError`, `_UpstreamResponseTooLargeError`): Separates expected boundary cutoffs (`413` incoming body limit, `502` upstream body limit, startup config validation) from unexpected crashes while ensuring secret values never appear in exception messages.
- URL & string normalization (`_validate_clean_url_parts`, `_format_netloc`, `_clean_optional_str`): Enforces HTTPS everywhere (allowing `http://localhost` and `http://127.0.0.1` only on `PUBLIC_ORIGIN`), rejects embedded URL credentials (`user:pass@`), query strings, and fragments, and normalizes default ports (`:80` / `:443`) so `Host` and `Origin` comparisons are exact.
- `Settings` & `load_settings`: Typed startup configuration loading from process env and optional `.env`. Validates `CHAT_BACKEND` (`f5`, `foundry_agent`, `foundry_openai`), requires only the active backend's variables (no silent fallback), restricts `SSL_VERIFY=false` strictly to `localhost` / `127.0.0.1` origins, masks secrets with `SecretStr`, and strips raw input values (`include_input=False`) from startup `ValidationError` summaries so malformed keys never leak in container logs.
- `ChatMessage` & `fail`: Validates `input` (1–500 non-blank chars), optional `lang`, and optional `conversationId` with `strict=True, extra="ignore"` (preventing type coercion and ignoring unsolicited client fields such as `model` or `endpoint`). `fail(status, message)` returns `Cache-Control: no-store` JSON errors without echoing user input or upstream bodies.
- `ChatSessions`: Bounded in-process `OrderedDict` store mapping cryptographic 192-bit opaque browser IDs (`secrets.token_urlsafe(24)`) to private Foundry `resp_...` IDs or F5 message arrays (trimmed to 40 messages), rotating a fresh single-use opaque ID every turn, expiring entries after 1,800s, and evicting oldest sessions at 1,000 entries. Unknown/expired IDs safely start a fresh conversation.
- `prepare_request`: Builds the exact URL, auth header, and JSON body for the single active backend (`f5` URL-encoded `/openai/{connection}/chat/completions` + Bearer token + history; `foundry_agent` Responses API + Entra Bearer token + `previous_response_id`; `foundry_openai` stateless Chat Completions + `api-key`) without trusting any browser-supplied routing fields.
- Response parsers, `_extract_f5_block_message`, & `format_reply`: Validates Chat Completions (`choices[0].message.content`) vs. Foundry Responses API (`status == "completed"` + assistant `output_text` items) separately. Detects F5 policy blocks (`HTTP 400` + `error.cai_error.outcome == "blocked"`), extracts the admin's custom scanner `message` or `"This message has been blocked by <scanner_name>"` from `error.cai_error.scanner_results` while stripping internal `scanner_id` fields and keeping blocked prompts out of history, passes through `429`, and sanitizes all other upstream errors/malformed payloads into `502`.
- `_check_host_and_origin`, `_read_bounded_body`, `_execute_upstream_turn`, & `_create_default_credential`: Verifies exact `Host` and `Origin` against `PUBLIC_ORIGIN` (mitigating cross-site `text/plain` POSTs and DNS rebinding), enforces streaming byte caps even when `Content-Length` is omitted, and lazily instantiates async `ManagedIdentityCredential` only when `CHAT_BACKEND=foundry_agent`.
- `create_app`, routes, & `main`: Pools a single `httpx.AsyncClient` (`follow_redirects=False`, `trust_env=False`, `verify=settings.ssl_verify`, `1000` max / `100` keep-alive connections) closed cleanly in `lifespan`, disables OpenAPI/Swagger routes, exposes `/healthz`, `/api/client-config`, `POST {CHAT_PATH}`, `/`, `/index.html`, `/chat.html`, and static mounts only for `/assets`, `/css`, `/js`, and runs Uvicorn on `0.0.0.0:PORT` with `access_log=False` so only sanitized telemetry is logged.

`public/js/chat.js` — Browser chat client blocks (what & why)
- Top-level IIFE & private module state (`MAX_INPUT_LENGTH`, `DEFAULT_LANG`, `cachedChatPath`, `conversationId`, `activeController`, `isSending`): Encapsulates session tokens and request state inside a strict closure so `conversationId` is not exposed on `window`, supporting both `/chat.html` and `/chat.html?widget=1`.
- `isValidChatPath` & `discoverChatPath`: Lazily fetches `GET /api/client-config` once on first send, verifies `chatPath` starts with a single `/` (rejecting `//` protocol-relative or external URLs to prevent off-origin redirection), and caches it for subsequent turns.
- `postParentEvent` & `detectWidgetMode`: Emits `reply`, `minimize`, and `browse-product` events via `window.parent.postMessage` scoped strictly to `window.location.origin` when embedded, and adds `.is-widget` to `<body>` when `?widget=1` is present.
- `syncInputSize` & `updateCounter`: Keeps `#chat-input` aligned at `44px` height with `overflowY: hidden` on single-line text, auto-expands up to `132px` before scrolling, and updates the live `N / 500` character counter.
- `showError`, `setSendingState`, `scrollToBottom`, & `appendMessage`: Manages accessible alert/typing states and renders user/assistant bubbles plus optional local `ShopAICatalogGuide` product suggestion cards exclusively via `document.createElement` + `textContent` so untrusted text is never parsed as HTML markup.
- `sendMessage`: Blocks concurrent duplicate sends, posts `{ input, lang, conversationId? }` with `Content-Type: text/plain` and `credentials: "same-origin"`, stores the server-rotated opaque `conversationId` (or clears it for stateless backends), attaches up to 3 matched catalog items (automatically suppressed on policy blocks), and ignores `AbortError` cleanly on user cancellation.
- `resetConversation` & event listeners: Aborts any in-flight `AbortController` on `New`, clears `conversationId` and message rows, restores `#welcome-panel`, and wires form submit, `Enter` vs. `Shift+Enter`, `New`, `Minimize`, and optional `[data-prompt]` triggers.

`public/js/app.js` — Storefront controller blocks (what & why)
- Top-level IIFE, `BAG_STORAGE_KEY`, `state`, & `getProducts`: Centralizes local filter, sort, modal, and bag state over `window.SHOPAI_PRODUCTS` while performing zero network or AI calls to preserve strict separation from `chat.js`.
- `loadBag`, `saveBag`, & `formatMoney`: Hydrates and persists `shopai_sports_bag_v1` in `window.localStorage`, validating each item's `{ id, size, qty > 0 }` schema on load (protecting against corrupted storage) and catching storage quota/privacy exceptions safely.
- `filteredProducts` & `renderCatalog`: Combines category pill selection, case-insensitive multi-field search (`name`, `categoryLabel`, `description`, `keywords`), and price sorting, then renders product cards safely via `createElement` + `textContent`.
- `addToBag`, `updateBagQty`, & `renderBag`: Keys bag line items by `(id, size)` so distinct sizes stay separate, caps per-item quantity at `20`, removes items at `<= 0`, and recalculates `#bag-count` and `#bag-total` from authoritative catalog prices rather than untrusted storage values.
- `openProductModal`, `closeProductModal`, & `setBagOpen`: Populates the quick-view modal with accessible `aria-pressed` size selector buttons and resets transient demo-checkout confirmation banners when closing the bag drawer.
- `initStorefront` & `window.ShopAIStore`: Wires category pills, live search, sort select, modal/drawer backdrop clicks, simulated demo checkout, and `Escape` key dismissal, and exposes `{ openProduct, addToBag }` on `window.ShopAIStore` so `widget.js` can open product details from chat suggestions.
7. Security and failure handling
Provider keys and managed identity tokens remain server-side.
Validate Host and exact same-origin Origin for chat requests.
Do not trust browser-supplied backend, model, agent, endpoint, or upstream response ID.
Bound body, input, response bytes, time, session count, session age, and F5 history.
Disable redirects on credential-bearing upstream requests.
Do not return provider headers or error bodies.
Do not log user text, model text, tokens, full exception strings, or raw provider JSON.
Serve only explicit HTML/static paths so .env and Python source cannot be fetched.
Use safe text APIs for all browser-provided/provider-provided text.
Keep health readiness independent from upstream availability.
Recommended statuses: Host/Origin failure 403; invalid body/input 400; oversized body 413; slow incoming request 408; provider rate limit 429; provider timeout/auth/network/malformed response 502. Return HTTP 200 with F5's configured guardrail block message (without internal `cai_error` scanner fields) only for the explicitly recognized F5 blocked outcome.
8. Dependencies (`requirements.txt`), Container (`Dockerfile`), and Hosting
Both `requirements.txt` and `Dockerfile` MUST include inline `#` comments explaining the purpose and necessity of every dependency, build flag, Linux capability, and container instruction by default.

Commented `requirements.txt` template:
~text
# =============================================================================
# ShopAI Chat — Python Dependencies (Pinned for Reproducible Builds)
# =============================================================================

# --- Web Framework & ASGI Server ---
# Core async web framework serving /healthz, /api/client-config, POST /api/proxy,
# and explicit static HTML/asset routes without exposing the repository root.
fastapi==0.115.6

# Production ASGI HTTP server that binds 0.0.0.0:PORT inside Docker or local venvs.
uvicorn==0.32.1

# --- Outbound HTTP Client ---
# Shared async HTTP client with connection pooling, strict connect/read timeouts,
# disabled redirects, configurable local-dev TLS verification, and streamed 2 MiB
# response caps (also provides httpx.MockTransport for offline unit tests).
httpx==0.28.1

# --- Configuration & Schema Validation ---
# Enforces strict request schemas (ChatMessage), URL/path validators, and SecretStr
# masking so API tokens and keys never leak in tracebacks or startup errors.
pydantic==2.10.6

# Loads typed Settings from environment variables and optional local .env files
# while ensuring process environment variables always take precedence.
pydantic-settings==2.7.1

# --- Azure Managed Identity Authentication (CHAT_BACKEND=foundry_agent) ---
# Provides async ManagedIdentityCredential to acquire Entra ID bearer tokens for
# Azure AI Foundry agents in production without storing static API keys.
azure-identity==1.19.0

# Async HTTP transport required under the hood by azure.identity.aio credentials
# so Managed Identity token acquisition stays non-blocking on the event loop.
aiohttp==3.11.11

# --- Offline Verification & Test Suite ---
# Test runner for backend security boundaries, provider adapters, and JS contracts.
pytest==8.3.4

# Enables async pytest coroutines for testing streaming body limits, slow-client
# timeouts, and ASGI transport behavior without network access.
pytest-asyncio==0.24.0
~

Commented `Dockerfile` template:
~dockerfile
# =============================================================================
# ShopAI Chat — Production Container Build
# Serves both the static storefront/chat UI (public/) and FastAPI proxy (app/)
# as an unprivileged user bound directly to TCP port 80.
# =============================================================================

# Minimal official Debian-based Python 3.12 image to reduce image size and OS attack surface.
FROM python:3.12-slim

# - PYTHONDONTWRITEBYTECODE=1: Skip writing .pyc files inside ephemeral container layers.
# - PYTHONUNBUFFERED=1: Flush stdout/stderr immediately so container logs stream in real time.
# - PORT=80: Default HTTP listener port expected by local Docker (-p 80:80) and Azure App Service.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=80

# Dedicated working directory isolated from system paths.
WORKDIR /srv/shopai

# Allow non-root execution on privileged port 80 (<1024):
# 1. Install libcap2-bin temporarily so we can set Linux file capabilities.
# 2. Grant cap_net_bind_service=+ep on the real python3 binary (resolving symlinks)
#    so Python can bind port 80 without running the container as root.
# 3. Purge libcap2-bin and delete apt package lists in the same layer to keep the image lean.
# 4. Create an unprivileged system account (appuser, UID/GID 10001) with no login shell or home dir.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libcap2-bin \
    && setcap 'cap_net_bind_service=+ep' "$(readlink -f /usr/local/bin/python3)" \
    && apt-get purge -y --auto-remove libcap2-bin \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser

# Copy and install Python dependencies BEFORE application source so Docker reuses
# this cached layer whenever only app/ or public/ files change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the FastAPI backend package and static browser assets.
# (.dockerignore prevents .env, secrets, tests, and .git from entering image layers.)
COPY app ./app
COPY public ./public

# Drop root privileges; all runtime processes execute as UID 10001.
USER appuser

# Document the container's listening port for operators and hosting platforms.
EXPOSE 80

# Lightweight local liveness probe using Python's stdlib urllib (avoids installing curl).
# Checks local web server readiness on /healthz without calling upstream AI providers.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; p = int(os.environ.get('PORT', '80')); urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=3)"

# Exec-form startup command so Python receives SIGTERM/SIGINT directly for graceful shutdown.
CMD ["python", "-m", "app.main"]
~

Use `.dockerignore` so `.env` and `.env.*` are never copied into image layers. At runtime, inject the selected backend's variables (e.g., `docker run --rm -p 80:80 --env-file .env --name shopai-chat shopai-chat`).
For Azure App Service custom containers: configure image and tag, environment settings, port 80, and managed identity. In agent mode, enable identity on that App Service and grant it project access. For a VM/local Docker, configure runtime variables separately; an App Service managed identity is not inherited by the VM.
A healthy /healthz proves the web process answers locally. It does not prove a provider endpoint, key, role assignment, or model is valid. Test a real chat turn and follow-up.
9. Rebuild and verification steps
Build chat.html and its responsive styles; support both full-page and ?widget=1 iframe layouts.
Implement chat.js and app.js with block-by-block JSDoc/inline comments explaining what each section/function does and why; in chat.js use the config endpoint, same-origin POST contract, safe rendering, typing state, New/cancel behavior, and opaque conversation ID.
Implement validated server configuration, backend selection, and all routes/helpers in app/main.py with docstrings and section comments explaining what each block does and why, plus inline-commented requirements.txt and Dockerfile (Section 8).
Implement each backend request and response parser exactly as above; do not unify away the differences.
Implement bounded F5 history and Foundry response-ID mapping.
Add Host/Origin checks, request/response limits, timeouts, safe error handling, and health route.
Add tests using mocked HTTP responses and fake managed identity. Test URLs, auth headers, body format, response extraction, policy block, follow-up, invalid/unknown IDs, input/size errors, Host/Origin rejection, 429/5xx, timeout, malformed JSON, and no secret leakage.
Run Python tests with python -m pytest -q. Current suites: tests/test_app.py, tests/test_f5.py, tests/test_agent.py, tests/test_foundry.py. Browser checks are under tests/browser/.
Test each backend separately with its own server-side settings. Confirm there is no silent fallback.
Build/start the container with runtime variables; check /healthz, /api/client-config, /chat.html, a first turn, and a follow-up.
In agent mode, verify the deployed host identity and role assignment at the correct Foundry project.
Check image contents and logs: no .env, secrets, raw provider diagnostics, or chat bodies.
10. Current source reference
Current implementation: app/__init__.py, app/main.py. Browser files: public/index.html, public/chat.html, public/css/styles.css, public/css/chat.css, public/assets/logo.svg, public/js/chat.js, public/js/widget.js, public/js/app.js, public/js/products.js, public/js/catalog-guide.js. Configuration template: .env.example. Dependencies: requirements.txt. Container: Dockerfile, .dockerignore, .gitignore. Documentation & visual architecture: README.md, Troubleshooting.md, Architecture.md, architecture-topology.html, architecture-topology.png, architecture-workflow.html, architecture-workflow.png. Tests: pytest.ini, tests/conftest.py, tests/test_app.py, tests/test_f5.py, tests/test_agent.py, tests/test_foundry.py, tests/browser/test_frontend_contract.py.
If code changes later, source is authoritative. This guide documents the current behavior and does not include any real API key.

11. Troubleshooting & live verification commands (`Troubleshooting.md`)
Include all of the operational runbooks and `curl` verification commands below in `Troubleshooting.md` (without real secrets—use shell placeholders or `.env` variables) so any user or operator on a new machine can reload `.env`, switch backends, and test both the local proxy and upstream providers immediately.

Reloading `.env` changes in Docker
Docker reads `--env-file .env` only when creating a new container (`docker restart` reuses old environment variables, and a detached `-d` container keeps holding port `80` until removed). Whenever `.env` is edited, save `.env` first and recreate the container:
~bash
# Foreground mode (logs stream in terminal; Ctrl+C stops and removes container)
docker rm -f shopai-chat 2>/dev/null; docker run --rm -p 80:80 --env-file .env --name shopai-chat shopai-chat

# Detached background mode (-d) + live logs
docker rm -f shopai-chat 2>/dev/null; docker run -d --rm -p 80:80 --env-file .env --name shopai-chat shopai-chat
docker logs -f --tail 30 shopai-chat
~
(On macOS, if `docker` is not on `PATH`, run `export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"` first.)

Confirm which `CHAT_BACKEND`, F5 region, CAI project name, and `SSL_VERIFY` setting the running container loaded:
~bash
docker exec shopai-chat python -c "from app.main import load_settings; s = load_settings(); print('Backend:', s.chat_backend, '| F5 Base:', s.f5_guardrails_base_url, '| CAI Project:', s.f5_guardrails_connection_name, '| SSL_VERIFY:', s.ssl_verify)"
~

Testing the local ShopAI server (`http://localhost`)
Health and client config checks:
~bash
curl -i http://localhost/healthz
# -> 200 OK {"status":"ok"}

curl -i http://localhost/api/client-config
# -> 200 OK {"chatPath":"/api/proxy"}
~

End-to-end proxy chat turn (`POST /api/proxy`) — include `Origin` and `Host` matching `PUBLIC_ORIGIN=http://localhost`:
~bash
curl -sS -i \
  -H "Origin: http://localhost" \
  -H "Host: localhost" \
  -H "Content-Type: text/plain" \
  -d '{"input":"Recommend an outdoor soccer ball","lang":"en"}' \
  http://localhost/api/proxy
~
- `f5` or `foundry_agent` returns `{"response":"...","conversationId":"<opaque-id>"}`.
- `foundry_openai` (stateless) returns `{"response":"..."}` (no `conversationId`).

Follow-up turn (`f5` or `foundry_agent`):
~bash
curl -sS -i \
  -H "Origin: http://localhost" \
  -H "Host: localhost" \
  -H "Content-Type: text/plain" \
  -d '{"input":"What size is best for adults?","lang":"en","conversationId":"PASTE_CONVERSATION_ID_HERE"}' \
  http://localhost/api/proxy
~

Direct upstream provider `curl` tests (bypassing the app)
Load variables from `.env` in your current shell (`set -a; source .env; set +a`). Add `-k` only on a laptop behind VPN/TLS inspection if host `curl` reports a self-signed certificate in chain.

Option 1 — F5 AI Guardrails connection (`CHAT_BACKEND=f5` — Default), allowed prompt + policy-blocked prompt:
~bash
# 1. Allowed sports prompt (expect HTTP 200 with choices[0].message.content; check us2 vs us1 & CAI project name on 401/404)
curl -sS -i \
  -X POST "${F5_GUARDRAILS_BASE_URL%/}/openai/${F5_GUARDRAILS_CONNECTION_NAME// /%20}/chat/completions" \
  -H "Authorization: Bearer ${F5_GUARDRAILS_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"${F5_GUARDRAILS_MODEL}\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"Which basketball works best on outdoor asphalt?\"}
    ]
  }"

# 2. Policy-blocked prompt check (expect HTTP 400 from F5 with error.cai_error.outcome == "blocked" and scanner_results; ShopAI /api/proxy converts this to HTTP 200 with the scanner's custom message or "This message has been blocked by <scanner_name>")
curl -sS -i \
  -X POST "${F5_GUARDRAILS_BASE_URL%/}/openai/${F5_GUARDRAILS_CONNECTION_NAME// /%20}/chat/completions" \
  -H "Authorization: Bearer ${F5_GUARDRAILS_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"${F5_GUARDRAILS_MODEL}\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"REPLACE_WITH_YOUR_F5_BLOCKED_TOPIC_TEST\"}
    ]
  }"
~

Option 2 — Saved Azure AI Foundry agent (`CHAT_BACKEND=foundry_agent`, tested via `az login` with Azure AI User role):
~bash
ENTRA_TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

curl -sS -i \
  -X POST "${FOUNDRY_PROJECT_ENDPOINT%/}/agents/${FOUNDRY_AGENT_NAME}/endpoint/protocols/openai/responses?api-version=v1" \
  -H "Authorization: Bearer ${ENTRA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {"role": "user", "content": "What home gym gear do you recommend?"}
    ]
  }'
~

Option 3 — Direct Azure OpenAI / Foundry model (`CHAT_BACKEND=foundry_openai`):
~bash
curl -sS -i \
  -X POST "${AZURE_OPENAI_ENDPOINT%/}/chat/completions" \
  -H "api-key: ${FOUNDRY_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"${FOUNDRY_AGENT_MODEL}\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"Hello! Recommend one road running shoe.\"}
    ]
  }"
~

Common errors & quick fixes
- Container exits on startup with `Invalid application configuration (ssl_verify)`: `PUBLIC_ORIGIN` was changed to a public `https://...` domain while `SSL_VERIFY=false` remained set from `.env.example`. Set `SSL_VERIFY=true` whenever `PUBLIC_ORIGIN` is not `localhost` / `127.0.0.1`.
- Browser shows `ERR_EMPTY_RESPONSE` or `Connection refused`: `PORT` in `.env` (e.g. `8000`) doesn't match Docker's published container port (`-p 80:80`). Keep `PORT=80` and `PUBLIC_ORIGIN=http://localhost` in `.env` and recreate the container with `-p 80:80`.
- Chat banner says `Forbidden` (`HTTP 403`): Browser URL or `curl` `Origin`/`Host` doesn't match `PUBLIC_ORIGIN` (e.g. opening `http://127.0.0.1` when `PUBLIC_ORIGIN=http://localhost`). Open exact `http://localhost` or match `PUBLIC_ORIGIN`.
- Chat banner says `Chat service unavailable` (`HTTP 502`) on `CHAT_BACKEND=f5`: Wrong F5 region (`us2` vs `us1`), wrong `F5_GUARDRAILS_CONNECTION_NAME` (must match exact CAI Project name), invalid token/model, or `SSL_VERIFY=true` behind laptop VPN/TLS inspection. Toggle `F5_GUARDRAILS_BASE_URL` (`https://us2.calypsoai.app` vs `https://us1.calypsoai.app`), verify CAI Project name & model via the direct F5 `curl` test, and keep `SSL_VERIFY=false` on local `localhost` Docker.
- Container still uses previous backend or old `.env` values: Old background `shopai-chat` container is still running or `.env` wasn't saved. Save `.env` and run `docker rm -f shopai-chat 2>/dev/null; docker run --rm -p 80:80 --env-file .env --name shopai-chat shopai-chat`.

12. Ready-to-use prompt for the next agent
Copy the prompt below into a coding agent in a fresh VM/directory (or existing project) alongside this `Portrait.md` file. No reference screenshot is needed.
~text
Build the complete, production-structured "<SHOP_NAME> — ShopAI" storefront and multi-backend AI chat web application from scratch (or integrate cleanly if files already exist) using the accompanying Portrait.md as the authoritative architecture, security, and behavior specification. Build the entire working frontend, FastAPI/Python backend, Docker container configuration, documentation, visual diagrams, and offline test suite—do not stop at a mockup or plan.

0. Storefront Name Prompt (Ask First Before Writing Files):
- Unless the user already specified a shop name in their message, start by asking one concise question: "What name would you like to use for your shop/storefront (for example, `Apex Sports`, `Metro Athletics`, or `ShopAI Sports`)?" and wait for their reply.
- Once confirmed, use that exact `<SHOP_NAME>` consistently everywhere: `public/index.html` (`<title>`, top navbar brand title, and footer), `README.md`, `Architecture.md`, and the titles/subtitles inside `architecture-topology.html` (`architecture-topology.png`) and `architecture-workflow.html` (`architecture-workflow.png`).

1. Storefront & Chat UI Specification (`public/`):
- Serve all browser assets strictly from `public/` (`public/index.html`, `public/chat.html`, `public/css/styles.css`, `public/css/chat.css`, `public/assets/logo.svg`, and `public/js/*.js`). Never serve the repository root.
- Design `public/index.html` ("<SHOP_NAME> — ShopAI Athletic Gear") with a clean, minimal athletic layout (light slate background `#f8fafc`, white surface cards `#ffffff`, emerald primary actions `#059669`) and NO large hero/promotional banner:
  - Sticky top header: SVG brand mark + `<SHOP_NAME>` + `ShopAI` pill badge + live color-coded active-backend status pill (`#backend-status-pill` / `#backend-status-text` showing `AI Backend: F5 AI Guardrails (CAI)`, `Azure AI Foundry Agent`, or `Azure OpenAI (Direct)` from `GET /api/client-config`), live search input (`#catalog-search`), `Full Chat` link (`/chat.html`), and `Bag` button (`#open-bag-btn`) with live item count badge (`#bag-count`).
  - Directly below the header, render the catalog toolbar & grid: category filter pills (`All Gear`, `Balls & Team`, `Running`, `Training & Gym`, `Outdoor & Racquet`), sort dropdown (`Featured`, `Price: Low to High`, `Price: High to Low`), and responsive product cards rendered from `public/js/products.js` (8 sports items across soccer/basketball balls, road/trail running shoes, kettlebell/resistance bands, tennis racquet, and insulated bottle, with emoji/gradient visual headers, badges, sizes, prices, `Details` modal button, and `Add to Bag` button).
  - Product quick-view modal (with selectable size pills) and slide-over shopping bag drawer persisted in `localStorage` (`shopai_sports_bag_v1`) with `−`/`+` quantity controls, total calculation, and a `Complete Demo Checkout` confirmation notice. `public/js/app.js` owns only storefront/cart behavior and must never call chat or provider APIs; document every function and code block in `public/js/app.js` with clear JSDoc/inline comments explaining what it does and why (avoiding forbidden test substrings like `innerHTML`, `fetch(`, `/api/proxy`, or `/api/client-config` even inside comments).
- Build `public/chat.html` & `public/css/chat.css` to support both standalone (`/chat.html`) and iframe widget (`/chat.html?widget=1`) modes:
  - Compact single-line header ("ShopAI Assistant" / "Sports & gear advisor" + `#chat-backend-pill` active backend badge) with non-wrapping `← Back to Shop` (standalone only), `New`, and `Minimize` (widget only) buttons.
  - Accessible message log (`role="log"`, `aria-live="polite"`) with a clean, minimal welcome card containing ONLY `"How can I help gear up your next session?"` (do NOT include an extra intro paragraph or starter prompt chip buttons), plus typing indicator and error alert banner.
  - Well-proportioned composer (`padding: 0.9rem 1.1rem 0.75rem`): `<textarea id="chat-input" rows="1" maxlength="500" placeholder="Type your message…">` sized to an exact `44px` single-line height (`padding: 10px 14px`, `line-height: 22px`, `overflow-y: hidden` until exceeding `max-height: 132px` so no scrollbar appears when empty or short), auto-resized on input/reset, paired side-by-side with a matching `44px`-tall `Send` button, and a clean metadata row (`Enter to send • Shift+Enter for new line` and `0 / 500` counter).
- Implement `public/js/chat.js` (with clear JSDoc and inline comments on every block/function explaining what it does and why, without mentioning `innerHTML` or provider domains/secret env names in comments):
  - Lazily fetch and cache `chatPath` from `GET /api/client-config`, validating it starts with a single `/` and is not protocol-relative (`//`).
  - Send `POST` to `chatPath` with `Content-Type: text/plain` and JSON string `{ "input", "lang": "en", "conversationId"?: ... }` (only forwarding opaque IDs issued by this server).
  - Auto-resize `#chat-input` between `44px` and `132px`, prevent duplicate concurrent sends, cancel pending requests via `AbortController` on `New`, render all user/assistant text strictly via `textContent` (never raw HTML markup), surface optional local product suggestion cards via `public/js/catalog-guide.js` (requiring at least one product keyword match in the assistant reply itself and suppressing suggestions on policy-block replies so custom admin block messages never show product cards), and notify `window.parent` via same-origin `postMessage` for reply/minimize/product-browse events.
- Implement `public/js/widget.js`:
  - Floating bottom-right `Ask ShopAI` / `Minimize Chat` launcher on the storefront with a `400px`-wide widget panel (`height: min(580px, calc(100vh - 6rem))`) that mounts `<iframe src="/chat.html?widget=1">` once and keeps it mounted in the DOM via an `.is-minimized` class when minimized so active conversations are never lost. Include unread reply indicator, `Escape` key minimize, `window.visualViewport` mobile height adjustment, and same-origin `browse-product` bridging to `window.ShopAIStore.openProduct(productId)`.

2. FastAPI Multi-Backend Server (`app/main.py`):
- Write Python code compatible with Python 3.9 through 3.12+ (`from __future__ import annotations`, `typing` generics, `asyncio.wait_for`, and Pydantic v2 `SettingsConfigDict(..., populate_by_name=True)`), and document every section, class, validator, helper, and route handler with module/function docstrings and block comments explaining what each block does and why (as specified in Section 6 of Portrait.md).
- Support all three explicit `CHAT_BACKEND` modes (`f5`, `foundry_agent`, `foundry_openai`) defaulting `CHAT_BACKEND` to `"f5"` with no silent fallback between backends, requiring only the selected backend's variables at startup:
  - `f5`: `POST {F5_GUARDRAILS_BASE_URL}/openai/{URL-encoded connection}/chat/completions` with `Authorization: Bearer {F5_GUARDRAILS_API_TOKEN}`, bounded 40-message (20-turn) server-side history, newly rotated opaque `conversationId` on every turn, and HTTP 200 preserving F5's exact per-guardrail response strictly when F5 returns HTTP 400 with `error.cai_error.outcome == "blocked"`. Important: top-level `error.message` on F5's `/openai/.../chat/completions` endpoint is generic `"CAI guardrails blocked the prompt"`, so extract the guardrail message in priority order from (1) non-empty `cai_error.response` / `custom_response`, (2) failed entries (`outcome` in `("failed", "blocked")`) inside `cai_error.scanner_results`—returning non-empty `scanner_results[i].message` when an admin configured custom text in F5, or `"This message has been blocked by " + scanner_results[i].scanner_name` when `message` is `null` (F5's default guardrail message)—and (3) non-generic `error.message` or fallback `"This subject is blocked by your company's chat policy. I can help with sports products, gear, sizing, and training instead."` only if empty. Never expose internal `scanner_id` values and never append blocked prompts to session history (all other errors map to 429/502).
  - `foundry_agent`: `POST {FOUNDRY_PROJECT_ENDPOINT}/agents/{URL-encoded agent}/endpoint/protocols/openai/responses?api-version=v1` using `azure.identity.aio.ManagedIdentityCredential` (optional `AZURE_CLIENT_ID`) for scope `https://ai.azure.com/.default`, requiring `status == "completed"`, joining assistant `output_text` parts, and mapping private Foundry `response.id` values to rotated opaque browser IDs (`previous_response_id` on follow-up).
  - `foundry_openai`: Stateless `POST {AZURE_OPENAI_ENDPOINT}chat/completions` (normalizing `/openai/v1` to `/openai/v1/`) with `api-key: {FOUNDRY_API_KEY}`, `model: {FOUNDRY_AGENT_MODEL}`, single current user message only, and returning `{"response": "..."}` with no `conversationId`.
- Enforce all security and operational rules from Portrait.md:
  - `PUBLIC_ORIGIN` requires `https://` for public hosts and allows `http://localhost` / `http://127.0.0.1` (with optional port) for local testing.
  - Include `SSL_VERIFY` (default `true`) passed to `httpx.AsyncClient(..., verify=settings.ssl_verify, follow_redirects=False, trust_env=False, limits=httpx.Limits(max_connections=1000, max_keepalive_connections=100))`, permitting `SSL_VERIFY=false` ONLY when `PUBLIC_ORIGIN` hostname is `localhost` or `127.0.0.1` (for local Docker behind laptop TLS inspection proxies) and rejecting `SSL_VERIFY=false` on public origins.
  - Check exact `Host` and `Origin` (`403`) before body reads or credential calls; enforce 15s body-read timeout (`408`), 64 KiB request cap (`413`), strict `ChatMessage` validation (`400`, 1–500 chars, non-blank, `extra="ignore"`), 2 MiB upstream response cap (`502`), `429` passthrough, safe `502` error sanitization, `SecretStr` masking + sanitized `StartupConfigurationError` (including static missing-variable rule messages without raw secret values), safe metadata-only logging (plus a `ShopAI startup: active_backend=...` line on container boot), `GET /healthz`, `GET /api/client-config` (returning `chatPath`, `backendMode`, and `backendLabel` without exposing URLs, project/model names, or secrets), disabled OpenAPI docs, and static mounts only for `/assets`, `/css`, `/js`.
  - Instantiate the shared `httpx.AsyncClient` in `create_app` and close it (plus async credential) in `lifespan` so both `TestClient` and `httpx.ASGITransport` work cleanly.

3. Packaging, Container, Tests & Documentation:
- Create `requirements.txt` with pinned dependencies (`fastapi`, `uvicorn`, `httpx`, `pydantic`, `pydantic-settings`, `azure-identity`, `aiohttp`, `pytest`, `pytest-asyncio`) and inline `#` comments above every dependency group/package explaining what each component does and why it is needed (matching Section 8 of Portrait.md), plus `pytest.ini` (`asyncio_default_fixture_loop_scope = function`), `.gitignore`, and `.dockerignore` (excluding `.env` and `.env.*`).
- Set `.env.example` defaults to `PUBLIC_ORIGIN=http://localhost`, `PORT=80`, followed by a blank line and then uncommented `SSL_VERIFY=false` (preceded by a clear comment explaining that `SSL_VERIFY=false` is for local `localhost`/`127.0.0.1` Docker behind VPN/TLS inspection and MUST be changed to `SSL_VERIFY=true` on any public HTTPS domain / Cloud VM / Azure Web App both for production TLS security and because startup validation rejects `SSL_VERIFY=false` on non-localhost origins), and `# Explicitly select one backend: f5 | foundry_agent | foundry_openai` followed by `CHAT_BACKEND=f5` (with F5 Option 1 active keeping its four uncommented lines grouped cleanly together—`F5_GUARDRAILS_API_TOKEN=your-API-token-generated-on-CAI`, `F5_GUARDRAILS_BASE_URL=https://us2.calypsoai.app`, `F5_GUARDRAILS_CONNECTION_NAME=your-cai-project-name`, `F5_GUARDRAILS_MODEL=your-AI-model-on-CAI`—followed at the end of the Option 1 block by comments explaining `F5_GUARDRAILS_CONNECTION_NAME`, `F5_GUARDRAILS_MODEL` `(e.g. gpt-4.1)`, and `# F5_GUARDRAILS_BASE_URL=https://us1.calypsoai.app`, while keeping EVERY line in Option 2 and Option 3 strictly `#` commented out as shown in Section 5 so users are never confused).
- Create `Dockerfile` on `python:3.12-slim` with `PORT=80`, granting `setcap 'cap_net_bind_service=+ep'` to the Python binary so non-root `USER appuser` (UID 10001) binds `0.0.0.0:80` cleanly, `EXPOSE 80`, local `/healthz` `HEALTHCHECK`, and `CMD ["python", "-m", "app.main"]`, including inline `#` comments on every instruction explaining why each layer, flag, capability, user, and healthcheck exists (matching Section 8 of Portrait.md).
- Implement offline test suites (`tests/test_app.py`, `tests/test_f5.py`, `tests/test_agent.py`, `tests/test_foundry.py`, and `tests/browser/test_frontend_contract.py`) using `httpx.MockTransport` and a fake async `ManagedIdentityCredential` covering all three backends, URL encoding, session rotation/TTL/capacity/40-message bounds, F5 policy block vs non-block errors, Host/Origin `403`, `400`/`408`/`413`/`429`/`502`, `SSL_VERIFY` guardrails, secret/log sanitization, frontend DOM/JS contracts, and verification that inline documentation comments are present in `requirements.txt`, `Dockerfile`, `app/main.py`, `public/js/chat.js`, and `public/js/app.js`.
- Create `README.md` featuring `./architecture-workflow.png` embedded near the top, a clear **Quick Start — Run Locally with Docker** (`cp .env.example .env`, edit `.env`, `docker build -t shopai-chat .`, `docker run --rm -p 80:80 --env-file .env --name shopai-chat shopai-chat`, open `http://localhost`, plus foreground & `-d` `.env` reload commands—do NOT use verbose `-e` flag lists), a complete **Environment Configuration & Variable Reference** section with tables documenting the default/example, requirement, and description of EVERY environment variable across Shared Settings (`PUBLIC_ORIGIN`, `CHAT_PATH`, `CHAT_TIMEOUT_SECONDS`, `PORT`, `SSL_VERIFY`, `CHAT_BACKEND`), Option 1 (`F5_GUARDRAILS_API_TOKEN`, `F5_GUARDRAILS_BASE_URL`, `F5_GUARDRAILS_CONNECTION_NAME`, `F5_GUARDRAILS_MODEL`), Option 2 (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_AGENT_NAME`, `AZURE_CLIENT_ID`), and Option 3 (`AZURE_OPENAI_ENDPOINT`, `FOUNDRY_API_KEY`, `FOUNDRY_AGENT_MODEL`), all three backend `.env` examples, optional local `.venv`/`pytest` steps, `SSL_VERIFY` + Azure App Service + Managed Identity RBAC notes, AND the complete **Troubleshooting & Verification Guide** section directly inline on `README.md` (so all troubleshooting commands, `curl` tests, and quick-fix tables display directly on the GitHub repository home page) as well as in standalone `Troubleshooting.md` reproducing Section 11 of Portrait.md.
- Create the visual architecture documentation and render BOTH high-resolution `.png` diagrams at the repository root (outside `public/` so static security tests stay untouched):
  1. `architecture-topology.html` + `architecture-topology.png`: Zero-dependency offline interactive 4-scenario topology explorer (Light/Dark toggle, clickable Browser, Docker+FastAPI, F5 AI Guardrails, and Azure AI Foundry cards, animated request/response SVG hops, and step-by-step wire details for `f5` allowed, `f5` blocked, `foundry_openai`, and `foundry_agent`), rendered at 2x Retina (`1200x720` viewport -> `2400x1440` PNG).
  2. `architecture-workflow.html` + `architecture-workflow.png`: Enterprise `"END-TO-END CONNECTION WORKFLOW"` vector SVG diagram on a light dotted canvas showing four nested environment zones (`User Environment` -> `Container Host` with nested blue `Docker Container (shopai-chat)` containing `Uvicorn Web` & `FastAPI App` with Docker whale / FastAPI / Python icons -> `F5 AI Guardrails (CalypsoAI SaaS)` red shield zone with `CAI Policy Engine` & HTTP 400 short-circuit callout -> `Azure Cloud Services` blue zone with `Entra ID & Keys` diamond and `Azure AI Foundry`), numbered directional workflow arrows `1` through `8` (solid green Browser<->Container, solid orange outbound HTTPS AI/CAI calls, dashed blue upstream return/block path, and dashed teal direct-mode bypass), and a bottom legend bar, rendered at 2x Retina (`1600x920` viewport -> `3200x1840` PNG).
  3. Render both `.png` files automatically (using headless Chrome/Chromium/Edge `--headless --user-data-dir=/tmp/chrome-headless-profile --disable-gpu --hide-scrollbars --force-device-scale-factor=2 --screenshot=...`, or Playwright/Python rendering if on a headless Linux VM without a system browser), and embed them alongside Mermaid topology/sequence diagrams in `Architecture.md`.

Execution workflow:
1. First, ask the admin what shop name (`<SHOP_NAME>`) they want for the storefront (unless already provided in their prompt) and wait for their answer.
2. Briefly outline your implementation plan, create a local `.venv`, install `requirements.txt`, implement all files using `<SHOP_NAME>`, render both `.png` architecture diagrams, and run `.venv/bin/python -m pytest -v`, fixing any failures until 100% pass.
3. Do not commit, push, publish images, or modify cloud resources unless explicitly asked. Summarize everything implemented, test results, and runtime configuration at the end.
~