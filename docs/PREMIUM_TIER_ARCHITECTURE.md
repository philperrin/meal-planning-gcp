# Premium Tier Architecture & Implementation Specification
**Project:** Meal Planning Assistant (`meal-planning-app-507921`)  
**Status:** Planned / Specification  
**Model:** Free Tier vs. Paid 1-Year Premium Pass  

---

## 1. Executive Summary

This document outlines the architectural plan, feature matrix, data model, and integration pathways to introduce a **Free vs. Premium (1-Year Pass)** model to the Meal Planning Assistant.

Under this model:
- **Free Users** receive access to essential core features: basic meal plan generation, standard recipe library storage, and 5-aisle consolidated grocery lists.
- **Paid Users** pay for a 1-year entitlement unlocking advanced Google Workspace integrations (automated Google Calendar dinners & grocery scheduling, Google Docs recipe generation), expanded multi-week planning, unlimited AI regenerations, and priority AI model cascades.
- **Entitlement Authority:** Centralized in **Google Cloud Firestore** to prevent client-side tampering.
- **Payment Processor:** **Stripe Checkout** with webhook synchronization.

---

## 2. Feature Comparison Matrix

| Feature Domain | Free Tier | Premium Tier (1-Year Access) | Implementation Reference |
| :--- | :--- | :--- | :--- |
| **Meal Plan Generation** | Up to 3 or 5 days per plan; 3 plans / month | Up to 14 days; unlimited regenerations | `services/gemini_service.py` |
| **AI Model Cascade** | Standard tier (`gemini-1.5-flash`) | Priority cascade (`gemini-3.6-flash` -> `gemini-3.5-flash`) | `services/gemini_service.py` |
| **Google Calendar Sync** | ❌ Gated (preview / upgrade CTA) | ✅ Full 1-click sync for dinner events and morning grocery checklist | `services/calendar_service.py` |
| **Google Docs Export** | ❌ Gated (preview / upgrade CTA) | ✅ Automated formatted recipe doc creation in Google Drive | `services/docs_service.py` |
| **Recipe Library** | Up to 10 stored recipes | Unlimited recipes & favorite-based recommendation biasing | `services/storage_service.py` |
| **Grocery List** | Standard 5-aisle consolidated checklist | 5-aisle checklist + pantry item exclusions & unit customizer | `services/shopping_service.py` |
| **Data Storage** | BYOS (`Automated_Meal_Planner_DB.json` on user's Drive) | BYOS on user's Drive (retains 100% data ownership) | `services/storage_service.py` |

---

## 3. Data Storage & Entitlement: Google Cloud Firestore

### 3.1 Why Firestore Over Google Drive?
The application currently uses a **Bring Your Own Storage (BYOS)** architecture where data lives in `Automated_Meal_Planner_DB.json` in the user's private Google Drive. 

Storing payment or subscription status in that Drive file is insecure because users could edit the JSON file to grant themselves premium status.

**Google Cloud Firestore** provides the ideal entitlement authority:
- **Native GCP Project:** Runs directly inside the existing `meal-planning-app-507921` project with no new cloud provider accounts.
- **Zero Fixed Cost:** The Firestore free tier includes 50,000 document reads, 20,000 writes, and 20,000 deletes daily—vastly exceeding the app's needs.
- **Serverless IAM Auth:** Cloud Run service accounts authenticate to Firestore automatically without managing database credentials or passwords.

### 3.2 Firestore Data Schema
Collection: `users`  
Document ID: Google OAuth Subject ID (`sub`) or normalized Google Email.

```json
{
  "google_user_id": "118239482938472918234",
  "email": "user@example.com",
  "display_name": "Jane Doe",
  "tier": "premium",
  "is_premium": true,
  "premium_started_at": "2026-10-10T22:00:00Z",
  "premium_expires_at": "2027-10-10T22:00:00Z",
  "stripe_customer_id": "cus_R4829104829",
  "stripe_checkout_session_id": "cs_test_a1b2c3d4...",
  "payment_type": "one_year_pass",
  "created_at": "2026-10-10T22:00:00Z",
  "updated_at": "2026-10-10T22:00:00Z"
}
```

### 3.3 Entitlement Verification Logic (`services/billing_service.py`)
```python
from datetime import datetime, timezone
from google.cloud import firestore
import os

db = firestore.Client(project=os.getenv("PROJECT_ID", "meal-planning-app-507921"))

def get_user_entitlement(google_user_id: str) -> dict:
    """
    Retrieves entitlement record for the given user.
    Returns free tier if record does not exist or has expired.
    """
    if not google_user_id:
        return {"tier": "free", "is_premium": False}

    doc = db.collection("users").document(google_user_id).get()
    if not doc.exists:
        return {"tier": "free", "is_premium": False}

    data = doc.to_dict()
    expires_at = data.get("premium_expires_at")

    if expires_at and expires_at > datetime.now(timezone.utc):
        return {
            "tier": "premium",
            "is_premium": True,
            "expires_at": expires_at.isoformat()
        }

    return {"tier": "free", "is_premium": False, "expired": True}
```

---

## 4. Payment Infrastructure: Stripe Integration

### 4.1 Payment Mode: 1-Year Pass vs. Recurring Annual Subscription
You can configure Stripe in one of two ways:
1. **1-Year Fixed Pass (`mode='payment'`)**: The user pays once. Access is active for exactly 365 days. No unexpected automatic renewal; users manually purchase another year upon expiration.
2. **Recurring Annual Subscription (`mode='subscription'`)**: Automatically renews every 365 days via Stripe billing until cancelled.

*Recommendation:* Start with the **1-Year Fixed Pass** (`mode='payment'`). It eliminates customer service overhead regarding cancellations/disputes, and customers love predictable non-recurring pricing for utility tools.

### 4.2 Checkout Flow
1. User clicks **"Upgrade to Premium ($X/year)"** in the UI.
2. Frontend calls `POST /api/billing/create-checkout-session`.
3. Backend creates a Stripe Checkout session with `client_reference_id = google_user_id` and metadata containing the user's email.
4. User is redirected to Stripe's hosted checkout page.
5. On completion, Stripe redirects back to `https://<YOUR_APP_DOMAIN>/?billing=success`.

### 4.3 Webhook Handling (`POST /api/billing/webhook`)
Webhooks ensure that payment fulfillment occurs asynchronously and reliably, even if the user closes their browser before returning.

**Events to Handle:**
- `checkout.session.completed`: Validate session payment status, extract `client_reference_id`, calculate `expires_at = now + 365 days`, and upsert Firestore user record.
- `customer.subscription.deleted` *(if using recurring subscription)*: Mark `is_premium = False` in Firestore.

```python
import os
import stripe
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")

@billing_bp.route("/webhook", methods=["POST"])
def handle_stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        google_user_id = session.get("client_reference_id")
        email = session.get("customer_details", {}).get("email")
        customer_id = session.get("customer")

        # Grant 365 days of premium access
        grant_premium_access(
            google_user_id=google_user_id,
            email=email,
            customer_id=customer_id,
            days=365
        )

    return jsonify({"received": True})
```

---

## 5. Backend Gating & Decorators

### 5.1 `@require_premium` Decorator
Placed in `core/auth.py` or `core/entitlements.py`:

```python
from functools import wraps
from flask import session, jsonify
from services.billing_service import get_user_entitlement

def require_premium(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("google_user_profile")
        if not user:
            return jsonify({"status": "error", "error": "Authentication required"}), 401
        
        entitlement = get_user_entitlement(user.get("id"))
        if not entitlement.get("is_premium"):
            return jsonify({
                "status": "error",
                "code": "PREMIUM_REQUIRED",
                "message": "This feature requires an active Premium subscription.",
                "upgrade_url": "/billing/upgrade"
            }), 403

        return f(*args, **kwargs)
    return decorated_function
```

### 5.2 Gated Endpoints in `routes/api.py`
Endpoints to protect:
- `POST /api/sync-calendar` (Calendar scheduling)
- `POST /api/create-docs` (Recipe Google Docs generation)
- `POST /api/generate-plan` (Limit day count: enforce `days <= 5` for free users)

---

## 6. Frontend UI / UX Specifications

### 6.1 User Status Badge
In the top-right header beside the Google OAuth user card:
- **Free Tier:** Shows `Free Plan` badge with an adjacent `[Upgrade to Premium ⭐]` button.
- **Premium Tier:** Shows `⭐ Premium Member (Expires Oct 2027)`.

### 6.2 Upgrade Modal
When a free user clicks **"Sync to Calendar"** or **"Export to Google Docs"**:
- An interactive modal appears:
  > **Unlock Google Calendar Sync & Google Docs with Premium**  
  > • 1-Click dinner schedules on your personal calendar  
  > • Morning "🛒 Groceries" checklist event  
  > • Formatted Google Docs recipe cards generated in Drive  
  > • Unlimited meal plans & priority AI  
  > **$29.00 / year (Only ~$2.40/month)**  
  > `[Continue to Secure Stripe Checkout]`

### 6.3 Graceful Degradation
If a user's 1-year pass expires:
- Their existing Drive recipes, meal history, and calendar events remain 100% intact.
- They are simply prevented from triggering *new* calendar syncs or docs exports until renewed.
- Banner prompt: *"Your Premium pass has expired. Click here to renew for another year."*

---

## 7. Configuration & Environment Variables

Add the following to `.env` (and Google Cloud Secret Manager for Cloud Run):

| Variable | Description |
| :--- | :--- |
| `STRIPE_SECRET_KEY` | Secret API key from Stripe Dashboard (`sk_live_...` or `sk_test_...`) |
| `STRIPE_PUBLISHABLE_KEY` | Public key for frontend components (`pk_live_...` or `pk_test_...`) |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for verifying webhook authenticity (`whsec_...`) |
| `STRIPE_PRICE_ID` | Price ID for the 1-Year Pass product (`price_...`) |
| `PROJECT_ID` | `meal-planning-app-507921` (GCP Project for Firestore) |

---

## 8. Implementation Roadmap (When Resuming)

1. **Phase 1: GCP Firestore Setup**
   - Enable Firestore API in `meal-planning-app-507921`.
   - Add `google-cloud-firestore` to `requirements.txt`.
   - Create `services/billing_service.py` with get/set entitlement functions.
2. **Phase 2: Stripe Integration**
   - Create Stripe product & price for "1-Year Meal Planning Premium".
   - Add `stripe` to `requirements.txt`.
   - Implement checkout session endpoint (`/api/billing/create-checkout-session`).
   - Implement webhook endpoint (`/api/billing/webhook`) and verify with `stripe-cli`.
3. **Phase 3: Route Protection & Gating**
   - Create `@require_premium` decorator.
   - Apply decorator to `/api/sync-calendar` and `/api/create-docs`.
   - Add day-count limit to `/api/generate-plan`.
4. **Phase 4: Frontend UI Enhancements**
   - Add tier check on SPA boot (`/api/user/status`).
   - Add header badge and upgrade CTA modal in `templates/index.html` & `static/js/app.js`.
5. **Phase 5: Automated Testing**
   - Add unit tests in `tests/test_billing.py` mocking Stripe events and Firestore lookups.
   - Verify `pytest -v` passing.
