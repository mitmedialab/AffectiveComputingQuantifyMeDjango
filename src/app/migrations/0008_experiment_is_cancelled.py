# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-26 15:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_auto_20160720_2155'),
    ]

    operations = [
        migrations.AddField(
            model_name='experiment',
            name='is_cancelled',
            field=models.BooleanField(default=False),
        ),
    ]
