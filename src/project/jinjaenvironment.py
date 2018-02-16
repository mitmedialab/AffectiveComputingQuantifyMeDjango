from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.urlresolvers import reverse
from jinja2 import Environment

from django.conf import settings
import simplejson


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'STATIC': settings.STATIC_URL,
        'MEDIA': settings.MEDIA_URL,
        'url': reverse,
    })
    env.filters.update({
        'to_json': simplejson.dumps,
    })
    return env


