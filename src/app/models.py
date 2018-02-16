from django.core.files.storage import FileSystemStorage
from django.db import models
from django.contrib.auth import models as auth_models
from django.db.models import Q, Sum

import dateutil.parser
import string, random, os, math, datetime, pytz, simplejson
import analysis
from analysis import mean

from .fields import SerializedDataField

from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings


def key_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class BaseModel(models.Model):
    '''
    Base model from which all other models should inherit. It has a unique key and other nice fields
    '''
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=10, unique=True, db_index=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def generate_key(self, length=10):
        if not self.key:
            for _ in range(10):
                key = key_generator(length)
                if not type(self).objects.filter(key=key).count():
                    self.key = key
                    break

    def save(self, *args, **kwargs):
        self.generate_key()
        super(BaseModel, self).save(*args, **kwargs)

    class Meta:
        abstract = True


class UserBackend(object):

    def authenticate(self, email=None, uuid=None):
        try:
            user = User.objects.get(email=email)

            if user.email != email:
                return None

        except User.DoesNotExist:
            user = User(email=email, username=email)
            user.save()
        except User.MultipleObjectsReturned:
            return None

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


def fix_email(cls):
    '''
    the Django User object by default doesn't use the email address for auth, so it's not required or unique. This is weird.
    We want to use email, not username. So let's modify the default email address since we can't overwrite it.
    '''
    field = cls._meta.get_field('email')
    field.required = True
    field.blank = False
    field._unique = True
    field.db_index = True

    return cls


class OverwriteStorage(FileSystemStorage):

    def get_available_name(self, name):

        # If the filename already exists, remove it as if it was a true file system
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name



##########################################################################################
# Put your classes after this line! Feel free to add fields to the User class too!



races = (("nativeamerican", "American Indian or Alaska Native"),
         ("hawaiian", "Hawaiian or Other Pacific Islander"),
         ("asian", "Asian or Asian American"),
         ("black", "Black or African American"),
         ("latino", "Hispanic or Latino"),
         ("white", "Non-Hispanic White"),
         ("other", "Other"),
         )


genders = (("m", "Male"), ("f", "Female"))


