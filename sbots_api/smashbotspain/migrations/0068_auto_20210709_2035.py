# Generated by Django 3.1.6 on 2021-07-09 18:35

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0067_auto_20210709_2009'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gameset',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]