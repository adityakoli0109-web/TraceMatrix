from redis import Redis
from rq import Worker

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is required for the background worker")
    redis = Redis.from_url(settings.redis_url)
    Worker(["tracematrix"], connection=redis).work()


if __name__ == "__main__":
    main()
