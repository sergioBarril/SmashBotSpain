# Generated by Django 3.1.6 on 2021-07-07 17:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0063_auto_20210707_1638'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='number',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
    ]
