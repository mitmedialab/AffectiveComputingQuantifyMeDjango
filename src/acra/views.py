from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.db.models import Count
from django.db import connection
from django.contrib.auth.decorators import login_required

import simplejson

from acra.models import CrashReport
from acra.decorators import http_basic_auth


# If there is no handling of the CSRF Token
@csrf_exempt
@http_basic_auth
@login_required
def report(request):

    if request.method == "PUT" or request.method == "POST":

        json_data = simplejson.loads(request.body)

        notallow = ["description", "solved", ]
        crashreport = CrashReport()

        for key in json_data.keys():

            if not key.lower() in notallow:
                setattr(crashreport, key.lower(), json_data[key])

        crashreport.save()

    return HttpResponse(simplejson.dumps({"ok": "true"}), content_type="application/json")
