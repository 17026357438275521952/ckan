# encoding: utf-8

'''
NB Don't test logic functions here. This is just for the mechanics of the API
controller itself.
'''
import json
import re
import mock
import __builtin__ as builtins
from StringIO import StringIO

from nose.tools import assert_equal, assert_in, eq_
from pyfakefs import fake_filesystem

from six import text_type
from six.moves import xrange

from ckan.lib.helpers import url_for
import ckan.tests.helpers as helpers
from ckan.tests import factories
from ckan.lib import helpers as template_helpers, uploader as ckan_uploader
import ckan.plugins as p
from ckan import model

fs = fake_filesystem.FakeFilesystem()
fake_os = fake_filesystem.FakeOsModule(fs)
fake_open = fake_filesystem.FakeFileOpen(fs)
real_open = open


def mock_open_if_open_fails(*args, **kwargs):
    try:
        return real_open(*args, **kwargs)
    except (OSError, IOError):
        return fake_open(*args, **kwargs)


class TestApiController(helpers.FunctionalTestBase):

    @helpers.change_config('ckan.storage_path', '/doesnt_exist')
    @mock.patch.object(builtins, 'open', side_effect=mock_open_if_open_fails)
    @mock.patch.object(ckan_uploader, 'os', fake_os)
    @mock.patch.object(ckan_uploader, '_storage_path', new='/doesnt_exist')
    def test_resource_create_upload_file(self, _):
        user = factories.User()
        pkg = factories.Dataset(creator_user_id=user['id'])
        # upload_content = StringIO()
        # upload_content.write('test-content')

        url = url_for(
            controller='api',
            action='action',
            logic_function='resource_create', ver='/3')
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        postparams = {
            'name': 'test-flask-upload',
            'package_id': pkg['id']
        }
        upload_content = 'test-content'
        upload_info = ('upload', 'test-upload.txt', upload_content)
        app = self._get_test_app()
        resp = app.post(
            url, params=postparams,
            upload_files=[upload_info],
            extra_environ=env
            # content_type= 'application/json'
        )
        result = resp.json['result']
        eq_('upload', result['url_type'])
        eq_(len(upload_content), result['size'])

    def test_unicode_in_error_message_works_ok(self):
        # Use tag_delete to echo back some unicode
        app = self._get_test_app()
        org_url = '/api/action/tag_delete'
        data_dict = {'id': u'Delta symbol: \u0394'}  # unicode gets rec'd ok
        postparams = '%s=1' % json.dumps(data_dict)
        response = app.post(url=org_url, params=postparams, status=404)
        # The unicode is backslash encoded (because that is the default when
        # you do str(exception) )
        assert 'Delta symbol: \\u0394' in response.body

    def test_dataset_autocomplete_name(self):
        dataset = factories.Dataset(name='rivers')
        url = url_for(controller='api', action='dataset_autocomplete', ver='/2')
        assert_equal(url, '/api/2/util/dataset/autocomplete')
        app = self._get_test_app()

        response = app.get(
            url=url,
            params={
                'incomplete': u'rive',
            },
            status=200,
        )

        results = json.loads(response.body)
        assert_equal(results, {"ResultSet": {"Result": [{
            'match_field': 'name',
            "name": "rivers",
            'match_displayed': 'rivers',
            'title': dataset['title'],
        }]}})
        assert_equal(response.headers['Content-Type'],
                     'application/json;charset=utf-8')

    def test_dataset_autocomplete_title(self):
        dataset = factories.Dataset(name='test_ri', title='Rivers')
        url = url_for(controller='api', action='dataset_autocomplete', ver='/2')
        assert_equal(url, '/api/2/util/dataset/autocomplete')
        app = self._get_test_app()

        response = app.get(
            url=url,
            params={
                'incomplete': u'riv',
            },
            status=200,
        )

        results = json.loads(response.body)
        assert_equal(results, {"ResultSet": {"Result": [{
            'match_field': 'title',
            "name": dataset['name'],
            'match_displayed': 'Rivers (test_ri)',
            'title': 'Rivers',
        }]}})
        assert_equal(response.headers['Content-Type'],
                     'application/json;charset=utf-8')

    def test_tag_autocomplete(self):
        factories.Dataset(tags=[{'name': 'rivers'}])
        url = url_for(controller='api', action='tag_autocomplete', ver='/2')
        assert_equal(url, '/api/2/util/tag/autocomplete')
        app = self._get_test_app()

        response = app.get(
            url=url,
            params={
                'incomplete': u'rive',
            },
            status=200,
        )

        results = json.loads(response.body)
        assert_equal(results, {"ResultSet": {"Result": [{"Name": "rivers"}]}})
        assert_equal(response.headers['Content-Type'],
                     'application/json;charset=utf-8')

    def test_group_autocomplete_by_name(self):
        org = factories.Group(name='rivers', title='Bridges')
        url = url_for(controller='api', action='group_autocomplete', ver='/2')
        assert_equal(url, '/api/2/util/group/autocomplete')
        app = self._get_test_app()

        response = app.get(
            url=url,
            params={
                'q': u'rive',
            },
            status=200,
        )

        results = json.loads(response.body)
        assert_equal(len(results), 1)
        assert_equal(results[0]['name'], 'rivers')
        assert_equal(results[0]['title'], 'Bridges')
        assert_equal(response.headers['Content-Type'],
                     'application/json;charset=utf-8')

    def test_group_autocomplete_by_title(self):
        org = factories.Group(name='frogs', title='Bugs')
        url = url_for(controller='api', action='group_autocomplete', ver='/2')
        app = self._get_test_app()

        response = app.get(
            url=url,
            params={
                'q': u'bug',
            },
            status=200,
        )

        results = json.loads(response.body)
        assert_equal(len(results), 1)
        assert_equal(results[0]['name'], 'frogs')

    def test_organization_autocomplete_by_name(self):
        org = factories.Organization(name='simple-dummy-org')
        url = url_for(controller='api', action='organization_autocomplete', ver='/2')
        assert_equal(url, '/api/2/util/organization/autocomplete')
        app = self._get_test_app()

        response = app.get(
            url=url,
            params={
                'q': u'simple',
            },
            status=200,
        )

        results = json.loads(response.body)
        assert_equal(len(results), 1)
        assert_equal(results[0]['name'], 'simple-dummy-org')
        assert_equal(results[0]['title'], org['title'])
        assert_equal(response.headers['Content-Type'],
                     'application/json;charset=utf-8')

    def test_organization_autocomplete_by_title(self):
        org = factories.Organization(title='Simple dummy org')
        url = url_for(controller='api', action='organization_autocomplete', ver='/2')
        app = self._get_test_app()

        response = app.get(
            url=url,
            params={
                'q': u'simple dum',
            },
            status=200,
        )

        results = json.loads(response.body)
        assert_equal(len(results), 1)
        assert_equal(results[0]['title'], 'Simple dummy org')

    def test_config_option_list_access_sysadmin(self):
        user = factories.Sysadmin()
        url = url_for(
            controller='api',
            action='action',
            logic_function='config_option_list',
            ver='/3')
        app = self._get_test_app()

        app.get(
            url=url,
            params={},
            extra_environ={'REMOTE_USER': user['name'].encode('ascii')},
            status=200,
        )

    def test_config_option_list_access_sysadmin_jsonp(self):
        user = factories.Sysadmin()
        url = url_for(
            controller='api',
            action='action',
            logic_function='config_option_list',
            ver='/3')
        app = self._get_test_app()

        app.get(
            url=url,
            params={'callback': 'myfn'},
            extra_environ={'REMOTE_USER': user['name'].encode('ascii')},
            status=403,
        )

    def test_jsonp_works_on_get_requests(self):

        dataset1 = factories.Dataset()
        dataset2 = factories.Dataset()

        url = url_for(
            controller='api',
            action='action',
            logic_function='package_list',
            ver='/3')
        app = self._get_test_app()
        res = app.get(
            url=url,
            params={'callback': 'my_callback'},
        )
        assert re.match('my_callback\(.*\);', res.body), res
        # Unwrap JSONP callback (we want to look at the data).
        msg = res.body[len('my_callback') + 1:-2]
        res_dict = json.loads(msg)
        eq_(res_dict['success'], True)
        eq_(sorted(res_dict['result']),
            sorted([dataset1['name'], dataset2['name']]))

    def test_jsonp_returns_javascript_content_type(self):
        url = url_for(
            controller='api',
            action='action',
            logic_function='status_show',
            ver='/3')
        app = self._get_test_app()
        res = app.get(
            url=url,
            params={'callback': 'my_callback'},
        )
        assert_in('application/javascript', res.headers.get('Content-Type'))

    def test_jsonp_does_not_work_on_post_requests(self):

        dataset1 = factories.Dataset()
        dataset2 = factories.Dataset()

        url = url_for(
            controller='api',
            action='action',
            logic_function='package_list',
            ver='/3',
            callback='my_callback',
        )
        app = self._get_test_app()
        res = app.post(
            url=url,
        )
        # The callback param is ignored and the normal response is returned
        assert not res.body.startswith('my_callback')
        res_dict = json.loads(res.body)
        eq_(res_dict['success'], True)
        eq_(sorted(res_dict['result']),
            sorted([dataset1['name'], dataset2['name']]))


