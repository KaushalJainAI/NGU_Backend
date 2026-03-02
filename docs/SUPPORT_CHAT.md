# Customer Support System

The `support` app handles user feedback and direct communication between administrators and customers. It has two main domains: Contact Submissions and Real-time Chat Sessions.

## 1. Contact Submissions
This handles generalized queries from the "Contact Us" public forms.

- **Throttling:** Anonymous users are aggressively throttled (Spam Protection) using `AnonRateThrottle` limited to 5 requests per hour.
- **Workflow:** 
  - User submits form (`status="new"`).
  - Admins can `POST /api/support/contact/mark_read/`.
  - Admins can `POST /api/support/contact/reply/` with internal `admin_notes` to mark it as responded.

## 2. Real-Time Chat Sessions
This system enables live support tickets, often tied specifically to previous `Order` IDs.

### Chat Architecture
- **Ticket Tracking:** Every chat initializes a unique `ChatSession` containing a rigid `session_id`.
- **Roles:**
  - **User:** Opens the chat and posts questions. Can only view their own chats unless opening a guest ticket.
  - **Admin/Staff:** Can view all active sessions, claim tickets (`assign`), and `close` tickets.
  - **System:** Generates automated messages (e.g., "This chat session has been closed").

### Endpoints (Viewsets)

- `GET /api/support/chats/` (List active tickets - Admin sees all, User sees theirs)
- `POST /api/support/chats/{pk}/messages/` (Post a new text message in the session)
- `POST /api/support/chats/{pk}/close/` (Gracefully close the ticket)
- `POST /api/support/chats/{pk}/assign/` (Admin claims responsibility for the ticket)

*Note: The Chat system uses HTTP polling or server requests currently, rather than native WebSockets (`channels`), to maintain a simpler infrastructural footprint while still providing immediate communication.*
