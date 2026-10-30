import logging
import os
import smtplib
import ssl
import time
from email.message import EmailMessage

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def send_mail(notification):
    host = os.environ['SMTP_HOST']
    sender = os.environ['SMTP_FROM']
    mode = os.environ.get('SMTP_SECURITY', 'STARTTLS')
    if mode not in ('STARTTLS', 'SSL'):
        raise ValueError('SMTP_SECURITY debe ser STARTTLS o SSL')
    message = EmailMessage()
    message['From'] = sender
    message['To'] = notification['correo']
    message['Subject'] = 'Aviso de solicitud de ausencia'
    if notification['tipo'] == 'CAMBIO_ESTADO':
        text = f"La solicitud {notification['solicitud_id']} cambió al estado {notification['estado_nuevo']}."
    else:
        text = f"La solicitud {notification['solicitud_id']} está pendiente de su revisión."
    message.set_content(text + '\nConsulte el sistema interno para ver el detalle.')
    context = ssl.create_default_context()
    port = int(os.environ.get('SMTP_PORT', '465' if mode == 'SSL' else '587'))
    client_class = smtplib.SMTP_SSL if mode == 'SSL' else smtplib.SMTP
    arguments = {'host': host, 'port': port, 'timeout': 20}
    if mode == 'SSL':
        arguments['context'] = context
    with client_class(**arguments) as client:
        if mode == 'STARTTLS':
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        username = os.environ.get('SMTP_USERNAME')
        if username:
            client.login(username, os.environ['SMTP_PASSWORD'])
        refused = client.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def process_notifications(limit=100):
    processed = 0
    try:
        with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as db:
            for _ in range(limit):
                # El bloqueo evita que dos procesos envíen la misma fila simultáneamente.
                with db.transaction():
                    row = db.execute("SELECT n.*, u.correo, u.activo, h.estado_nuevo FROM notificaciones n JOIN usuarios u ON u.id = n.destinatario_id LEFT JOIN historial_solicitud h ON h.id = n.historial_id WHERE n.estado_envio IN ('PENDIENTE', 'ERROR', 'PROCESANDO') AND n.proximo_intento_en <= CURRENT_TIMESTAMP AND (n.bloqueada_hasta IS NULL OR n.bloqueada_hasta <= CURRENT_TIMESTAMP) ORDER BY n.proximo_intento_en, n.id FOR UPDATE OF n SKIP LOCKED LIMIT 1").fetchone()
                    if not row:
                        break
                    db.execute("UPDATE notificaciones SET estado_envio = 'PROCESANDO', intentos = intentos + 1, bloqueada_hasta = CURRENT_TIMESTAMP + interval '2 minutes' WHERE id = %s", (row['id'],))
                    try:
                        if not row['activo']:
                            raise ValueError('Destinatario inactivo')
                        send_mail(row)
                    except Exception as exc:
                        # No se persisten mensajes SMTP que puedan contener información sensible.
                        error = type(exc).__name__
                        delay = min(3600, 30 * 2 ** min(row['intentos'], 7))
                        db.execute("UPDATE notificaciones SET estado_envio = 'ERROR', ultimo_error = %s, bloqueada_hasta = NULL, proximo_intento_en = clock_timestamp() + %s * interval '1 second' WHERE id = %s", (error, delay, row['id']))
                    else:
                        db.execute("UPDATE notificaciones SET estado_envio = 'ENVIADA', enviada_en = clock_timestamp(), bloqueada_hasta = NULL, ultimo_error = NULL WHERE id = %s", (row['id'],))
                    processed += 1
    except (psycopg.Error, KeyError):
        logger.error('No fue posible procesar la cola de notificaciones')
    return processed


def main():
    logging.basicConfig(level=logging.INFO)
    interval = max(1, int(os.environ.get('NOTIFICATION_POLL_SECONDS', '10')))
    while True:
        process_notifications()
        time.sleep(interval)


if __name__ == '__main__':
    main()