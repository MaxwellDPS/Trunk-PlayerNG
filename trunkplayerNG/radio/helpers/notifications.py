import logging, apprise
from django.contrib.auth.models import User
from django.conf import settings
from radio.models import TalkGroup, Unit, UserAlert

if settings.SEND_TELEMETRY:
    from sentry_sdk import capture_exception

logger = logging.getLogger(__name__)


def handle_transmission_notification(TransmissionX: dict) -> None:
    """
    Handles Dispatching Transmission Notifications
    """
    from radio.tasks import publish_user_notification

    talkgroup = TransmissionX["talkgroup"]
    units = TransmissionX["units"]
    logging.debug(f'[+] Handling Notifications for TX:{TransmissionX["UUID"]}')

    for alert in UserAlert.objects.all():
        alert: UserAlert

        try:
            if alert.talkgroups.filter(UUID=talkgroup).exists():
                talkgroupObject = TalkGroup.objects.get(UUID=talkgroup)
                talkgroup: TalkGroup
                if alert.emergencyOnly:
                    if TransmissionX["emergency"]:
                        publish_user_notification.delay(
                            "Talkgroup",
                            TransmissionX["UUID"],
                            talkgroupObject.alphaTag,
                            alert.appRiseURLs,
                            alert.appRiseNotification,
                            alert.webNotification,
                            TransmissionX["emergency"],
                            alert.body,
                            alert.title,
                        )
                        logging.debug(
                            f'[+] Handling Sent notification for TX:{TransmissionX["UUID"]} - {alert.name} - {alert.user}'
                        )
                else:
                    publish_user_notification.delay(
                        "Talkgroup",
                        TransmissionX["UUID"],
                        talkgroupObject.alphaTag,
                        alert.appRiseURLs,
                        alert.appRiseNotification,
                        alert.webNotification,
                        TransmissionX["emergency"],
                        alert.body,
                        alert.title,
                    )
                    logging.debug(
                        f'[+] Handling Sent notification for TX:{TransmissionX["UUID"]} - {alert.name} - {alert.user}'
                    )

            AlertUnits = alert.units.all()
            AlertUnitUUIDs = [str(unit.UUID) for unit in AlertUnits]

            ActiveUnits = []
            for unit in units:
                if str(unit) in AlertUnitUUIDs:
                    ActiveUnits.append(unit)

            if len(ActiveUnits) > 0:
                AUs = ""

                for AU in ActiveUnits:
                    AU: Unit = Unit.objects.get(UUID=AU)
                    if AU.description != "" and AU.description != None:
                        UnitID = AU.description
                    else:
                        UnitID = str(AU.decimalID)
                    AUs = AUs + f"; {UnitID}"

                if alert.emergencyOnly:
                    if TransmissionX["emergency"]:
                        publish_user_notification.delay(
                            "Unit",
                            TransmissionX["UUID"],
                            AUs,
                            alert.appRiseURLs,
                            alert.appRiseNotification,
                            alert.webNotification,
                            TransmissionX["emergency"],
                            alert.body,
                            alert.title,
                        )
                        logging.debug(
                            f'[+] Handling Sent notification for TX:{TransmissionX["UUID"]} - {alert.name} - {alert.user}'
                        )
                else:
                    publish_user_notification.delay(
                        "Unit",
                        TransmissionX["UUID"],
                        AUs,
                        alert.appRiseURLs,
                        alert.appRiseNotification,
                        alert.webNotification,
                        TransmissionX["emergency"],
                        alert.body,
                        alert.title,
                    )
                    logging.debug(
                        f'[+] Handling Sent notification for TX:{TransmissionX["UUID"]} - {alert.name} - {alert.user}'
                    )
        except Exception as e:
            if settings.SEND_TELEMETRY:
                capture_exception(e)


def format_message(
    type: str, value: str, url: str, emergency: bool, title: str, body: str
) -> tuple[str, str]:
    title = title.replace("%T", type)
    title = title.replace("%I", value)
    title = title.replace("%E", str(emergency))
    title = title.replace("%U", url)

    body = body.replace("%T", type)
    body = body.replace("%I", value)
    body = body.replace("%E", str(emergency))
    body = body.replace("%U", url)

    return title, body


def broadcast_user_notification(
    type: str,
    TransmissionUUID: str,
    value: str,
    appRiseURLs: str,
    appRiseNotification: bool,
    webNotification: bool,
    emergency: bool,
    titleTemplate: str,
    bodyTemplate: str,
) -> None:
    if webNotification:
        # broadcast_web_notification(alert, Transmission, type, value)
        pass
    if appRiseNotification:
        URLs = appRiseURLs.split(",")
        apobj = apprise.Apprise()

        for URL in URLs:
            apobj.add(URL)

        body, title = format_message(
            type, value, TransmissionUUID, emergency, titleTemplate, bodyTemplate
        )

        logging.debug(f"[+] BROADCASTING TO APPRISE {TransmissionUUID}")
        apobj.notify(
            body=body,
            title=title,
        )
