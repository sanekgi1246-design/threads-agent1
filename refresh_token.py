"""Продлевает долгоживущий токен Threads (живёт 60 дней) и сохраняет его в секрет репозитория."""
import os
import subprocess

from common import env
from threads_api import Threads


def main():
    data = Threads.refresh_long_lived(env("THREADS_ACCESS_TOKEN", required=True))
    days = int(data.get("expires_in", 0)) // 86400
    if not os.environ.get("GH_TOKEN"):
        raise SystemExit("Нет секрета GH_PAT — новый токен получен, но сохранить его некуда.")
    subprocess.run(["gh", "secret", "set", "THREADS_ACCESS_TOKEN", "--body", data["access_token"]],
                   check=True)
    print(f"Токен продлён ещё на {days} дн.")


if __name__ == "__main__":
    main()
