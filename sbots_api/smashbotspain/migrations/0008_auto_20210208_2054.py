# Generated by Django 3.1.6 on 2021-02-08 19:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0007_auto_20210208_2053'),
    ]

    operations = [
        migrations.AlterField(
            model_name='arena',
            name='players',
            field=models.ManyToManyField(through='smashbotspain.ArenaPlayer', to='smashbotspain.Player'),
        ),
    ]