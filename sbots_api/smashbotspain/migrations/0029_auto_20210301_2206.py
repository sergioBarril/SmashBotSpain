# Generated by Django 3.1.6 on 2021-03-01 21:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0028_auto_20210301_2046'),
    ]

    operations = [
        migrations.AddField(
            model_name='guild',
            name='list_channel',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='guild',
            name='flairing_channel',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='guild',
            name='spam_channel',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]