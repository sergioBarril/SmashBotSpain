# Generated by Django 3.1.6 on 2021-02-26 01:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0021_arena_rejected_players'),
    ]

    operations = [
        migrations.AlterField(
            model_name='arena',
            name='rejected_players',
            field=models.ManyToManyField(blank=True, related_name='rejected_players', to='smashbotspain.Player'),
        ),
    ]
