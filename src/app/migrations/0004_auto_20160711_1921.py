# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-11 19:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_auto_20160711_1919'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='happy',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='user',
            name='sleep_quality',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='user',
            name='stress',
            field=models.IntegerField(default=0),
        ),
    ]