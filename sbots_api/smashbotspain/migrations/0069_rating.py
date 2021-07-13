# Generated by Django 3.1.6 on 2021-07-09 23:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0068_auto_20210709_2035'),
    ]

    operations = [
        migrations.CreateModel(
            name='Rating',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.IntegerField(default=1000)),
                ('guild', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.guild')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.player')),
            ],
        ),
    ]
