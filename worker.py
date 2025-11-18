import os
import redis
from rq import Worker, Queue, Connection
from app import create_app

listen = ['default']

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    app = create_app()
    app.app_context().push()
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()
