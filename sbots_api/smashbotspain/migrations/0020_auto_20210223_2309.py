# Generated by Django 3.1.6 on 2021-02-23 22:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0019_arena_channel_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='arena',
            name='status',
            field=models.CharField(choices=[('SEARCHING', 'Searching'), ('WAITING', 'Waiting'), ('CONFIRMATION', 'Confirmation'), ('PLAYING', 'Playing'), ('CLOSED', 'Closed')], default='SEARCHING', max_length=12),
        ),
    ]
