from django.core.management.base import BaseCommand

from ReelRoots_app.models import VerificationRequest
from ReelRoots_app.verification_engine import VerificationEngine


class Command(BaseCommand):
    help = "Process queued ReelRoots verification requests."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        requests = VerificationRequest.objects.filter(status="queued").order_by("created_at")[:options["limit"]]
        for request in requests:
            self.stdout.write(f"Processing {request.id}")
            VerificationEngine().process(request.id)
        self.stdout.write(self.style.SUCCESS(f"Processed {len(requests)} request(s)."))
