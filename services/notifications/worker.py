"""Notification worker; prints demo notifications and stores processed event IDs."""
import json
import os
import pika
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column
from shared.database import Base, database

class Notification(Base):
    __tablename__='notifications'
    id:Mapped[int]=mapped_column(primary_key=True)
    event_id:Mapped[str]=mapped_column(String(160),unique=True)
    order_id:Mapped[int]
    message:Mapped[str]=mapped_column(String(300))

Session=database('notifications')

def process(event:dict):
    # Dedupe handles at-least-once RabbitMQ delivery.
    with Session() as db:
        if db.scalar(select(Notification).where(Notification.event_id==event['event_id'])):return False
        msg=f'Order #{event["order_id"]}: {event["status"]} (store #{event["store_id"]})'
        db.add(Notification(event_id=event['event_id'],order_id=event['order_id'],message=msg))
        db.commit();print('NOTIFICATION:',msg,flush=True)
        return True

def main():
    connection=pika.BlockingConnection(pika.URLParameters(os.environ.get('RABBITMQ_URL','amqp://guest:guest@localhost:5672/%2F')))
    channel=connection.channel();channel.exchange_declare(exchange='cloudcart.events',exchange_type='topic',durable=True)
    channel.queue_declare(queue='cloudcart.notifications',durable=True)
    channel.queue_bind(exchange='cloudcart.events',queue='cloudcart.notifications',routing_key='order.*')
    channel.basic_qos(prefetch_count=1)
    def handle(ch, method, props, body):
        try:process(json.loads(body));ch.basic_ack(method.delivery_tag)
        except Exception as err:
            print('Notification processing failed:',err,flush=True)
            ch.basic_nack(method.delivery_tag,requeue=False) # dead-letter queue to be added in reliability stage
    channel.basic_consume(queue='cloudcart.notifications',on_message_callback=handle)
    print('Notification worker listening...',flush=True);channel.start_consuming()

if __name__=='__main__': main()
