# Generated by Django 5.1.3 on 2024-12-03 18:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0006_alter_customuser_username'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='activity',
            options={'ordering': ['-created_at'], 'verbose_name_plural': 'Activities'},
        ),
        migrations.AddField(
            model_name='activity',
            name='latitude',
            field=models.FloatField(blank=True, help_text='Latitude for mapping the activity location.', null=True),
        ),
        migrations.AddField(
            model_name='activity',
            name='longitude',
            field=models.FloatField(blank=True, help_text='Longitude for mapping the activity location.', null=True),
        ),
        migrations.AlterField(
            model_name='activity',
            name='activity_type',
            field=models.CharField(choices=[('WATCH_MOVIE', 'Watching a Movie'), ('READ_BOOK', 'Reading a Book'), ('PLAY_GAME', 'Playing a Game'), ('LISTEN_MUSIC', 'Listening to Music'), ('DINING_OUT', 'Dining Out'), ('HIKING', 'Hiking'), ('GYM', 'Gym')], help_text='The type of activity.', max_length=20),
        ),
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(fields=['user'], name='authenticat_user_id_ed55d0_idx'),
        ),
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(fields=['created_at'], name='authenticat_created_307f5e_idx'),
        ),
    ]
