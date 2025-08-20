import os, json, requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")  # e.g. "my-firebase-project"
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

def _require_env():
    if not FIREBASE_PROJECT_ID:
        raise RuntimeError("FIREBASE_PROJECT_ID env var is not set")
    if not (GOOGLE_APPLICATION_CREDENTIALS_JSON or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
        raise RuntimeError("Set GOOGLE_APPLICATION_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS")

def _get_access_token():
    _require_env()
    if GOOGLE_APPLICATION_CREDENTIALS_JSON:
        info = json.loads(GOOGLE_APPLICATION_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=SCOPES
        )
    creds.refresh(Request())
    return creds.token

def _post_fcm(payload: dict):
    url = f"https://fcm.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/messages:send"
    try:
        access_token = _get_access_token()
        resp = requests.post(url, headers={"Authorization": f"Bearer {access_token}"}, json=payload, timeout=10)
        j = resp.json() if resp.content else {}
        return resp.ok, resp.status_code, j
    except requests.RequestException as e:
        return False, 0, {"error": {"message": str(e)}}

def send_fcm_v1_to_token(token: str, title: str, body: str, data: dict | None = None):
    payload = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": {k: str(v) for k, v in (data or {}).items()},
            "android": {"priority": "HIGH"},
            "apns": {"headers": {"apns-priority": "10"}},
        }
    }
    ok, code, j = _post_fcm(payload)
    drop_codes = {"NOT_FOUND", "UNREGISTERED", "INVALID_ARGUMENT"}
    status_text = str(j.get("error", {}).get("status", "")).upper()
    drop = status_text in drop_codes
    return {"ok": ok, "status": code, "drop_token": drop, "detail": j}

def send_fcm_v1_to_topic(topic: str, title: str, body: str, data: dict | None = None):
    payload = {
        "message": {
            "topic": topic,
            "notification": {"title": title, "body": body},
            "data": {k: str(v) for k, v in (data or {}).items()},
        }
    }
    ok, code, j = _post_fcm(payload)
    return {"ok": ok, "status": code, "detail": j}