@fix_email
class User(auth_models.AbstractUser, BaseModel):
    terms_accepted = models.BooleanField(blank=True, default=False)
    jawbone_access_token = models.CharField(max_length=256, blank=True)
    jawbone_reset_token = models.CharField(max_length=256, blank=True)
    jawbone_user_id = models.CharField(max_length=256, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    race = models.CharField(max_length=16, choices=races)
    gender = models.CharField(max_length=1, choices=genders)
    happy = models.IntegerField(default=0)
    stress = models.IntegerField(default=0)
    activity = models.CharField(max_length=32, blank=True)
    sleep_quality = models.IntegerField(default=0)
    timezone = models.CharField(max_length=32, default="America/New_York")



NUM_STAGES = 3


class Experiment(BaseModel):
    experiment_type = models.CharField(max_length=32)
    user = models.ForeignKey(User, related_name="experiments")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=False, blank=True)
    is_cancelled = models.BooleanField(default=False, blank=True)
    cancel_reason = models.TextField()

    initial_stage_average = models.IntegerField(blank=True, null=True, default=None)

    result_value = models.FloatField(default=0)
    result_confidence = models.FloatField(default=0)
    stage_results = models.TextField(default="{}")

    stage_dates = models.TextField(default=simplejson.dumps([None for _ in xrange(NUM_STAGES + 1)]))  # json'ed list of date tuples
    stage_target_values = models.TextField(default=simplejson.dumps([None for _ in xrange(NUM_STAGES + 1)]))  # json'ed list of floats
    stage_restart_count = models.TextField(default=simplejson.dumps([0 for _ in xrange(NUM_STAGES + 1)]))  # json'ed list of floats

    current_stage = models.IntegerField(default=0)

    self_efficacy = models.IntegerField()
    app_efficacy = models.IntegerField()
    experiment_efficacy = models.IntegerField()

    def init(self):
        start = self.localize(timezone.now()).date()
        self.set_stage_dates(0, start, start + datetime.timedelta(days=7))
        self.start_time = timezone.now()
        self.is_active = True

    def localize(self, dt):
        return dt.astimezone(pytz.timezone(self.user.timezone))

    def get_experiment_type(self):
        return analysis.EXPERIMENT_TYPES.get(self.experiment_type)

    def get_jawbone_events(self, type_name, start_date, end_date):
        start_time = datetime.datetime.combine(start_date, datetime.time.min).replace(tzinfo=pytz.UTC)
        end_time = datetime.datetime.combine(end_date, datetime.time.min).replace(tzinfo=pytz.UTC)
        return JawboneMeasurement.objects.filter(user=self.user).order_by("start_time").filter(type=type_name, end_time__gte=start_time, start_time__lt=end_time)

    def get_stage_targets(self):
        return simplejson.loads(self.stage_target_values)

    def get_stage_target(self, stage):
        targets = self.get_stage_targets()
        if stage >= len(targets):
            return None
        return targets[stage]

    def get_daily_target(self, stage, day_in_stage):
        use_variability = self.get_experiment_type().use_variability() if self.get_experiment_type() else False

        stage_target = self.get_stage_target(stage)
        if not use_variability or stage_target is None:
            # normally, we just want to return the target value for the stage
            return stage_target

        # but if we're doing a variability study, we want to return a number that rotates around the base average, according
        # to the variability value of the stage
        base_target = self.initial_stage_average
        if day_in_stage % 2:
            return base_target + stage_target
        else:
            return base_target - stage_target


    def set_stage_targets(self, initial_stage_inputs):

        use_variability = self.get_experiment_type().use_variability() if self.get_experiment_type() else False
        initial_stage_inputs = [i for i in initial_stage_inputs if i is not None]
        ranges = self.get_experiment_type().get_ranges()
        range_size = self.get_experiment_type().get_range_size()
        average = self.get_experiment_type().calculate_input_average(initial_stage_inputs)
        variability = max(initial_stage_inputs) - min(initial_stage_inputs)

        target_value = variability if use_variability else average

        if target_value <= ranges["under"]:
            targets = ("under", "N1", "N3", "N2")
        elif target_value <= ranges["N1"] + range_size:
            targets = ("N1", "N3", "N1", "N2")
        elif target_value <= ranges["N2"] + range_size:
            targets = ("N2", "N3", "N1", "N2")
        elif target_value <= ranges["N3"] + range_size:
            targets = ("N3", "N1", "N3", "N2")
        else:
            targets = ("over", "N3", "N1", "N2")

        self.stage_target_values = simplejson.dumps([ranges.get(v) for v in targets])
        self.initial_stage_average = average

    def set_stage_dates(self, stage, start, end):
        dates = simplejson.loads(self.stage_dates)
        dates[stage] = (start.isoformat(), end.isoformat())
        self.stage_dates = simplejson.dumps(dates)

    def get_stage_dates(self, stage, today=None):
        dates = simplejson.loads(self.stage_dates)
        if stage >= len(dates):
            now = self.localize(self.end_time).date()
            return (now, now) if self.end_time else (None, None)
        if dates[stage]:
            start = dateutil.parser.parse(dates[stage][0]).date()
            end = dateutil.parser.parse(dates[stage][1]).date()
            if today:
                end = min(end, today)

            return start, end
        return None, None

    def end_stage(self):
        if self.current_stage == 0:
            stage_inputs = self.get_stage_inputs(0, True)
            self.set_stage_targets(stage_inputs)

        self.current_stage = self.current_stage + 1

        if self.current_stage > NUM_STAGES:
            self.is_active = False
            self.end_time = timezone.now()
        else:
            start = self.localize(timezone.now()).date()
            self.set_stage_dates(self.current_stage, start, start + datetime.timedelta(days=7))

    def restart_current_stage(self):
        stage = self.current_stage
        stage_restart_counts = simplejson.loads(self.stage_restart_count)
        stage_restart_counts[stage] += 1
        self.stage_restart_count = simplejson.dumps(stage_restart_counts)
        start = self.localize(timezone.now()).date()
        self.set_stage_dates(stage, start, start + datetime.timedelta(7))

    def should_end_stage(self):
        '''

        :return: should_end, ended_early, restarted_stage
        '''

        stage_start, stage_end = self.get_stage_dates(self.current_stage)
        today = self.localize(timezone.now()).date()
        stage_day = (today - stage_start).days

        missed_days = self.get_num_missed_days()
        valid_days = len(self.get_valid_days(self.current_stage))
        is_output_stable = self.is_output_stable()

        # print self.current_stage, stage_start, today, stage_day, missed_days, valid_days, is_output_stable

        if (self.current_stage > 0 and missed_days >= 2) or (self.current_stage == 0 and missed_days > 2):
            # not enough valid days, kill the stage
            self.restart_current_stage()
            return False, True, True

        if self.current_stage > 0:
            if valid_days >= 5 and is_output_stable:
                # end early! we have enough valid days!
                return True, True, False

            if stage_day >= 4:
                days_left = 7 - stage_day
                possible_valid_days = valid_days + days_left
                if possible_valid_days < 4:
                    # not enough valid days, kill the stage
                    self.restart_current_stage()
                    return False, True, True

        if stage_day == 7:
            # we have enough valid days, but we're not ending early. We're ending on time.
            return True, False, False

        # continue the stage
        return False, False, False

    def is_output_stable(self):
        if self.current_stage == 0:
            return False  # the test stage should never cut out early due to stable data
        outputs = self.get_stage_outputs(self.current_stage)
        relevant_outputs = [x for x in outputs if x is not None][-5:]
        if not relevant_outputs:
            return False
        return max(relevant_outputs) - min(relevant_outputs) <= self.get_experiment_type().get_stable_range()

    def get_valid_days(self, stage):
        # valid if output is within target, and we have both input and output
        inputs, outputs = self.get_stage_data(stage)
        data = zip(inputs, outputs)
        target = self.get_stage_target(stage)
        stage_range = self.get_experiment_type().get_range_size()
        if target is None:
            return [(i, o) for i, o in data if i is not None and o is not None]
        return [(i, o) for i, o in data if i is not None and o is not None and target - stage_range <= i <= target + stage_range]

    def get_num_missed_days(self):
        # missed if we don't have input or output
        inputs, outputs = self.get_stage_data(self.current_stage)
        data = zip(inputs, outputs)
        return sum([1 for i, o in data if i is None or o is None])

    def get_stage_inputs(self, stage, always_get_median=False):

        use_variability = self.get_experiment_type().use_variability() if self.get_experiment_type() else False
        use_variability = False if always_get_median else use_variability

        experiment_type = self.get_experiment_type()
        today = self.localize(timezone.now()).date()
        start_date, end_date = self.get_stage_dates(stage, today=today)
        return experiment_type.get_inputs(self, start_date, end_date, use_variability)

    def get_stage_outputs(self, stage):
        experiment_type = self.get_experiment_type()
        today = self.localize(timezone.now()).date()
        start_date, end_date = self.get_stage_dates(stage, today=today)
        return experiment_type.get_outputs(self, start_date, end_date)

    def get_stage_data(self, stage, always_get_median=False):

        use_variability = self.get_experiment_type().use_variability() if self.get_experiment_type() else False
        use_variability = False if always_get_median else use_variability

        experiment_type = self.get_experiment_type()
        today = self.localize(timezone.now()).date()
        start_date, end_date = self.get_stage_dates(stage, today=today)
        if not start_date:
            return [], []
        inputs = experiment_type.get_inputs(self, start_date, end_date, use_variability)
        outputs = experiment_type.get_outputs(self, start_date, end_date)
        return inputs, outputs

    def get_all_data(self):
        experiment_type = self.get_experiment_type()
        today = self.localize(timezone.now()).date()
        start_date = self.localize(self.start_time).date()
        end_date = self.localize(self.end_time).date() if self.end_time else today
        if not start_date:
            return [], []
        dates = [start_date + datetime.timedelta(days=d) for d in range((end_date-start_date).days)]
        inputs = experiment_type.get_inputs(self, start_date, end_date, False)
        outputs = experiment_type.get_outputs(self, start_date, end_date)
        return dict(inputs=zip(dates, inputs), outputs=zip(dates, outputs))


    def calculate_results(self):

        want_minimized_results = self.get_experiment_type().should_minimize_result()

        targets = self.get_stage_targets()

        stage_results = [None]  # we don't care about the first stage, just null it out
        best_stage = 0
        best_output = 500000 if want_minimized_results else -500000  # HACK
        for stage in xrange(1, NUM_STAGES + 1):
            valid_days = self.get_valid_days(stage)
            inputs, outputs = zip(*valid_days)

            target = targets[stage]
            mean = float(sum(outputs)) / len(outputs)
            min_output = min(outputs)
            max_output = max(outputs)

            if (mean > best_output and not want_minimized_results) or (want_minimized_results and mean < best_output):
                best_output = mean
                best_stage = stage


            stage_results.append(dict(stage=stage, input=target, output=mean, min=min_output, max=max_output, inputs=inputs, values=outputs))

        # now we calculate confidence. which is the number of output values in the winning stage that are above any
        # other value in any other stage, divided by the number of values we have in the winning stage total

        # find the maximum value not in the winning stage
        max_overlap = 50000 if want_minimized_results else -50000  # HAX
        for stage in xrange(1, NUM_STAGES + 1):
            if stage == best_stage:
                # don't want our best stage
                continue
            if want_minimized_results:
                overlap = float(len([1 for val in stage_results[stage]['values'] if val <= stage_results[best_stage]['max']])) / len(stage_results[stage]['values'])
                max_overlap = min(max_overlap, overlap)
            else:
                overlap = float(len([1 for val in stage_results[stage]['values'] if val >= stage_results[best_stage]['min']])) / len(stage_results[stage]['values'])
                max_overlap = max(max_overlap, overlap)

        confidence = 1.0 - max_overlap
        confidence = round(confidence, 2)

        self.result_value = stage_results[best_stage]['input']
        self.result_confidence = min(confidence, .9)
        self.stage_results = simplejson.dumps(stage_results[1:])

    def to_dict(self):
        if self.end_time:
            days = (self.end_time.date() - self.start_time.date()).days + 1
        else:
            days = (timezone.now().date() - self.start_time.date()).days + 1

        return dict(key=self.key,
                    days=days,
                    result_value=self.result_value,
                    result_confidence=self.result_confidence,
                    type=self.experiment_type,
                    start_time=self.start_time.isoformat(),
                    end_time=self.end_time.isoformat() if self.end_time else None,
                    is_cancelled=self.is_cancelled,
                    is_active=self.is_active)

    def __unicode__(self):
        return self.key

