# Generated by Django 5.2 on 2025-05-08 01:13

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_remove_bookswap_status_bookswapdecision"),
    ]

    operations = [
        migrations.RenameField(
            model_name="bookswapdecision",
            old_name="decision",
            new_name="status",
        ),
        migrations.RenameField(
            model_name="bookswapdecision",
            old_name="decision_made_on",
            new_name="timestamp",
        ),
    ]
