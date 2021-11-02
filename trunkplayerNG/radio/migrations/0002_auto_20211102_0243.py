# Generated by Django 3.2.8 on 2021-11-02 02:43

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('radio', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='talkgroupacl',
            old_name='defualtNewTalkgroups',
            new_name='defaultNewTalkgroups',
        ),
        migrations.RenameField(
            model_name='talkgroupacl',
            old_name='defualtNewUsers',
            new_name='defaultNewUsers',
        ),
        migrations.RemoveField(
            model_name='talkgroup',
            name='commonName',
        ),
        migrations.AddField(
            model_name='systemforwarder',
            name='enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='systemreciverate',
            name='time',
            field=models.DateTimeField(default=datetime.datetime(2021, 11, 2, 2, 43, 54, 300951)),
        ),
        migrations.AlterField(
            model_name='transmission',
            name='units',
            field=models.ManyToManyField(to='radio.TransmissionUnit'),
        ),
    ]