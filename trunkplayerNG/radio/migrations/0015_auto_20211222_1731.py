# Generated by Django 3.2.8 on 2021-12-23 01:31

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('radio', '0014_auto_20211218_1747'),
    ]

    operations = [
        migrations.AddField(
            model_name='system',
            name='enableTalkGroupACLs',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='systemreciverate',
            name='time',
            field=models.DateTimeField(default=datetime.datetime(2021, 12, 22, 17, 31, 24, 541235)),
        ),
    ]