class TestApiControllerApiInfo(helpers.FunctionalTestBase):
    """
    As template loader initialized during setiing-up application
    datastore(container of ajax_snippets/api_info.html) should be loaded before
    any test
    """
    @classmethod
    def _apply_config_changes(cls, config):
        config['ckan.plugins'] = 'datastore'

    @classmethod
    def teardown_class(cls):
        if p.plugin_loaded('datastore'):
            p.unload('datastore')

    def test_api_info(self):

        dataset = factories.Dataset()
        resource = factories.Resource(
            id='588dfa82-760c-45a2-b78a-e3bc314a4a9b',
            package_id=dataset['id'], datastore_active=True)

        # the 'API info' is seen on the resource_read page, a snippet loaded by
        # javascript via data_api_button.html
        url = template_helpers.url_for(
            controller='api', action='snippet', ver=1,
            snippet_path='api_info.html', resource_id=resource['id'])

        app = self._get_test_app()
        page = app.get(url, status=200)

        # check we built all the urls ok
        expected_urls = (
            'http://test.ckan.net/api/3/action/datastore_create',
            'http://test.ckan.net/api/3/action/datastore_upsert',
            '<code>http://test.ckan.net/api/3/action/datastore_search',
            'http://test.ckan.net/api/3/action/datastore_search_sql',
            'http://test.ckan.net/api/3/action/datastore_search?resource_id=588dfa82-760c-45a2-b78a-e3bc314a4a9b&amp;limit=5',
            'http://test.ckan.net/api/3/action/datastore_search?q=jones&amp;resource_id=588dfa82-760c-45a2-b78a-e3bc314a4a9b',
            'http://test.ckan.net/api/3/action/datastore_search_sql?sql=SELECT * from &#34;588dfa82-760c-45a2-b78a-e3bc314a4a9b&#34; WHERE title LIKE &#39;jones&#39;',
            "url: 'http://test.ckan.net/api/3/action/datastore_search'",
            "http://test.ckan.net/api/3/action/datastore_search?resource_id=588dfa82-760c-45a2-b78a-e3bc314a4a9b&amp;limit=5&amp;q=title:jones",
        )
        for url in expected_urls:
            assert url in page, url


