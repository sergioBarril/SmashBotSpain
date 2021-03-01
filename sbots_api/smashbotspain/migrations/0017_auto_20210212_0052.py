# Generated by Django 3.1.6 on 2021-02-11 23:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0016_auto_20210211_0043'),
    ]

    operations = [
        migrations.AlterField(
            model_name='arena',
            name='status',
            field=models.CharField(choices=[('WAITING', 'Waiting'), ('CONFIRMATION', 'Confirmation'), ('PLAYING', 'Playing'), ('CLOSED', 'Closed')], default='WAITING', max_length=12),
        ),
    ]