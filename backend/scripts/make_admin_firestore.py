"""CLI tool to bootstrap the first admin in Firestore.

Usage:
    python scripts/make_admin_firestore.py <email> [--name NAME]

Requires the Firebase Admin SDK to be initialised. Credentials can be
provided via any of these methods (checked in order):
  A. GOOGLE_APPLICATION_CREDENTIALS env var
  B. FIREBASE_SERVICE_ACCOUNT_B64 env var (base64-encoded JSON)
  C. FIREBASE_CREDENTIALS env var → default firebase-service-account.json

The tool looks up the user by email in Firestore's `users` collection.
If the user doc exists, their role is set to 'admin'; if not, a doc is
created with role='admin'.

This is typically run once during initial project setup to grant the first
admin before the admin panel is usable.
"""
import argparse
import os
import sys

# Ensure the backend package is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Single Firebase init implementation (no independent initialization here).
from app.core.firebase import init_firebase, get_firestore_client  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Bootstrap an admin user in Firestore")
    parser.add_argument("email", help="Email address of the user to promote")
    parser.add_argument("--name", default="", help="Display name (optional)")
    args = parser.parse_args()

    if not init_firebase():
        print("ERROR: Firebase Admin SDK could not be initialized — no service-account "
              "credentials found (GOOGLE_APPLICATION_CREDENTIALS / "
              "FIREBASE_SERVICE_ACCOUNT_B64 / FIREBASE_CREDENTIALS).")
        sys.exit(1)

    email = args.email.strip().lower()
    name = args.name or email.split("@")[0]

    from app.services.firestore_service import set_user_role

    # We need the Firebase UID, which we don't know from just the email — query
    # the Firestore users collection by email.
    db = get_firestore_client()
    users_ref = db.collection("users")
    docs = users_ref.where("email", "==", email).stream()

    uid = None
    for doc in docs:
        uid = doc.id
        break

    if uid is None:
        print(f"No Firestore user found with email '{email}'.")
        print("The user must sign in via the app at least once before running this tool.")
        print("After they sign in, re-run this command to grant them admin.")
        sys.exit(1)

    set_user_role(uid, "admin", email=email, display_name=name)
    print(f"Admin role granted to {email} (uid={uid}).")


if __name__ == "__main__":
    main()