class TestRevisionSearch(helpers.FunctionalTestBase):

    # Error cases

    def test_no_search_term(self):
        app = self._get_test_app()
        response = app.get('/api/search/revision', status=400)
        assert_in('Bad request - Missing search term', response.body)

    def test_no_search_term_api_v2(self):
        app = self._get_test_app()
        response = app.get('/api/2/search/revision', status=400)
        assert_in('Bad request - Missing search term', response.body)

    def test_date_instead_of_revision(self):
        app = self._get_test_app()
        response = app.get('/api/search/revision'
                           '?since_id=2010-01-01T00:00:00', status=404)
        assert_in('Not found - There is no revision', response.body)

    def test_date_invalid(self):
        app = self._get_test_app()
        response = app.get('/api/search/revision'
                           '?since_time=2010-02-31T00:00:00', status=400)
        assert_in('Bad request - ValueError: day is out of range for month',
                  response.body)

    def test_no_value(self):
        app = self._get_test_app()
        response = app.get('/api/search/revision?since_id=', status=400)
        assert_in('Bad request - No revision specified', response.body)

    def test_revision_doesnt_exist(self):
        app = self._get_test_app()
        response = app.get('/api/search/revision?since_id=1234', status=404)
        assert_in('Not found - There is no revision', response.body)

    def test_revision_doesnt_exist_api_v2(self):
        app = self._get_test_app()
        response = app.get('/api/2/search/revision?since_id=1234', status=404)
        assert_in('Not found - There is no revision', response.body)

    # Normal usage

    @classmethod
    def _create_revisions(cls, num_revisions):
        rev_ids = []
        for i in xrange(num_revisions):
            rev = model.repo.new_revision()
            rev.id = text_type(i)
            model.Session.commit()
            rev_ids.append(rev.id)
        return rev_ids

    def test_revision_since_id(self):
        rev_ids = self._create_revisions(4)
        app = self._get_test_app()

        response = app.get('/api/2/search/revision?since_id=%s' % rev_ids[1])

        res = json.loads(response.body)
        assert_equal(res, rev_ids[2:])

    def test_revision_since_time(self):
        rev_ids = self._create_revisions(4)
        app = self._get_test_app()

        rev1 = model.Session.query(model.Revision).get(rev_ids[1])
        response = app.get('/api/2/search/revision?since_time=%s'
                           % rev1.timestamp.isoformat())

        res = json.loads(response.body)
        assert_equal(res, rev_ids[2:])

    def test_revisions_returned_are_limited(self):
        rev_ids = self._create_revisions(55)
        app = self._get_test_app()

        response = app.get('/api/2/search/revision?since_id=%s' % rev_ids[1])

        res = json.loads(response.body)
        assert_equal(res, rev_ids[2:52])  # i.e. limited to 50
