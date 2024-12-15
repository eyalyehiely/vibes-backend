# Generated by Django 5.1.3 on 2024-12-13 17:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0014_customuser_search_friends'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='latitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='longitude',
            field=models.FloatField(blank=True, null=True),
        ),
    ]