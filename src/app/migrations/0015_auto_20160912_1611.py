# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-09-12 16:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0014_checkin_result_day'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='checkin',
            name='result_day',
        ),
        migrations.RemoveField(
            model_name='checkin',
            name='result_instructions',
        ),
        migrations.RemoveField(
            model_name='checkin',
            name='result_status',
        ),
        migrations.AddField(
            model_name='checkin',
            name='result',
            field=models.TextField(default='{}'),
            preserve_default=False,
        ),
    ]
