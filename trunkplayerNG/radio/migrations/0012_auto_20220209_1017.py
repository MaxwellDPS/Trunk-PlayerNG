# Generated by Django 3.2.10 on 2022-02-09 18:17

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('radio', '0011_auto_20220208_1306'),
    ]

    operations = [
        migrations.AddField(
            model_name='talkgroupacl',
            name='downloadAllowed',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='systemreciverate',
            name='time',
            field=models.DateTimeField(default=datetime.datetime(2022, 2, 9, 10, 17, 23, 368699)),
        ),
    ]
