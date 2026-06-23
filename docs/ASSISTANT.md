# Unified Chat & AI Assistant System

The `assistant` app is the single source of truth for all customer conversations —
AI-driven shopping help, voice ordering, and human admin support all live in the
same thread. The old `support.ChatSession` order-scoped chat system has been
removed entirely; there is no separate support chat anymore.

## Architecture

```
Frontend widget (text or voice input)
      │
      │  POST /api/assistant/chat/
      │  { message, conversation_id, language }
      ▼
AssistantChatView          ← trust boundary: injects authenticated user
      │
      ├── _get_or_create_conversation()
      │     loads existing thread (G1 isolation) or creates a new one
      │
      ├── _load_history()
      │     last MAX_HISTORY_TURNS turns — roles: user | assistant | admin
      │     (admin messages are included so the LLM knows a human has joined)
      │
      ▼
Agent.run(message, history, language)
      │
      ├── _complete(messages)   ← LLM call (OpenRouter or any LangChain provider)
      │         │
      │    JSON envelope { thought, tool?, args?, action?, final_reply?, title? }
      │         │
      ├── tool in READ_TOOLS?
      │     yes → toolkit.run_read_tool(tool, user, args)
      │            └─ result wrapped in <<DATA>> spotlighting
      │            └─ appended to messages, loop continues (max 4 iterations)
      │
      ├── action in ACTION_BUILDERS?
      │     yes → build_action(action, user, args) → proposed_action returned to frontend
      │
      └── final_reply reached → return { reply, proposed_action, sources, escalate, title }
                                         │
                              title: only on first turn, auto-saves to conversation.title
                              escalate: sets conversation.needs_human = True (flags thread for admin)
```

The loop is bounded to **MAX_ITERATIONS = 4** tool calls per turn.

---

## Data Model

### `AssistantConversation`

One thread per customer session. A customer can have many threads and switch between them.

| Field | Type | Notes |
|-------|------|-------|
| `conversation_id` | UUID | Public identifier sent to clients |
| `user` | FK (nullable) | Null for anonymous sessions |
| `anon_session` | CharField | Opaque client-generated id for guests |
| `title` | CharField(80) | Auto-set from LLM on first turn; editable |
| `status` | CharField | `active` / `resolved` / `archived` |
| `needs_human` | BooleanField | True when AI escalates or admin flags it |
| `assigned_to` | FK → User (nullable) | Admin who owns this thread |
| `created_at` | DateTimeField | |
| `updated_at` | DateTimeField | |

### `AssistantMessage`

One row per turn. Roles: `user` / `assistant` / `tool` / `system` / `admin`.

| Field | Type | Notes |
|-------|------|-------|
| `conversation` | FK | Parent thread |
| `role` | CharField | `user` \| `assistant` \| `tool` \| `system` \| `admin` |
| `content` | TextField | Message body |
| `sender_name` | CharField(100) | Display name — set for `admin` role (e.g. "Kaushal"), blank otherwise |
| `meta` | JSONField | Audit trail: sources, proposed_action, escalate flag, llm_used |
| `created_at` | DateTimeField | |

---

## API Endpoints

### Customer-facing

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `POST` | `/api/assistant/chat/` | Optional | Send a message; AI responds |
| `GET` | `/api/assistant/conversations/` | Required | List the authenticated user's threads |
| `POST` | `/api/assistant/conversations/` | Required | Create a new empty thread |
| `GET` | `/api/assistant/conversations/{id}/messages/` | Required | Full message history for one thread |

### Admin-facing (`IsAdminUser`)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/assistant/conversations/admin/` | All threads; filter by `needs_human`, `status`, `user`, date |
| `POST` | `/api/assistant/conversations/{id}/admin-reply/` | Insert an admin message; clears `needs_human` |
| `PATCH` | `/api/assistant/conversations/{id}/` | Update `status`, `assigned_to` |

#### `POST /api/assistant/chat/` Request / Response

```json
// Request
{
  "message": "Do you have haldi?",
  "conversation_id": "uuid-or-omit-for-new",
  "language": "hi"
}

// Response
{
  "reply": "हाँ! हमारे पास Nidhi Haldi Powder है…",
  "conversation_id": "abc123...",
  "proposed_action": null,
  "sources": [{ "tool": "search_products", "args": { "query": "haldi" } }]
}
```

