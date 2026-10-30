import os
import ssl
import smtplib
import time
import logging
from email.message import EmailMessage
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def claim(conn):
    with conn.transaction():
        row = conn.execute('''SELECT n.*, e.correo, e.activo AS destinatario_activo, h.estado_nuevo
            FROM notificaciones n JOIN empleados e ON e.id = n.destinatario_id
            LEFT JOIN historial_solicitud h ON h.id = n.historial_id
            WHERE ((n.estado_envio IN ('PENDIENTE', 'FALLIDA') AND n.proximo_intento_en <= CURRENT_TIMESTAMP)
               OR (n.estado_envio = 'EN_PROCESO' AND n.bloqueada_hasta < CURRENT_TIMESTAMP))
            ORDER BY n.proximo_intento_en, n.id LIMIT 1 FOR UPDATE OF n SKIP LOCKED''').fetchone()
        if row is None:
            return None
        lease = conn.execute('''UPDATE notificaciones SET estado_envio = 'EN_PROCESO',
            bloqueada_hasta = clock_timestamp() + interval '5 minutes', intentos = intentos + 1,
            enviada_en = NULL WHERE id = %s RETURNING bloqueada_hasta, intentos''', (row['id'],)).fetchone()
        row.update(lease)
        return row


def send(row):
    if not row['destinatario_activo']:
        raise ValueError('Destinatario inactivo')
    message = EmailMessage()
    message['From'] = os.environ['SMTP_FROM']
    message['To'] = row['correo']
    message['Message-ID'] = f"<ausencia-{row['id']}@{os.environ['SMTP_MESSAGE_ID_DOMAIN']}>"
    message['Subject'] = 'Aviso del sistema de ausencias'
    if row['tipo'] == 'CAMBIO_ESTADO':
        text = f"Su solicitud {row['solicitud_id']} cambió al estado {row['estado_nuevo']}. Consulte el portal interno para ver el detalle."
    else:
        text = f"La solicitud {row['solicitud_id']} requiere revisión. Ingrese al panel administrativo para consultar su bandeja."
    message.set_content(text)
    host = os.environ['SMTP_HOST']
    mode = os.environ.get('SMTP_TLS_MODE', 'starttls')
    port = int(os.environ.get('SMTP_PORT', '465' if mode == 'ssl' else '587'))
    tls_context = ssl.create_default_context()
    if mode not in ('ssl', 'starttls'):
        raise ValueError('SMTP requiere TLS')
    client = smtplib.SMTP_SSL(host, port, timeout=30, context=tls_context) if mode == 'ssl' else smtplib.SMTP(host, port, timeout=30)
    with client:
        if mode == 'starttls':
            client.ehlo()
            client.starttls(context=tls_context)
            client.ehlo()
        username = os.environ.get('SMTP_USER')
        if username:
            client.login(username, os.environ['SMTP_PASSWORD'])
        client.send_message(message)


def run_once(conn):
    row = claim(conn)
    if row is None:
        return False
    try:
        send(row)
    except Exception as exc:
        # No se guardan respuestas SMTP ni datos personales en el error.
        delay = min(3600, 30 * 2 ** min(row['intentos'], 7))
        conn.execute('''UPDATE notificaciones SET estado_envio = 'FALLIDA', bloqueada_hasta = NULL,
            ultimo_error = %s, proximo_intento_en = clock_timestamp() + (%s * interval '1 second')
            WHERE id = %s AND estado_envio = 'EN_PROCESO' AND bloqueada_hasta = %s''',
            (type(exc).__name__, delay, row['id'], row['bloqueada_hasta']))
    else:
        conn.execute('''UPDATE notificaciones SET estado_envio = 'ENVIADA', bloqueada_hasta = NULL,
            enviada_en = clock_timestamp(), ultimo_error = NULL
            WHERE id = %s AND estado_envio = 'EN_PROCESO' AND bloqueada_hasta = %s''',
            (row['id'], row['bloqueada_hasta']))
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as conn:
                while True:
                    if not run_once(conn):
                        time.sleep(3)
        except psycopg.Error:
            logger.warning('El worker reintentará la conexión a PostgreSQL')
            time.sleep(5)

if __name__ == '__main__':
    main()