# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-09-22 18:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0017_auto_20160920_1938'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='timezone',
            field=models.CharField(default=b'America/New_York', max_length=32),
        ),
    ]