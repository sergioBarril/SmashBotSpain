# Generated by Django 3.1.6 on 2021-07-04 20:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0058_message_mode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='tier',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.tier'),
        ),
    ]
