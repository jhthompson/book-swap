# Generated by Django 5.2 on 2025-05-03 04:04

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_alter_booklisting_isbn"),
    ]

    operations = [
        migrations.AddField(
            model_name="booklisting",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
    ]
