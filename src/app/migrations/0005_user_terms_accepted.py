# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-11 19:33
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_auto_20160711_1921'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='terms_accepted',
            field=models.BooleanField(default=False),
        ),
    ]
