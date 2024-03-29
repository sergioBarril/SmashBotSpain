# Generated by Django 3.1.6 on 2021-02-07 01:17

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Arena',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('WAITING', 'Waiting'), ('CONFIRM', 'Confirmation'), ('PLAYING', 'Playing'), ('CLOSED', 'Closed')], max_length=7)),
                ('max_players', models.IntegerField(validators=[django.core.validators.MinValueValidator(2)])),
                ('num_players', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Character',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='Main',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('main', models.CharField(choices=[('MAIN', 'Main'), ('SECOND', 'Second')], max_length=10)),
                ('character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.character')),
            ],
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='Tier',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=15)),
            ],
        ),
        migrations.CreateModel(
            name='Player',
            fields=[
                ('discord_id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('characters', models.ManyToManyField(through='smashbotspain.Main', to='smashbotspain.Character')),
                ('regions', models.ManyToManyField(to='smashbotspain.Region')),
                ('tier', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='smashbotspain.tier')),
            ],
        ),
        migrations.AddField(
            model_name='main',
            name='player',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.player'),
        ),
        migrations.CreateModel(
            name='ArenaPlayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=7)),
                ('arena', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.arena')),
                ('player', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='smashbotspain.player')),
            ],
        ),
        migrations.AddField(
            model_name='arena',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_by', to='smashbotspain.player'),
        ),
        migrations.AddField(
            model_name='arena',
            name='players',
            field=models.ManyToManyField(through='smashbotspain.ArenaPlayer', to='smashbotspain.Player'),
        ),
        migrations.AddField(
            model_name='arena',
            name='tier',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='smashbotspain.tier'),
        ),
    ]
