# Generated by Django 3.2.8 on 2021-12-30 03:08

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('radio', '0004_auto_20211228_1835'),
    ]

    operations = [
        migrations.AlterField(
            model_name='incident',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='systemreciverate',
            name='time',
            field=models.DateTimeField(default=datetime.datetime(2021, 12, 29, 19, 8, 13, 310743)),
        ),
    ]