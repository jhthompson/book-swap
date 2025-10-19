from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from core.models import UserProfile


class Command(BaseCommand):
    help = "Create a UserProfile for a given user"

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            type=str,
            help="Username of the user to create a profile for",
        )
        parser.add_argument(
            "--city",
            type=str,
            default="Ottawa",
            help="City for the user profile (default: Ottawa)",
        )
        parser.add_argument(
            "--latitude",
            type=float,
            default=45.4215,
            help="Latitude for the user location (default: 45.4215 - Ottawa)",
        )
        parser.add_argument(
            "--longitude",
            type=float,
            default=-75.6972,
            help="Longitude for the user location (default: -75.6972 - Ottawa)",
        )

    def handle(self, *args, **options):
        username = options["username"]
        city = options["city"]
        latitude = options["latitude"]
        longitude = options["longitude"]

        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'User "{username}" does not exist') from exc

        # Check if profile already exists
        if hasattr(user, "userprofile"):
            raise CommandError(f'UserProfile for user "{username}" already exists')

        # Create the UserProfile
        location = Point(longitude, latitude, srid=4326)
        UserProfile.objects.create(
            user=user,
            city=city,
            location=location,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created UserProfile for user "{username}" '
                f"in {city} at ({latitude}, {longitude})"
            )
        )
