"""Generate local credentials without printing or overwriting existing secrets."""

import secrets
from pathlib import Path


def main():
    destination = Path(__file__).resolve().parents[2] / "runtime/private/langfuse.env"
    destination.parent.mkdir(parents=True, exist_ok=True)
    values = {name: secrets.token_hex(32) for name in (
        "POSTGRES_PASSWORD", "CLICKHOUSE_PASSWORD", "REDIS_AUTH", "MINIO_PASSWORD",
        "SALT", "ENCRYPTION_KEY", "NEXTAUTH_SECRET", "LANGFUSE_ADMIN_PASSWORD",
    )}
    values.update(
        LANGFUSE_PUBLIC_KEY="pk-lf-" + secrets.token_hex(16),
        LANGFUSE_SECRET_KEY="sk-lf-" + secrets.token_hex(32),
        LANGFUSE_ADMIN_EMAIL="evaluator@sapilot.local",
        LANGFUSE_BASE_URL="http://localhost:3300",
    )
    try:
        with destination.open("x", encoding="utf-8") as stream:
            stream.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    except FileExistsError:
        print(f"Preserved existing credentials: {destination}")
    else:
        print(f"Created local credentials: {destination}")


if __name__ == "__main__":
    main()
