# Generated by Django 3.1.6 on 2021-03-04 22:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0032_arena_guild'),
    ]

    operations = [
        migrations.AddField(
            model_name='region',
            name='guild',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.guild'),
        ),
        migrations.AddField(
            model_name='tier',
            name='guild',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.guild'),
        ),
    ]