#### `GET /api/assistant/conversations/` Response

```json
[
  {
    "conversation_id": "abc123...",
    "title": "Haldi powder order query",
    "status": "active",
    "needs_human": false,
    "last_message": "Anything else you'd like?",
    "updated_at": "2026-06-21T10:32:00Z"
  }
]
```

#### `POST /api/assistant/conversations/{id}/admin-reply/` Request

```json
{ "message": "Let me check that order for you right away." }
```

---

## Security Guardrails

| Guard | What it does |
|-------|-------------|
| **G1 — user isolation** | No tool accepts a `user_id`/email argument. Every user-scoped read is hard-filtered by the authenticated user from the view. Admin endpoints verified via `IsAdminUser`. |
| **G2 — public fields only** | Tool serializers expose a whitelisted subset of fields. No cost prices, margins, supplier data, or internal flags. |
| **G3 — closed registry + spotlighting** | Only names in `ALL_TOOL_NAMES` can be called. Retrieved data wrapped in `<<DATA source=…>>…<</DATA>>` markers. |
| **G4 — bounded loop + degrade** | Max 4 iterations; max 600 output tokens. LLM unavailable → `FALLBACK_REPLY`. |
| **G5 — quantity clamp** | Add-to-cart proposals clamped to 10 units max. |
| **G6 — navigation allowlist** | `navigate` only returns routes from a hardcoded static set or verified slugs. No open redirect. |

---

## Tool Registry

### READ_TOOLS — executed server-side, result fed back to LLM

