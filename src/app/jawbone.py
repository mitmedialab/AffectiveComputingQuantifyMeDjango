import requests, datetime, pytz, simplejson
from decimal import Decimal
from django.db import transaction

from models import JawboneMeasurement


class JawboneEvent(object):

    def __init__(self, jawbone_object, activity_type):
        '''
        Convert Jawbone API's data into usable data.
        See https://jawbone.com/up/developer/types for details

        These are not JawboneMeasurements, which are saved to the database. These are meant to be lightweight
        and kept in memory only. To persist one of these, save it as a JawboneMeasurement
        '''
        details = jawbone_object.get("details", {})
        self.jawbone_id = jawbone_object.get("xid")
        self.timezone = details.get("tz", "")
        self.start_time = datetime.datetime.fromtimestamp(jawbone_object.get("time_created"))
        self.end_time = datetime.datetime.fromtimestamp(jawbone_object.get("time_completed"))
        self.latitude = Decimal(jawbone_object.get("place_lat") or "0")
        self.longitude = Decimal(jawbone_object.get("place_lon") or "0")
        self.datestring = jawbone_object.get("date", "")
        self.type = activity_type
        self.raw = simplejson.dumps(jawbone_object)
        self.steps = details.get("steps", 0)
        self.distance = details.get("distance", 0)
        self.awake_time = details.get("awake", 0)

        if activity_type == "workouts":
            self.duration = details.get("time", 0)
        elif activity_type == "sleeps":
            self.duration = details.get("duration", 0)
        elif activity_type == "moves":
            self.duration = details.get("active_time", 0)



def update_jawbone_workouts(user, date=None, access_token=None):
    items = _update_jawbone_data(user, "workouts", date, access_token)
    return items


def update_jawbone_moves(user, date=None, access_token=None):
    items = _update_jawbone_data(user, "moves", date, access_token)
    return items


def update_jawbone_sleep(user, date=None, access_token=None):
    items = _update_jawbone_data(user, "sleeps", date, access_token)
    return items


def update_jawbone_all(user, date=None):
    access_token = user.get_jawbone_access_token()
    if date is None:
        date = datetime.date.today()

    update_jawbone_sleep(user, date, access_token)
    update_jawbone_moves(user, date, access_token)
    # update_jawbone_workouts(user, date, access_token)


def _update_jawbone_data(user, activity_type, date=None, access_token=None):
    if date is None:
        date = datetime.date.today()

    if access_token is None:
        access_token = user.jawbone_access_token

    if not access_token:
        return

    # jawbone returns data in terms of local time for the user. what's today for us may be yesterday for them.
    # for safety sake, let's get every event today and yesterday and deal with all of them.
    # inefficient, but safe.
    yesterday = date - datetime.timedelta(days=1)
    items = _get_jawbone_items_for_day(activity_type, date, access_token) + \
           _get_jawbone_items_for_day(activity_type, yesterday, access_token)

    _save_jawbone_to_db(user, activity_type, items)

    return items



def _get_jawbone_items_for_day(activity_type, date, access_token):
    date_string = datetime.datetime.strftime(date, "%Y%m%d")

    get_params = {"date": date_string}
    headers = {"Accept": "application/json", "Authorization": "Bearer " + access_token}
    result = requests.get("https://jawbone.com/nudge/api/v.1.1/users/@me/" + activity_type, params=get_params, headers=headers)
    return _get_all_items_from_result(result.json(), activity_type)


def _get_all_items_from_result(data_object, activity_type):
    data = data_object.get("data", {})
    items = [JawboneEvent(item, activity_type) for item in data.get("items", [])]
    links = data.get("links", {})
    next_link = links.get("next")

    if next_link:
        result = requests.get(next_link)
        return items + _get_all_items_from_result(result.json(), activity_type)

    return items


def _save_jawbone_to_db(user, activity_type, items):
    items_by_id = {item.jawbone_id: item for item in items}
    preexisting_models = JawboneMeasurement.objects.filter(user=user, type=activity_type, jawbone_id__in=items_by_id.keys())

    used_keys = [a.jawbone_id for a in preexisting_models]

    with transaction.atomic():
        for measurement in preexisting_models:
            jawbone_object = items_by_id[measurement.jawbone_id]
            measurement.set_data_from_event(jawbone_object)
            measurement.save()

    new_measurements = []
    for key in set(items_by_id.keys()) - set(used_keys):
        jawbone_object = items_by_id[key]
        measurement = JawboneMeasurement(user=user)
        measurement.set_data_from_event(jawbone_object)
        new_measurements.append(measurement)

    JawboneMeasurement.objects.bulk_create(new_measurements)


def get_user_id(user):

    headers = {"Accept": "application/json", "Authorization": "Bearer " + user.jawbone_access_token}
    result = requests.get("https://jawbone.com/nudge/api/v.1.1/users/@me/", headers=headers)

    return result.json().get("data").get("xid")
