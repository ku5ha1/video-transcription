import time
from celery import Celery


celery_app = Celery(
    "worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

@celery_app.task
def heavy_lifting_task(name: str):
    time.sleep(30) 
    return f"Hello {name}, your long task is finished!"