from django.core.management.base import BaseCommand

from ReelRoots_app.models import ContributorSubmission
from ReelRoots_app.moderation import process_submission


class Command(BaseCommand):
    help = "Process submitted contributor content through verification and moderation preparation."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        submissions = ContributorSubmission.objects.filter(status="submitted").order_by("created_at")[:options["limit"]]
        for submission in submissions:
            self.stdout.write(f"Processing {submission.id}")
            process_submission(submission.id)
        self.stdout.write(self.style.SUCCESS(f"Processed {len(submissions)} submission(s)."))
