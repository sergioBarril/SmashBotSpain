# Generated by Django 3.1.6 on 2021-03-14 03:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0039_auto_20210314_0322'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='name',
            field=models.CharField(blank=True, max_length=90, null=True),
        ),
    ]
