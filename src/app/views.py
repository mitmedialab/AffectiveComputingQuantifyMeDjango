import simplejson, pytz, StringIO
import datetime, random, math
from decimal import Decimal
from dateutil.parser import parse as parse_date

from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from functools import wraps
from django.shortcuts import render

from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .decorators import app_view
from django.conf import settings
from django import forms

from models import User, races, genders, Experiment, Checkin

import jawbone

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

def json_response(**kwargs):
    return HttpResponse(simplejson.dumps(kwargs))

def context(**extra):
    return dict(**extra)

@app_view
def app_test(request):
    return json_response(success=True)


def test(request):
    return HttpResponse("Success!")


def test_error(request):
    raise simplejson.JSONDecodeError
    return HttpResponse()


def render_to(template):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            out = func(request, *args, **kwargs)
            if isinstance(out, dict):
                out = render(request, template, out)
            return out
        return wrapper
    return decorator


##############################################
# Add your views here!


@render_to('app/index.html')
def index(request):
    return context(test=True)


class UserDataForm(forms.Form):
    jawbone_access = forms.CharField(required=True)
    jawbone_reset = forms.CharField(required=True)
    date_of_birth = forms.DateField(required=True, input_formats=('%Y-%m-%d',))
    race = forms.ChoiceField(required=True, choices=races)
    gender = forms.ChoiceField(required=True, choices=genders)
    happy = forms.IntegerField(required=True)
    stress = forms.IntegerField(required=True)
    activity = forms.CharField(required=True)
    sleep_quality = forms.IntegerField(required=True)
    timezone = forms.CharField(required=True)


@app_view
@api_view(['POST'])
@permission_classes((IsAuthenticated,))
def set_user_data(request):

    form = UserDataForm(request.POST)

    success = False

    had_user_data = request.user.terms_accepted

    if form.is_valid():
        data = form.cleaned_data

        user = request.user

        user.terms_accepted = True
        user.jawbone_access_token = data.get('jawbone_access')
        user.jawbone_reset_token = data.get('jawbone_reset')
        user.date_of_birth = data.get('date_of_birth')
        user.race = data.get('race')
        user.gender = data.get('gender')
        user.happy = data.get('happy')
        user.stress = data.get('stress')
        user.activity = data.get('activity')
        user.sleep_quality = data.get('sleep_quality')
        user.timezone = data.get('timezone')

        user.jawbone_user_id = jawbone.get_user_id(user)

        user.save()

        success = True

    return json_response(success=success, had_user_data=had_user_data)



class StartExperimentForm(forms.Form):
    type = forms.CharField(required=True)
    self_efficacy = forms.IntegerField(required=True)
    app_efficacy = forms.IntegerField(required=True)
    experiment_efficacy = forms.IntegerField(required=True)


@app_view
@api_view(['POST'])
@permission_classes((IsAuthenticated,))
def start_experiment(request):

    form = StartExperimentForm(request.POST)

    if form.is_valid():
        data = form.cleaned_data

        experiment = Experiment()
        experiment.experiment_type = data.get("type")
        experiment.user = request.user
        experiment.init()
        experiment.self_efficacy = data["self_efficacy"]
        experiment.app_efficacy = data["app_efficacy"]
        experiment.experiment_efficacy = data["experiment_efficacy"]

        experiment.save()

        return json_response(success=True, key=experiment.key)

    return json_response(success=False)


class ExperimentCheckinForm(forms.Form):
    experiment_key = forms.CharField(required=True)
    did_follow_instructions = forms.IntegerField(required=True)
    happy = forms.IntegerField(required=True)
    stress = forms.IntegerField(required=True)
    productivity = forms.IntegerField(required=True)
    leisure_time = forms.IntegerField(required=True)
    app_version = forms.CharField(required=False)


@app_view
@api_view(['POST'])
@permission_classes((IsAuthenticated,))
def experiment_checkin(request):

    form = ExperimentCheckinForm(request.POST)

    if form.is_valid():
        data = form.cleaned_data

        experiment = Experiment.objects.get(key=data.get("experiment_key"))

        checkin = Checkin()
        checkin.experiment = experiment
        checkin.checkin_time = timezone.now()
        checkin.did_follow_instructions = data.get("did_follow_instructions")
        checkin.happiness = data.get("happy")
        checkin.stress = data.get("stress")
        checkin.productivity = data.get("productivity")
        checkin.leisure_time = data.get("leisure_time")
        checkin.app_version = data.get("app_version", "")

        day = (checkin.checkin_time.date() - experiment.start_time.date()).days + 1

        checkin.save()

        result = dict(day=day)

        should_end, ended_early, restarted_stage = experiment.should_end_stage()

        if restarted_stage:
            result['restarted_stage'] = restarted_stage
            experiment.save()

        if should_end:
            result['new_stage'] = True
            result['ended_early'] = ended_early
            experiment.end_stage()
            experiment.save()

        inputs, outputs = experiment.get_stage_data(experiment.current_stage, always_get_median=True)
        result['stage_inputs'] = inputs
        result['stage_outputs'] = outputs
        result['target'] = experiment.get_daily_target(experiment.current_stage, len(result['stage_inputs']) - 1)
        result['current_stage'] = experiment.current_stage

        if not experiment.is_active:
            experiment.calculate_results()
            experiment.save()
            result['is_complete'] = True
            result['result_value'] = experiment.result_value
            result['result_confidence'] = experiment.result_confidence
            result['stage_results'] = experiment.stage_results

        return json_response(success=True, key=experiment.key, result=result)

    return json_response(success=False)


@app_view
@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def refresh_instructions(request):
    experiment = Experiment.objects.get(key=request.GET.get("experiment_key"))
    inputs, outputs = experiment.get_stage_data(experiment.current_stage, always_get_median=True)
    result = dict()
    result['stage_inputs'] = inputs
    result['stage_outputs'] = outputs
    result['target'] = experiment.get_daily_target(experiment.current_stage, len(result['stage_inputs']) - 1)
    result['current_stage'] = experiment.current_stage
    return json_response(success=True, key=experiment.key, result=result)


@app_view
@api_view(['POST'])
@permission_classes((IsAuthenticated,))
def cancel_experiment(request):

    experiment_key = request.POST.get("experiment_key")
    reason = request.POST.get("reason")
    experiment = Experiment.objects.get(key=experiment_key, user=request.user)

    if experiment.is_active:
        experiment.is_active = False
        experiment.is_cancelled = True
        experiment.end_time = timezone.now()
        experiment.cancel_reason = reason
        experiment.save()

    return _get_experiments_internal(request)


@app_view
@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def get_experiments(request):
    return _get_experiments_internal(request)


def _get_experiments_internal(request):
    experiments = Experiment.objects.filter(user=request.user).order_by('-start_time')

    experiments_json = [experiment.to_dict() for experiment in experiments]

    return json_response(success=True, experiments=experiments_json)


@csrf_exempt
def jawbone_webhook(request):
    data = simplejson.loads(request.body)
    for event in data.get("events", []):
        action = event.get("action")
        event_type = event.get("type")
        user_id = event.get("user_xid")
        user = User.objects.get(jawbone_user_id=user_id)
        if event_type == "workout":
            jawbone.update_jawbone_workouts(user)
        elif event_type == "move":
            jawbone.update_jawbone_moves(user)
        elif event_type == "sleep" or action == "exit_sleep_mode" or action == "enter_sleep_mode":
            jawbone.update_jawbone_sleep(user)
    return HttpResponse()


def update_jawbone(request):
    jawbone.update_jawbone_all(request.user)
    return HttpResponse("Got it, boss!")
