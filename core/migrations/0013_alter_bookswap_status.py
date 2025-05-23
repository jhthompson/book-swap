# Generated by Django 5.2 on 2025-05-12 23:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_alter_bookswapevent_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookswap",
            name="status",
            field=models.CharField(
                choices=[
                    ("PROPOSED", "Proposed"),
                    ("CANCELLED", "Cancelled"),
                    ("ACCEPTED", "Accepted"),
                    ("DECLINED", "Declined"),
                ],
                default="PROPOSED",
                max_length=9,
            ),
        ),
    ]
