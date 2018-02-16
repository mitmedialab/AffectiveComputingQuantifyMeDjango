import simplejson

from django.db import models
from django.utils.translation import ugettext_lazy as _


class SerializedDataField(models.TextField):
    description = _("Serialized Data")
    default = "{}"

    def __init__(self, *args, **kwargs):

        tempkwargs = dict(default="{}")
        tempkwargs.update(kwargs)

        super(SerializedDataField, self).__init__(*args, **tempkwargs)

    def to_python(self, value):
        if value is None:
            return

        if not isinstance(value, basestring):
            return value

        if not value:
            return self.default

        value = simplejson.loads(value)
        return value

    def from_db_value(self, value, expression, connection, context):
        if value is None:
            return

        value = simplejson.loads(value)
        return value


    def get_prep_value(self, value):
        if value is None:
            return
        if isinstance(value, basestring): return value

        return simplejson.dumps(value)




class SerializedListField(SerializedDataField):
    description = _("Serialized List")
    default = "[]"

    def __init__(self, *args, **kwargs):

        tempkwargs = dict(default="[]")
        tempkwargs.update(kwargs)

        super(SerializedListField, self).__init__(*args, **tempkwargs)



