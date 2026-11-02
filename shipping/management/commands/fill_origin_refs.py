from django.conf import settings
from django.core.management.base import BaseCommand

from shipping.np_ttn import MSG_NO_KEY
from shipping.origin_refs import fill_missing_refs


class Command(BaseCommand):
    help = 'Заповнює Ref-и точок відправки Нової Пошти'

    def handle(self, *args, **options):
        if not (getattr(settings, 'NOVAPOSHTA_API_KEY', '') or '').strip():
            self.stderr.write(MSG_NO_KEY)
            return
        for line in fill_missing_refs():
            self.stdout.write(line)
