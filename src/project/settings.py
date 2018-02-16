"""
Django settings for this project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

import datetime
import os

import passwords

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = passwords.SECRET_KEY

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False


ALLOWED_HOSTS = passwords.ALLOWED_HOSTS


# Application definition

INSTALLED_APPS = (
    'pipeline',
    'grappelli',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_expiring_authtoken',
    'app',
    'acra',
)

MIDDLEWARE_CLASSES = (
    'project.middleware.ExceptionLoggingMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'project.urls'

WSGI_APPLICATION = 'project.wsgi.application'

APP_TEMPLATE_CONTEXT_PROCESSORS = (
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.template.context_processors.debug",
    "django.template.context_processors.i18n",
    "django.template.context_processors.media",
    "django.template.context_processors.static",
    "django.template.context_processors.tz",
    "django.contrib.messages.context_processors.messages",
)
APP_TEMPLATE_DEBUG = True

APP_TEMPLATE_LOADERS = (
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                    )

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': (os.path.join(BASE_DIR, "templates-admin"),),
        'OPTIONS': {
            'context_processors': APP_TEMPLATE_CONTEXT_PROCESSORS,
            'debug': APP_TEMPLATE_DEBUG,
            'loaders': APP_TEMPLATE_LOADERS,
        },
    },
    {
        'BACKEND': 'project.jinja2backend.Jinja2Backend',
        'DIRS': (os.path.join(BASE_DIR, "templates"),),
        'APP_DIRS': True,
        'OPTIONS': {
            'environment': 'project.jinjaenvironment.environment',
            'context_processors': APP_TEMPLATE_CONTEXT_PROCESSORS,
            'extensions': ['pipeline.templatetags.ext.PipelineExtension'],
        },

    },
]

# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': passwords.MYSQL_DB,
        'USER': passwords.MYSQL_USER,
        'PASSWORD': passwords.MYSQL_PASSWORD,
        'HOST': '', # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '', # Set to empty string for default.
        'OPTIONS': {
            # NOTE: for MySQL 5.7, use: 'init_command': 'SET default_storage_engine=INNODB',
            'init_command': 'SET default_storage_engine=INNODB',
        }
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True



AUTH_USER_MODEL = 'app.User'

AUTHENTICATION_BACKENDS = (
    'app.models.UserBackend',
    'django.contrib.auth.backends.ModelBackend',
)


LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt': "%d/%b/%Y %H:%M:%S"
        },
    },
    'handlers': {
        'logfile': {
            'level': 'DEBUG',
            'class': 'project.logger.GroupWriteRotatingFileHandler',
            'filename': "/var/log/django/django.log",
            'maxBytes': 50000,
            'backupCount': 200,
            'formatter': 'standard',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
    },
    'loggers': {
        '': {
            'handlers': ['logfile'],
            'propagate': True,
            'level': 'WARN',
        }
    }
}

if DEBUG:
    # make all loggers use the console.
    for logger in LOGGING['loggers']:
        LOGGING['loggers'][logger]['handlers'] += ['console']

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'pipeline.finders.PipelineFinder',
)
STATICFILES_STORAGE = 'pipeline.storage.PipelineCachedStorage'
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "../staticfiles")

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, "../media")

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "static"),
)
PIPELINE_CSS_COMPRESSOR = 'pipeline.compressors.yui.YUICompressor'
PIPELINE_JS_COMPRESSOR = 'pipeline.compressors.yui.YUICompressor'
PIPELINE_YUI_BINARY = '/usr/bin/yui-compressor'
PIPELINE_LESS_BINARY = '/usr/local/bin/lessc'

PIPELINE_COMPILERS = (
  'pipeline.compilers.less.LessCompiler',
)

PIPELINE_JS = {
  'scripts': {
    'source_filenames': (
        'js/base.js',
    ),
    'output_filename': 'js/script.js',
  },
}

PIPELINE_CSS = {
  'less': {
    'source_filenames': (
        "less/reset.css",
        "less/base.less",
    ),
    'output_filename': 'css/style.css',
  },
}

APP_KEY = passwords.APP_KEY

EXPIRING_TOKEN_LIFESPAN = datetime.timedelta(hours=24)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_expiring_authtoken.authentication.ExpiringTokenAuthentication',
    )
}