class Checkin(BaseModel):
    experiment = models.ForeignKey(Experiment, related_name="checkins")
    checkin_time = models.DateTimeField()
    did_follow_instructions = models.IntegerField()
    happiness = models.IntegerField()
    stress = models.IntegerField()
    productivity = models.IntegerField()
    leisure_time = models.IntegerField()
    app_version = models.CharField(max_length=64, blank=True, default="")


class JawboneMeasurement(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User)
    type = models.CharField(max_length=32)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    jawbone_id = models.CharField(max_length=32, default="", blank=True)
    jawbone_timezone = models.CharField(max_length=32, default="", blank=True)
    jawbone_datestring = models.CharField(max_length=8, default="", blank=True)
    latitude = models.DecimalField(max_digits=12, decimal_places=9, default=0)
    longitude = models.DecimalField(max_digits=12, decimal_places=9, default=0)

    # this field is stored in seconds from jawbone's api
    duration = models.PositiveIntegerField(default=0)
    steps = models.PositiveIntegerField(default=0)
    distance = models.PositiveIntegerField(default=0)

    # obviously, only valid for sleep events
    awake_time = models.PositiveIntegerField(default=0)

    raw_jawbone_object = models.TextField()

    def set_data_from_event(self, event):

        self.type = event.type
        self.start_time = event.start_time
        self.end_time = event.end_time
        self.jawbone_id = event.jawbone_id
        self.jawbone_timezone = event.timezone
        self.jawbone_datestring = event.datestring
        self.latitude = event.latitude
        self.longitude = event.longitude
        self.duration = event.duration
        self.steps = event.steps
        self.distance = event.distance
        self.raw_jawbone_object = event.raw
        self.awake_time = event.awake_time


