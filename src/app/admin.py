from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django import forms

import fields, csv, zipfile, os, uuid, errno, datetime
import simplejson, pytz
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect

from django.contrib.admin.widgets import AdminTextareaWidget, AdminTextInputWidget
from django.template.loader import render_to_string

from django.utils.translation import ugettext_lazy as _

from django.db.models import Count, Case, When, IntegerField, Sum
from django.conf import settings
from django import utils

from .models import User, Experiment, JawboneMeasurement, Checkin


def register(model):
    def inner(admin_class):
        admin.site.register(model,admin_class)
        return admin_class

    return inner

def export_users_csv(modeladmin,request, queryset):
    import csv
    from django.utils.encoding import smart_str
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=UserData.csv'
    writer = csv.writer(response, csv.excel)
    response.write(u'\ufeff'.encode('utf8')) # BOM (optional...Excel needs it to open UTF-8 file properly)
    writer.writerow([
        smart_str(u"ID"),
        smart_str(u"User"),
        smart_str(u"JawboneAccessToken"),
        smart_str(u"JawboneResetToken"),
        smart_str(u"JawboneUserID"),
        smart_str(u"DateOfBirth"),
        smart_str(u"Race"),
        smart_str(u"Gender"),
        smart_str(u"Happy"),
        smart_str(u"Stress"),
        smart_str(u"Activity"),
        smart_str(u"SleepQuality"),
        smart_str(u"Timezone"),
        
    ])
    for obj in queryset:
        writer.writerow([
            smart_str(obj.pk),
            smart_str(obj.username),
            smart_str(obj.jawbone_access_token),
            smart_str(obj.jawbone_reset_token),
            smart_str(obj.jawbone_user_id),
            smart_str(obj.date_of_birth),
            smart_str(obj.race),
            smart_str(obj.gender),
            smart_str(obj.happy),
            smart_str(obj.stress),
            smart_str(obj.activity),
            smart_str(obj.sleep_quality),
            smart_str(obj.timezone)
        ])
    return response
export_users_csv.short_description = u"Export to CSV"


@register(User)
class UserAdmin(auth_admin.UserAdmin):
    list_display = auth_admin.UserAdmin.list_display

    fieldsets = auth_admin.UserAdmin.fieldsets + (
        (_('User Data'), {'fields': ('terms_accepted',
                                     'jawbone_access_token',
                                     'jawbone_reset_token',
                                     'jawbone_user_id',
                                     'date_of_birth',
                                     'race',
                                     'gender',
                                     'happy',
                                     'stress',
                                     'activity',
                                     'sleep_quality',
                                     'timezone')}),
    )
    actions = [export_users_csv]


class SerializedFieldWidget(AdminTextareaWidget):

    def render(self, name, value, attrs=None):
        return super(SerializedFieldWidget, self).render(name, simplejson.dumps(value, indent=4), attrs)

