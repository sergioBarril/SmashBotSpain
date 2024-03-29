# Generated by Django 3.1.6 on 2021-03-19 23:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0047_remove_player_name'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='regionrole',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='regionrole',
            name='guild',
        ),
        migrations.RemoveField(
            model_name='regionrole',
            name='region',
        ),
        migrations.RemoveField(
            model_name='arena',
            name='max_players',
        ),
        migrations.RemoveField(
            model_name='main',
            name='character_role',
        ),
        migrations.RemoveField(
            model_name='player',
            name='character_roles',
        ),
        migrations.RemoveField(
            model_name='player',
            name='region_roles',
        ),
        migrations.RemoveField(
            model_name='tier',
            name='name',
        ),
        migrations.AddField(
            model_name='character',
            name='discord_id',
            field=models.BigIntegerField(default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='character',
            name='guild',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.guild'),
        ),
        migrations.AddField(
            model_name='main',
            name='character',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.character'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='player',
            name='characters',
            field=models.ManyToManyField(blank=True, through='smashbotspain.Main', to='smashbotspain.Character'),
        ),
        migrations.AddField(
            model_name='player',
            name='regions',
            field=models.ManyToManyField(blank=True, to='smashbotspain.Region'),
        ),
        migrations.AddField(
            model_name='region',
            name='discord_id',
            field=models.BigIntegerField(default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='region',
            name='guild',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='smashbotspain.guild'),
        ),
        migrations.AlterUniqueTogether(
            name='character',
            unique_together={('discord_id',)},
        ),
        migrations.AlterUniqueTogether(
            name='region',
            unique_together={('discord_id',)},
        ),
        migrations.DeleteModel(
            name='CharacterRole',
        ),
        migrations.DeleteModel(
            name='RegionRole',
        ),
        migrations.RemoveField(
            model_name='character',
            name='emoji',
        ),
        migrations.RemoveField(
            model_name='character',
            name='name',
        ),
        migrations.RemoveField(
            model_name='region',
            name='emoji',
        ),
        migrations.RemoveField(
            model_name='region',
            name='name',
        ),
    ]
