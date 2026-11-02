import logging

logger = logging.getLogger(__name__)


def schedule_auto_ttn_quietly(order):
    try:
        from shipping.np_ttn import schedule_auto_ttn
        schedule_auto_ttn(order)
    except Exception:
        logger.warning(
            'NP TTN: не вдалося запланувати замовлення %s',
            getattr(order, 'pk', None),
        )
