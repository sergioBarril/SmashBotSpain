# Generated by Django 3.1.6 on 2021-03-16 02:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smashbotspain', '0043_auto_20210316_0335'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='characterrole',
            unique_together={('character', 'guild')},
        ),
        migrations.AlterUniqueTogether(
            name='regionrole',
            unique_together={('region', 'guild')},
        ),
    ]
