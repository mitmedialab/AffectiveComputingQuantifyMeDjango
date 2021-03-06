# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-10-14 19:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0021_auto_20161012_1455'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='experiment',
            name='stage_start_dates',
        ),
        migrations.AddField(
            model_name='experiment',
            name='cancel_reason',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='experiment',
            name='stage_dates',
            field=models.TextField(default=b'[null, null, null, null]'),
        ),
        migrations.AddField(
            model_name='experiment',
            name='stage_restart_count',
            field=models.TextField(default=b'[0, 0, 0, 0]'),
        ),
        migrations.AlterField(
            model_name='experiment',
            name='stage_target_values',
            field=models.TextField(default=b'[null, null, null, null]'),
        ),
    ]
