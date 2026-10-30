import logging
import os
import signal
import smtplib
import ssl
import threading
from email.message import EmailMessage

import psycopg
from psycopg.rows import dict_row

stop = threading.Event()
logger = logging.getLogger('notificaciones')


def send_email(notification):
    message = EmailMessage()
    message['From'] = os.environ['SMTP_FROM']
    message['To'] = notification['correo_destino']
    message['Subject'] = notification['asunto']
    message['Message-ID'] = f"<ausencia-notificacion-{notification['id']}@{os.environ['SMTP_MESSAGE_DOMAIN']}>"
    message.set_content(notification['contenido'])
    mode = os.environ.get('SMTP_SECURITY', 'STARTTLS')
    if mode not in {'STARTTLS', 'SSL'}:
        raise ValueError('SMTP_SECURITY debe ser STARTTLS o SSL')
    port = int(os.environ.get('SMTP_PORT', '465' if mode == 'SSL' else '587'))
    context = ssl.create_default_context()
    if mode == 'SSL':
        client = smtplib.SMTP_SSL(os.environ['SMTP_HOST'], port, timeout=30, context=context)
    else:
        client = smtplib.SMTP(os.environ['SMTP_HOST'], port, timeout=30)
    with client:
        if mode == 'STARTTLS':
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        username = os.environ.get('SMTP_USERNAME')
        if username:
            client.login(username, os.environ['SMTP_PASSWORD'])
        client.send_message(message)


def process_one():
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row, connect_timeout=10) as connection:
        with connection.transaction():
            row = connection.execute("SELECT * FROM notificaciones WHERE (estado_envio IN ('PENDIENTE','FALLIDA') AND proximo_intento_en<=now()) OR (estado_envio='EN_PROCESO' AND proximo_intento_en<=now()) ORDER BY proximo_intento_en,id LIMIT 1 FOR UPDATE SKIP LOCKED").fetchone()
            if not row:
                return False
            claimed = connection.execute("UPDATE notificaciones SET estado_envio='EN_PROCESO',intentos=intentos+1,proximo_intento_en=now()+interval '10 minutes' WHERE id=%s RETURNING intentos", (row['id'],)).fetchone()
            attempt = claimed['intentos']
        try:
            send_email(row)
        except Exception as exc:
            error_name = type(exc).__name__
            delay = min(3600, 30 * 2 ** min(attempt, 7))
            connection.execute("UPDATE notificaciones SET estado_envio='FALLIDA',ultimo_error=%s,proximo_intento_en=now()+(%s * interval '1 second') WHERE id=%s AND estado_envio='EN_PROCESO' AND intentos=%s", (error_name, delay, row['id'], attempt))
            logger.warning('Entrega fallida para notificación %s: %s', row['id'], error_name)
        else:
            connection.execute("UPDATE notificaciones SET estado_envio='ENVIADA',enviada_en=now(),ultimo_error=NULL WHERE id=%s AND estado_envio='EN_PROCESO' AND intentos=%s", (row['id'], attempt))
        return True


def main():
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set():
        try:
            if not process_one():
                stop.wait(5)
        except Exception as exc:
            logger.error('Cola no disponible: %s', type(exc).__name__)
            stop.wait(10)


if __name__ == '__main__':
    main()