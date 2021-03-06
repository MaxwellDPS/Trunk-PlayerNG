import os
import socketio
import logging

from celery import shared_task
from asgiref.sync import sync_to_async
from django.conf import settings

from radio.helpers.incident import _send_incident, _forward_incident
from radio.helpers.cleanup import _prune_transmissions

from radio.helpers.notifications import (
    _broadcast_web_notification,
    _send_transmission_notifications,
    _broadcast_user_notification,
)

from radio.helpers.transmission import (
    _broadcast_transmission,
    _forward_transmission,
    _send_transmission_to_web,
    _forward_transmission_to_remote_instance,
)

if settings.SEND_TELEMETRY:
    from sentry_sdk import capture_exception

logger = logging.getLogger(__name__)


@shared_task()
def forward_transmission(data: dict, tg_uuid: str, *args, **kwargs) -> None:
    """
    Iterates over Forwarders and dispatches send_transmission
    """
    _forward_transmission(data, tg_uuid)


@shared_task()
def send_transmission_to_web(data: dict, *args, **kwargs) -> None:
    """
    Sends socket.io messages to webclients
    """
    _send_transmission_to_web(data)


@shared_task()
def forward_transmission_to_remote_instance(
    data: dict,
    forwarder_name: str,
    recorder_key: str,
    forwarder_url: str,
    tg_uuid: str,
    *args,
    **kwargs
) -> None:
    """
    Forwards a single TX to a single system
    """
    _forward_transmission_to_remote_instance(
        data, forwarder_name, recorder_key, forwarder_url, tg_uuid
    )


@shared_task()
def forward_incidents(data: dict, created: bool, *args, **kwargs) -> None:
    """
    Iterates over Forwarders and dispatches send_Incident
    """
    _forward_incident(data, created)


@shared_task()
def send_incident(
    data: dict,
    forwarder_name: str,
    recorder_key: str,
    forwarder_url: str,
    created: bool,
    *args,
    **kwargs
):
    """
    Forwards a single Incident to a single system
    """
    _send_incident(data, forwarder_name, recorder_key, forwarder_url, created)


@shared_task()
def import_radio_refrence(
    uuid: str, site_id: str, username: str, password: str, *args, **kwargs
) -> None:
    """
    Imports RR Data
    """
    from radio.helpers.radioreference import RR

    rr: RR = RR(site_id, username, password)
    rr.load_system(uuid)


@shared_task()
def prune_tranmissions(*args, **kwargs) -> None:
    """
    Prunes Transmissions per system based on age
    """
    _prune_transmissions()


@shared_task
def send_transmission_notifications(transmission: dict, *args, **kwargs) -> None:
    """
    Does the logic to send user notifications
    """
    _send_transmission_notifications(transmission)


@shared_task
def broadcast_user_notification(
    type: str,
    transmission: dict,
    value: str,
    alertuser_uuid: str,
    app_rise_urls: str,
    app_rise_notification: bool,
    web_notification: bool,
    emergency: bool,
    title_template: str,
    body_template: str,
    *args,
    **kwargs
) -> None:
    """
    Sends the User a notification(s)
    """
    _broadcast_user_notification(
        type,
        transmission,
        value,
        alertuser_uuid,
        app_rise_urls,
        app_rise_notification,
        web_notification,
        emergency,
        title_template,
        body_template,
    )


@shared_task
def broadcast_web_notification(
    alertuser_uuid: str,
    TransmissionUUID: str,
    emergency: bool,
    title: str,
    body: str,
    *args,
    **kwargs
) -> None:
    """
    Sends web based user notifications
    """
    _broadcast_web_notification(
        alertuser_uuid, TransmissionUUID, emergency, title, body
    )


@shared_task
def broadcast_transmission(event: str, room: str, data: dict) -> None:
    """
    Sends new TX messsage to client
    """
    _broadcast_transmission(event, room, data)
