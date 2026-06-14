"""Create a demo account for trying out JarvisX locally.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/seed_demo_user.py

Creates (or updates) a user with:
    username: demo_user
    password: demopassword123

If Ollama is running locally with a model pulled (e.g. `ollama pull llama3.2:3b`),
this also configures the account to use it so you can chat with no API key.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, init_db
from app.models import User
from app.security import hash_password

DEMO_USERNAME = "demo_user"
DEMO_PASSWORD = "demopassword123"
DEMO_EMAIL = "demo_user@example.com"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == DEMO_USERNAME).first()
        if user:
            print(f"Demo user '{DEMO_USERNAME}' already exists (id={user.id}).")
        else:
            user = User(
                username=DEMO_USERNAME,
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name="Demo User",
                llm_provider="ollama",
                llm_model="llama3.2:3b",
            )
            db.add(user)
            db.commit()
            print(f"Created demo user '{DEMO_USERNAME}' (id={user.id}).")

        print()
        print("Log in with:")
        print(f"  username: {DEMO_USERNAME}")
        print(f"  password: {DEMO_PASSWORD}")
        print()
        print("This account is configured to use a local Ollama model (llama3.2:3b).")
        print("Install Ollama (https://ollama.com) and run `ollama pull llama3.2:3b`,")
        print("or change the provider in Settings to Anthropic/OpenAI/Google and add an API key.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
