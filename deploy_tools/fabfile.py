from fabric.contrib.files import append, exists, sed, settings, hide
from fabric.api import env, local, run
import random

REPO_URL = 'https://github.com/dredivaris/tdd-dev-with-python-book.git'

def deploy():
    site_folder = '/home/%s/sites/%s' % (env.user, env.host)
    source_folder = site_folder + '/source'
    _create_directory_structure_if_necessary(site_folder)
    _get_latest_source(source_folder)
    _update_settings(source_folder, env.host)
    _update_virtualenv(source_folder)
    _update_static_files(source_folder)
    _update_database(source_folder)
    _create_virtual_host(source_folder, env.host)
    _setup_upstart(source_folder, env.host)
    start_services(env.host)

def _create_directory_structure_if_necessary(site_folder):
    for subfolder in ('database', 'static', 'virtualenv', 'source'):
        run('mkdir -p %s/%s' % (site_folder, subfolder))


def _get_latest_source(source_folder):
    if exists(source_folder + '/.git'):
        run('cd %s && git fetch' % source_folder)
    else:
        run('git clone %s %s' % (REPO_URL, source_folder))
    current_commit = local('git log -n 1 --format=%H', capture=True)
    run('cd %s && git reset --hard %s' % (source_folder, current_commit))


def _update_settings(source_folder, site_name):
    settings_path = source_folder + '/superlists/settings.py'
    sed(settings_path, "DEBUG = True", "DEBUG = False")
    sed(settings_path, 'ALLOWED_HOSTS =.+$', 'ALLOWED_HOSTS = ["%s"]' % site_name)

    secret_key_file = source_folder + '/superlists/secret_key.py'
    if not exists(secret_key_file):
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        key = ''.join(random.SystemRandom().choice(chars) for _ in range(50))
        append(secret_key_file, "SECRET_KEY = '%s'" % key)
    append(settings_path, '\nfrom .secret_key import SECRET_KEY')


def _update_virtualenv(source_folder):
    virtualenv_folder = source_folder + '/../virtualenv'
    if not exists(virtualenv_folder +  '/bin/pip'):
        run('virtualenv --python=python3 %s' % virtualenv_folder)
    run('%s/bin/pip install -r %s/requirements.txt' % (virtualenv_folder, source_folder))


def _update_static_files(source_folder):
    run('cd %s && ../virtualenv/bin/python3 manage.py collectstatic --noinput' % source_folder)


def _update_database(source_folder):
    run('cd %s && ../virtualenv/bin/python3 manage.py migrate --noinput' % source_folder)


def _create_virtual_host(source_folder, site_name):
    run('''cd %s && sed "s/SITENAME/%s/g" deploy_tools/nginx.template.conf | sudo tee /etc/nginx/sites-available/%s''' %
        (source_folder, site_name, site_name))
    with settings(
        hide('warnings'),
        warn_only=True
    ):
        run('''sudo ln -s /etc/nginx/sites-available/%s /etc/nginx/sites-enabled/%s''' % (site_name, site_name))


def _setup_upstart(source_folder, site_name):
    run('''cd %s && sed "s/SITENAME/%s/g" deploy_tools/gunicorn-upstart.template.conf | sudo tee /etc/init/gunicorn-%s.conf''' % (source_folder, site_name, site_name))


def start_services(site_name):
    run('sudo service nginx reload')
    with settings(
        hide('warnings'),
        warn_only=True
    ):
        run('sudo start gunicorn-%s' % site_name)
