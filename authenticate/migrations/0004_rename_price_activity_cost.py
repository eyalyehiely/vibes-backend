# Generated by Django 5.1.3 on 2024-12-03 08:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0003_alter_activity_id'),
    ]

    operations = [
        migrations.RenameField(
            model_name='activity',
            old_name='price',
            new_name='cost',
        ),
    ]