| Tool | Auth | Description |
|------|------|-------------|
| `search_products` | No | Fuzzy text search products and combos |
| `browse_products` | No | Structured catalogue browse/filter (category, price range, spice_form, on_offer, in_stock, sort, limit) over products + combos |
| `get_product_details` | No | Full detail for one product/combo by slug |
| `get_product_reviews` | No | Rating summary + recent public reviews for one product/combo (public review fields only) |
| `list_categories` | No | All active categories |
| `get_policy` | No | Shipping or return policy content |
| `get_order_status` | Yes | Status of a single order (authenticated user's own) |
| `get_order_details` | Yes | Line items of one of the user's orders (for "what was in X" / reorder) |
| `list_my_orders` | Yes | The authenticated user's recent orders (number, status, date, total) |
| `get_cart` | Yes | Authenticated user's current cart |

All user-scoped tools (`get_order_*`, `list_my_orders`, `get_cart`) are hard-filtered
by the authenticated user from the view (G1). No tool accepts a user identifier, so
the model has no way to request another customer's orders, cart, or reviews. Catalogue
and review tools expose only public, whitelisted fields (G2) — no cost prices, margins,
stock counts, supplier data, or reviewer emails.

### ACTION_BUILDERS — return `proposed_action`; UI confirms before acting

| Action | Auth | Description |
|--------|------|-------------|
| `add_to_cart` | Yes | Propose adding a product/variant (one item per turn) |
| `checkout` | Yes | Propose navigating to checkout |
| `navigate` | No | Return a verified in-app route |
| `escalate_to_human` | No | Set `needs_human=True`; admin sees thread highlighted |

---

## Voice Ordering

Voice input is handled entirely in the browser (Web Speech API → transcript text).
The transcript is sent to `POST /api/assistant/chat/` identically to typed text —
no separate voice endpoint exists.

The system prompt enforces a structured ordering arc for voice sessions:
1. Search for the item → confirm name + price in the reply
2. Propose `add_to_cart` for one item at a time (never silently)
3. Ask "Anything else?" after each addition
4. Propose checkout when the customer is done

---

## Three-Party Conversation

Every thread can have three participant types:

| Role | Who | Rendered as |
|------|-----|-------------|
| `user` | Customer (typed or voice) | Right-aligned bubble |
| `assistant` | Nidhi AI | Left-aligned, bot icon |
| `admin` | Admin team member | Left-aligned, distinct color, name shown |

When the LLM encounters `admin` messages in history, it acknowledges the handoff
and defers cart actions to the admin.

Admins post into any thread via `POST …/admin-reply/`. The message is stored as
`AssistantMessage(role='admin', sender_name=<admin display name>)` and becomes
part of the thread history the customer sees and the LLM reads.

---

## Anonymous Sessions

Unauthenticated users can use the chat widget. For guest sessions:
- `AssistantConversation.user` is `null`
- `AssistantConversation.anon_session` holds a client-generated opaque string (UUID stored
  in `localStorage("assistant_conversation_id")` on the frontend)
- The view scopes thread lookup to `anon_session` — a guest can only resume their own thread
- Cart and order tools return a "please log in" message for anonymous users (enforced
  per-tool, not at the view level — the view does not block anonymous traffic)

## Human Escalation (`needs_human`)

`needs_human=True` is set on the conversation when:
1. The LLM returns `"escalate": true` in its JSON envelope (e.g. a complex complaint or
   sensitive query)
2. The `escalate_to_human` action is built (treated as a tool call result)

It is **cleared automatically** when an admin posts a reply to the thread
(`POST …/admin-reply/`), signalling that a human is now engaged.

In the admin panel, threads with `needs_human=True` appear highlighted and can be filtered
with `?needs_human=true`. A sidebar badge shows the count of threads needing attention.

## Message Role Visibility

| Role | Visible to customer | Visible to admin | Sent to LLM |
|------|--------------------|--------------------|-------------|
| `user` | Yes | Yes | Yes |
| `assistant` | Yes | Yes | Yes |
| `admin` | Yes | Yes | Yes |
| `tool` | No | Yes | Yes (as observation) |
| `system` | No | No | Yes (as system prompt) |

`tool` and `system` messages are filtered out of customer-facing responses. The LLM
receives the full history including tool observations.

## Conversation Persistence & Thread Management

- All messages are persisted immediately on every turn (user + AI + admin + tool)
- A customer can have unlimited threads; the frontend lists them sorted by `updated_at`
- `MAX_HISTORY_TURNS = 8` **pairs** (user + assistant) are sent to the LLM per request;
  older turns stay in the DB for the full audit trail but are not included in the LLM
  context. This prevents context bloat on long conversations.
- `MAX_ITERATIONS = 4` — the agent loop runs at most 4 tool-call cycles per turn before
  being forced to a final reply
- Thread title is auto-generated by the LLM on the first turn and stored on
  `AssistantConversation.title`
- `status` lifecycle: `active` → `resolved` (admin action) → `archived`
- `needs_human=True` highlights the thread in the admin dashboard

---

## Admin Dashboard Integration

The admin panel polls `GET /api/assistant/conversations/admin/` every 5 seconds
when a thread is open. Filters available: `needs_human=true`, `status`, `user_id`,
date range. Unread/needs-attention count shown as a badge in the sidebar.

---

## Multilingual Replies

The `language` field (`en`, `hi`, `hinglish`, `gu`, `mr`, `pa`) controls
`final_reply` language only. The JSON envelope, tool calls, and all DB content
always stay in English.

---

## Rate Limiting

| Throttle | Limit |
|----------|-------|
| `AssistantBurstThrottle` | 20 requests/minute |
| `AssistantDailyThrottle` | 500 requests/day |

---

## LLM Configuration

```env
LLM_API_KEY=sk-or-v1-...
MODEL_PROVIDER=openrouter
LLM_MODEL=minimax/minimax-m2.5

# Optional: stronger model for the assistant
ASSISTANT_MODEL_PROVIDER=openrouter
ASSISTANT_LLM_MODEL=openai/gpt-4o-mini
```

---

## Graceful Degradation

```
LLM unavailable          → FALLBACK_REPLY (no crash)
Bad JSON from LLM        → one repair prompt → if still bad → FALLBACK_REPLY
Unknown tool/action name → error fed back to LLM (not executed)
Tool raises exception    → {'error': 'tool_error'} returned as observation
```

---

## Removed: support.ChatSession Escalation

An earlier design had `AssistantConversation.escalated_session` point to a
`support.ChatSession` record. That FK, the `ChatSession`/`ChatMessage` models, and
the `/api/chat-sessions/` endpoints have all been **removed** (migrations
`assistant.0003_remove_escalated_session` and `support.0004_delete_chat_models`).
Human-admin participation now happens directly inside `AssistantMessage` via the
`admin` role.
