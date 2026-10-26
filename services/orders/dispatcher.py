"""Transactional-outbox publisher. Run only when RabbitMQ is configured.

RabbitMQ is not required for API ordering; events remain pending in the order DB.
"""
import json
import os
import time
import pika
from sqlalchemy import select
from services.orders.main import Session, Outbox

EXCHANGE='cloudcart.events'

def run_once():
    connection=pika.BlockingConnection(pika.URLParameters(os.environ.get('RABBITMQ_URL','amqp://guest:guest@localhost:5672/%2F')))
    try:
        ch=connection.channel();ch.confirm_delivery();ch.exchange_declare(exchange=EXCHANGE,exchange_type='topic',durable=True)
        # Declare the durable queue before publishing so the worker may start later.
        ch.queue_declare(queue='cloudcart.notifications',durable=True)
        ch.queue_bind(exchange=EXCHANGE,queue='cloudcart.notifications',routing_key='order.*')
        with Session() as db:
            rows=db.scalars(select(Outbox).where(Outbox.published.is_(False)).order_by(Outbox.id).limit(50)).all()
            for row in rows:
                # Publisher confirms + consumer event-ID dedupe; occasional duplicates are possible.
                ok=ch.basic_publish(exchange=EXCHANGE,routing_key=row.event_type,body=row.payload.encode(),properties=pika.BasicProperties(delivery_mode=2,content_type='application/json',message_id=str(row.id)),mandatory=False)
                if not ok:break
                row.published=True;db.commit()
            return len(rows)
    finally:connection.close()

if __name__=='__main__':
    print('Order event publisher started (Ctrl+C to stop)')
    while True:
        try:run_once()
        except pika.exceptions.AMQPError as e:print('RabbitMQ unavailable:',e)
        time.sleep(3)
