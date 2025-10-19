from allauth.account.models import EmailAddress

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify a user's email address in django-allauth"

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            type=str,
            help="Username of the user to verify email for",
        )
        parser.add_argument(
            "--email",
            type=str,
            help=(
                "Specific email address to verify "
                "(optional, defaults to user's primary email)"
            ),
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options.get("email")

        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'User "{username}" does not exist') from exc

        # If email is not specified, use the user's primary email
        if not email:
            email = user.email

        if not email:
            raise CommandError(
                f'User "{username}" does not have an email address set. '
                "Please specify an email with --email"
            )

        # Check if EmailAddress exists for this user and email
        try:
            email_address = EmailAddress.objects.get(user=user, email=email)
        except EmailAddress.DoesNotExist:
            # Create the EmailAddress if it doesn't exist
            email_address = EmailAddress.objects.create(
                user=user,
                email=email,
                primary=True,
                verified=True,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created and verified email address "{email}" '
                    f'for user "{username}"'
                )
            )
            return

        # If it exists but is not verified, verify it
        if not email_address.verified:
            email_address.verified = True
            email_address.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully verified email address "{email}" '
                    f'for user "{username}"'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'Email address "{email}" for user "{username}" is already verified'
                )
            )
