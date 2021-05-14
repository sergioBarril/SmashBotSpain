# Generated by Django 3.1.6 on 2021-04-06 22:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0053_auto_20210325_2324'),
    ]

    operations = [
        migrations.CreateModel(
            name='Game',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage', models.CharField(blank=True, max_length=50, null=True)),
                ('winner_character', models.CharField(blank=True, max_length=50, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='GameSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('win_condition', models.CharField(choices=[('BO3', 'BO3'), ('BO5', 'BO5'), ('FT5', 'FT5'), ('FT10', 'FT10')], max_length=40)),
                ('guild', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.guild')),
                ('players', models.ManyToManyField(to='smashbotspain.Player')),
                ('winner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='winner_set', to='smashbotspain.player')),
            ],
        ),
        migrations.CreateModel(
            name='GamePlayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('character', models.CharField(blank=True, max_length=50, null=True)),
                ('winner', models.BooleanField(null=True)),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.game')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.player')),
            ],
        ),
        migrations.AddField(
            model_name='game',
            name='game_set',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.gameset'),
        ),
        migrations.AddField(
            model_name='game',
            name='guild',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.guild'),
        ),
        migrations.AddField(
            model_name='game',
            name='players',
            field=models.ManyToManyField(through='smashbotspain.GamePlayer', to='smashbotspain.Player'),
        ),
        migrations.AddField(
            model_name='game',
            name='winner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='winner_game', to='smashbotspain.player'),
        ),
    ]