class DateTimeEncoder(simplejson.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        if isinstance(o, datetime.date):
            return o.isoformat()

        return simplejson.JSONEncoder.default(self, o)

def export_experiments_csv(modeladmin,request, queryset):
    import csv
    from django.utils.encoding import smart_str
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=ExperimentData.csv'
    writer = csv.writer(response, csv.excel)
    response.write(u'\ufeff'.encode('utf8')) # BOM (optional...Excel needs it to open UTF-8 file properly)
    writer.writerow([
        smart_str(u"ID"),
        smart_str(u"User"),
        smart_str(u"Key"),
        smart_str(u"ExperimentType"),
        smart_str(u"StartTime"),
        smart_str(u"EndTime"),
        smart_str(u"SelfEfficacy"),
        smart_str(u"AppEfficacy"),
        smart_str(u"ExperientEfficacy"),
        smart_str(u"IsActive"),
        smart_str(u"IsCancelled"),
        smart_str(u"CancelReason"),
        smart_str(u"InitialStageAverage"),
        smart_str(u"StageDates"),
        smart_str(u"StageTargetValues"),
        smart_str(u"StageRestartCount"),
        smart_str(u"CurrentStage"),
        smart_str(u"ResultValue"),
        smart_str(u"ResultConfidence"),
        smart_str(u"StageResults"),
    ])
    for obj in queryset:
        writer.writerow([
            smart_str(obj.pk),
            smart_str(obj.user),
            smart_str(obj.key),
            smart_str(obj.experiment_type),
            smart_str(obj.start_time),
            smart_str(obj.end_time),
            smart_str(obj.self_efficacy),
            smart_str(obj.app_efficacy),
            smart_str(obj.experiment_efficacy),
            smart_str(obj.is_active),
            smart_str(obj.is_cancelled),
            smart_str(obj.cancel_reason),
            smart_str(obj.initial_stage_average),
            smart_str(obj.stage_dates),
            smart_str(obj.stage_target_values),
            smart_str(obj.stage_restart_count),
            smart_str(obj.current_stage),
            smart_str(obj.result_value),
            smart_str(obj.result_confidence),
            smart_str(obj.stage_results),
        ])
    return response
export_experiments_csv.short_description = u"Export to CSV"


@register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    actions = ('download_json',)
    list_display = ('user', 'experiment_type', 'start_time', 'end_time', 'is_active', 'is_cancelled')
    list_filter = ('user',)
    # actions = [export_experiments_csv]

    def download_json(self, request, experiments):

        today = datetime.date.today()

        data = [dict(user=experiment.user.username,
                     stage_data=[experiment.get_stage_data(stage, False) for stage in range(0, 4)],
                     all_data=experiment.get_all_data(),
                     stage_targets=experiment.get_stage_targets(),
                     stage_dates=simplejson.loads(experiment.stage_dates),
                     **experiment.to_dict()) for experiment in experiments if experiment.get_experiment_type()]

        response = HttpResponse(simplejson.dumps(data, cls=DateTimeEncoder, indent=2), content_type='text/json')
        response['Content-Disposition'] = 'attachment; filename=experiments.json'
        return response
    download_json.short_description = "Download JSON file for selected experiments."


@register(Checkin)
class CheckinAdmin(admin.ModelAdmin):
    list_display = ('user', 'experiment', 'checkin_time', 'did_follow_instructions', 'happiness', 'stress', 'productivity', 'leisure_time', 'app_version')
    list_filter = ('experiment',)
    list_select_related = (
            'experiment__user',
        )

    def user(self, obj):
        return obj.experiment.user

    def export_checkins_csv(modeladmin, request, queryset):
        import csv
        from django.utils.encoding import smart_str
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=CheckinData.csv'
        writer = csv.writer(response, csv.excel)
        response.write(u'\ufeff'.encode('utf8'))  # BOM (optional...Excel needs it to open UTF-8 file properly)
        writer.writerow([
            smart_str(u"ID"),
            smart_str(u"Key"),
            smart_str(u"ExperimentKey"),
            smart_str(u"CheckinTime"),
            smart_str(u"DidFollowInstructions"),
            smart_str(u"Happiness"),
            smart_str(u"Stress"),
            smart_str(u"Productivity"),
            smart_str(u"LeisureTime"),
            smart_str(u"AppVersion"),
        ])
        for obj in queryset:
            writer.writerow([
                smart_str(obj.pk),
                smart_str(obj.key),
                smart_str(obj.experiment),
                smart_str(obj.checkin_time),
                smart_str(obj.did_follow_instructions),
                smart_str(obj.happiness),
                smart_str(obj.stress),
                smart_str(obj.productivity),
                smart_str(obj.leisure_time),
                smart_str(obj.app_version),
            ])
        return response
    export_checkins_csv.short_description = u"Export to CSV"

    actions=[export_checkins_csv]

def export_jawbone_measurements_csv(modeladmin,request, queryset):
    import csv
    from django.utils.encoding import smart_str
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=JawboneMeasurementData.csv'
    writer = csv.writer(response, csv.excel)
    response.write(u'\ufeff'.encode('utf8')) # BOM (optional...Excel needs it to open UTF-8 file properly)
    writer.writerow([
        smart_str(u"ID"),
        smart_str(u"User"),
        smart_str(u"Type"),
        smart_str(u"StartTime"),
        smart_str(u"EndTime"),
        smart_str(u"JawboneID"),
        smart_str(u"JawboneTimezone"),
        smart_str(u"JawboneDateString"),
        smart_str(u"Latitude"),
        smart_str(u"Longitude"),
        smart_str(u"Duration"),
        smart_str(u"Steps"),
        smart_str(u"Distance"),
        smart_str(u"AwakeTime"),
        smart_str(u"RawJawboneObject"),
    ])
    for obj in queryset:
        writer.writerow([
            smart_str(obj.pk),
            smart_str(obj.user),
            smart_str(obj.type),
            smart_str(obj.start_time),
            smart_str(obj.end_time),
            smart_str(obj.jawbone_id),
            smart_str(obj.jawbone_timezone),
            smart_str(obj.jawbone_datestring),
            smart_str(obj.latitude),
            smart_str(obj.longitude),
            smart_str(obj.duration),
            smart_str(obj.steps),
            smart_str(obj.distance),
            smart_str(obj.awake_time),
            smart_str(obj.raw_jawbone_object),
        ])
    return response
export_jawbone_measurements_csv.short_description = u"Export to CSV"


@register(JawboneMeasurement)
class JawboneMeasurementAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'jawbone_id', 'start_time', 'end_time', 'duration')
    list_filter = ('user',)
    actions = [export_jawbone_measurements_csv]



