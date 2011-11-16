# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import mox
import nova
import unittest
import webob
from xml.dom import minidom

from nova import exception
from nova import test
from nova.api.openstack.contrib import security_groups
from nova.tests.api.openstack import fakes


FAKE_UUID = 'a47ae74e-ab08-447f-8eee-ffd43fc46c16'


class AttrDict(dict):
    def __getattr__(self, k):
        return self[k]


def security_group_template(**kwargs):
    sg = kwargs.copy()
    sg.setdefault('tenant_id', '123')
    sg.setdefault('name', 'test')
    sg.setdefault('description', 'test-description')
    return sg


def security_group_db(security_group, id=None):
    attrs = security_group.copy()
    if 'tenant_id' in attrs:
        attrs['project_id'] = attrs.pop('tenant_id')
    if id is not None:
        attrs['id'] = id
    attrs.setdefault('rules', [])
    attrs.setdefault('instances', [])
    return AttrDict(attrs)


def security_group_rule_template(**kwargs):
    rule = kwargs.copy()
    rule.setdefault('ip_protocol', 'tcp')
    rule.setdefault('from_port', 22)
    rule.setdefault('to_port', 22)
    rule.setdefault('parent_group_id', 2)
    return rule


def security_group_rule_db(rule, id=None):
    attrs = rule.copy()
    if 'ip_protocol' in attrs:
        attrs['protocol'] = attrs.pop('ip_protocol')
    return AttrDict(attrs)


def return_server(context, server_id):
    return {'id': int(server_id),
            'power_state': 0x01,
            'host': "localhost",
            'uuid': FAKE_UUID,
            'name': 'asdf'}


def return_server_by_uuid(context, server_uuid):
    return {'id': 1,
            'power_state': 0x01,
            'host': "localhost",
            'uuid': server_uuid,
            'name': 'asdf'}


def return_non_running_server(context, server_id):
    return {'id': server_id, 'power_state': 0x02,
            'host': "localhost", 'name': 'asdf'}


def return_security_group_by_name(context, project_id, group_name):
    return {'id': 1, 'name': group_name, "instances": [{'id': 1}]}


def return_security_group_without_instances(context, project_id, group_name):
    return {'id': 1, 'name': group_name}


def return_server_nonexistent(context, server_id):
    raise exception.InstanceNotFound(instance_id=server_id)


class StubExtensionManager(object):
    def register(self, *args):
        pass


class TestSecurityGroups(test.TestCase):
    def setUp(self):
        super(TestSecurityGroups, self).setUp()

        self.controller = security_groups.SecurityGroupController()
        self.manager = security_groups.Security_groups(StubExtensionManager())

    def tearDown(self):
        super(TestSecurityGroups, self).tearDown()

    def test_create_security_group(self):
        sg = security_group_template()

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        res_dict = self.controller.create(req, {'security_group': sg})
        self.assertEqual(res_dict['security_group']['name'], 'test')
        self.assertEqual(res_dict['security_group']['description'],
                         'test-description')

    def test_create_security_group_with_no_name(self):
        sg = security_group_template()
        del sg['name']

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPUnprocessableEntity,
                          self.controller.create, req, sg)

    def test_create_security_group_with_no_description(self):
        sg = security_group_template()
        del sg['description']

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_with_blank_name(self):
        sg = security_group_template(name='')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_with_whitespace_name(self):
        sg = security_group_template(name=' ')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_with_blank_description(self):
        sg = security_group_template(description='')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_with_whitespace_description(self):
        sg = security_group_template(description=' ')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_with_duplicate_name(self):
        sg = security_group_template()

        # FIXME: Stub out _get instead of creating twice
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.controller.create(req, {'security_group': sg})

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_with_no_body(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPUnprocessableEntity,
                          self.controller.create, req, None)

    def test_create_security_group_with_no_security_group(self):
        body = {'no-securityGroup': None}

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPUnprocessableEntity,
                          self.controller.create, req, body)

    def test_create_security_group_above_255_characters_name(self):
        sg = security_group_template(name='1234567890' * 26)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_above_255_characters_description(self):
        sg = security_group_template(description='1234567890' * 26)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_non_string_name(self):
        sg = security_group_template(name=12)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_create_security_group_non_string_description(self):
        sg = security_group_template(description=12)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group': sg})

    def test_get_security_group_list(self):
        groups = []
        for i, name in enumerate(['default', 'test']):
            sg = security_group_template(id=i + 1,
                                         name=name,
                                         description=name + '-desc',
                                         rules=[])
            groups.append(sg)
        expected = {'security_groups': groups}

        def return_security_groups(context, project_id):
            return [security_group_db(sg) for sg in groups]

        self.stubs.Set(nova.db, 'security_group_get_by_project',
                       return_security_groups)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups')
        res_dict = self.controller.index(req)

        self.assertEquals(res_dict, expected)

    def test_get_security_group_by_id(self):
        sg = security_group_template(id=2, rules=[])

        def return_security_group(context, group_id):
            self.assertEquals(sg['id'], group_id)
            return security_group_db(sg)

        self.stubs.Set(nova.db, 'security_group_get',
                       return_security_group)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups/2')
        res_dict = self.controller.show(req, '2')

        expected = {'security_group': sg}
        self.assertEquals(res_dict, expected)

    def test_get_security_group_by_invalid_id(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups/invalid')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.delete,
                          req, 'invalid')

    def test_get_security_group_by_non_existing_id(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups/111111111')
        self.assertRaises(webob.exc.HTTPNotFound, self.controller.delete,
                          req, '111111111')

    def test_delete_security_group_by_id(self):
        sg = security_group_template(id=1, rules=[])

        self.called = False

        def security_group_destroy(context, id):
            self.called = True

        def return_security_group(context, group_id):
            self.assertEquals(sg['id'], group_id)
            return security_group_db(sg)

        self.stubs.Set(nova.db, 'security_group_destroy',
                       security_group_destroy)
        self.stubs.Set(nova.db, 'security_group_get',
                       return_security_group)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups/1')
        self.controller.delete(req, '1')

        self.assertTrue(self.called)

    def test_delete_security_group_by_invalid_id(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups/invalid')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.delete,
                          req, 'invalid')

    def test_delete_security_group_by_non_existing_id(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-groups/11111111')
        self.assertRaises(webob.exc.HTTPNotFound, self.controller.delete,
                          req, '11111111')

    def test_associate_by_non_existing_security_group_name(self):
        body = dict(addSecurityGroup=dict(name='non-existing'))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.manager._addSecurityGroup, body, req, '1')

    def test_associate_by_invalid_server_id(self):
        body = dict(addSecurityGroup=dict(name='test'))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/invalid/action')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.manager._addSecurityGroup, body, req, 'invalid')

    def test_associate_without_body(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        body = dict(addSecurityGroup=None)

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._addSecurityGroup, body, req, '1')

    def test_associate_no_security_group_name(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        body = dict(addSecurityGroup=dict())

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._addSecurityGroup, body, req, '1')

    def test_associate_security_group_name_with_whitespaces(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        body = dict(addSecurityGroup=dict(name="   "))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._addSecurityGroup, body, req, '1')

    def test_associate_non_existing_instance(self):
        self.stubs.Set(nova.db, 'instance_get', return_server_nonexistent)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       return_server_nonexistent)
        body = dict(addSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.manager._addSecurityGroup, body, req, '1')

    def test_associate_non_running_instance(self):
        self.stubs.Set(nova.db, 'instance_get', return_non_running_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       return_non_running_server)
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_without_instances)
        body = dict(addSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._addSecurityGroup, body, req, '1')

    def test_associate_already_associated_security_group_to_instance(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       return_server_by_uuid)
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_by_name)
        body = dict(addSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._addSecurityGroup, body, req, '1')

    def test_associate(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       return_server_by_uuid)
        self.mox.StubOutWithMock(nova.db, 'instance_add_security_group')
        nova.db.instance_add_security_group(mox.IgnoreArg(),
                                            mox.IgnoreArg(),
                                            mox.IgnoreArg())
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_without_instances)
        self.mox.ReplayAll()

        body = dict(addSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.manager._addSecurityGroup(body, req, '1')

    def test_disassociate_by_non_existing_security_group_name(self):
        body = dict(removeSecurityGroup=dict(name='non-existing'))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.manager._removeSecurityGroup, body, req, '1')

    def test_disassociate_by_invalid_server_id(self):
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_by_name)
        body = dict(removeSecurityGroup=dict(name='test'))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/invalid/action')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.manager._removeSecurityGroup, body, req,
                          'invalid')

    def test_disassociate_without_body(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        body = dict(removeSecurityGroup=None)

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._removeSecurityGroup, body, req, '1')

    def test_disassociate_no_security_group_name(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        body = dict(removeSecurityGroup=dict())

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._removeSecurityGroup, body, req, '1')

    def test_disassociate_security_group_name_with_whitespaces(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        body = dict(removeSecurityGroup=dict(name="   "))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._removeSecurityGroup, body, req, '1')

    def test_disassociate_non_existing_instance(self):
        self.stubs.Set(nova.db, 'instance_get', return_server_nonexistent)
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_by_name)
        body = dict(removeSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.manager._removeSecurityGroup, body, req, '1')

    def test_disassociate_non_running_instance(self):
        self.stubs.Set(nova.db, 'instance_get', return_non_running_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       return_non_running_server)
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_by_name)
        body = dict(removeSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._removeSecurityGroup, body, req, '1')

    def test_disassociate_already_associated_security_group_to_instance(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       return_server_by_uuid)
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_without_instances)
        body = dict(removeSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.manager._removeSecurityGroup, body, req, '1')

    def test_disassociate(self):
        self.stubs.Set(nova.db, 'instance_get', return_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       return_server_by_uuid)
        self.mox.StubOutWithMock(nova.db, 'instance_remove_security_group')
        nova.db.instance_remove_security_group(mox.IgnoreArg(),
                                    mox.IgnoreArg(),
                                    mox.IgnoreArg())
        self.stubs.Set(nova.db, 'security_group_get_by_name',
                       return_security_group_by_name)
        self.mox.ReplayAll()

        body = dict(removeSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v1.1/123/servers/1/action')
        self.manager._removeSecurityGroup(body, req, '1')


class TestSecurityGroupRules(test.TestCase):
    def setUp(self):
        super(TestSecurityGroupRules, self).setUp()

        controller = security_groups.SecurityGroupController()

        sg1 = security_group_template(id=1)
        sg2 = security_group_template(id=2,
                                      name='authorize_revoke',
                                      description='authorize-revoke testing')
        db1 = security_group_db(sg1)
        db2 = security_group_db(sg2)

        def return_security_group(context, group_id):
            if group_id == db1['id']:
                return db1
            if group_id == db2['id']:
                return db2
            raise exception.NotFound()

        self.stubs.Set(nova.db, 'security_group_get',
                       return_security_group)

        self.parent_security_group = db2

        self.controller = security_groups.SecurityGroupRulesController()

    def tearDown(self):
        super(TestSecurityGroupRules, self).tearDown()

    def test_create_by_cidr(self):
        rule = security_group_rule_template(cidr='10.2.3.124/24')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        res_dict = self.controller.create(req, {'security_group_rule': rule})

        security_group_rule = res_dict['security_group_rule']
        self.assertNotEquals(security_group_rule['id'], 0)
        self.assertEquals(security_group_rule['parent_group_id'], 2)
        self.assertEquals(security_group_rule['ip_range']['cidr'],
                          "10.2.3.124/24")

    def test_create_by_group_id(self):
        rule = security_group_rule_template(group_id='1')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        res_dict = self.controller.create(req, {'security_group_rule': rule})

        security_group_rule = res_dict['security_group_rule']
        self.assertNotEquals(security_group_rule['id'], 0)
        self.assertEquals(security_group_rule['parent_group_id'], 2)

    def test_create_by_invalid_cidr_json(self):
        rules = {
                  "security_group_rule": {
                        "ip_protocol": "tcp",
                        "from_port": "22",
                        "to_port": "22",
                        "parent_group_id": 2,
                        "cidr": "10.2.3.124/2433"}}
        rule = security_group_rule_template(
                ip_protocol="tcp",
                from_port=22,
                to_port=22,
                parent_group_id=2,
                cidr="10.2.3.124/2433")
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_by_invalid_tcp_port_json(self):
        rule = security_group_rule_template(
                ip_protocol="tcp",
                from_port=75534,
                to_port=22,
                parent_group_id=2,
                cidr="10.2.3.124/24")

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_by_invalid_icmp_port_json(self):
        rule = security_group_rule_template(
                ip_protocol="icmp",
                from_port=1,
                to_port=256,
                parent_group_id=2,
                cidr="10.2.3.124/24")
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_add_existing_rules(self):
        rule = security_group_rule_template(cidr='10.0.0.0/24')

        self.parent_security_group['rules'] = [security_group_rule_db(rule)]

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_no_body(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPUnprocessableEntity,
                          self.controller.create, req, None)

    def test_create_with_no_security_group_rule_in_body(self):
        rules = {'test': 'test'}
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPUnprocessableEntity,
                          self.controller.create, req, rules)

    def test_create_with_invalid_parent_group_id(self):
        rule = security_group_rule_template(parent_group_id='invalid')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_non_existing_parent_group_id(self):
        rule = security_group_rule_template(group_id='invalid',
                                            parent_group_id='1111111111111')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPNotFound, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_invalid_protocol(self):
        rule = security_group_rule_template(ip_protocol='invalid-protocol',
                                            cidr='10.2.2.0/24')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_no_protocol(self):
        rule = security_group_rule_template(cidr='10.2.2.0/24')
        del rule['ip_protocol']

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_invalid_from_port(self):
        rule = security_group_rule_template(from_port='666666',
                                            cidr='10.2.2.0/24')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_invalid_to_port(self):
        rule = security_group_rule_template(to_port='666666',
                                            cidr='10.2.2.0/24')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_non_numerical_from_port(self):
        rule = security_group_rule_template(from_port='invalid',
                                            cidr='10.2.2.0/24')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_non_numerical_to_port(self):
        rule = security_group_rule_template(to_port='invalid',
                                            cidr='10.2.2.0/24')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_no_from_port(self):
        rule = security_group_rule_template(cidr='10.2.2.0/24')
        del rule['from_port']

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_no_to_port(self):
        rule = security_group_rule_template(cidr='10.2.2.0/24')
        del rule['to_port']

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_invalid_cidr(self):
        rule = security_group_rule_template(cidr='10.2.2222.0/24')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_no_cidr_group(self):
        rule = security_group_rule_template()

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        res_dict = self.controller.create(req, {'security_group_rule': rule})

        security_group_rule = res_dict['security_group_rule']
        self.assertNotEquals(security_group_rule['id'], 0)
        self.assertEquals(security_group_rule['parent_group_id'],
                          self.parent_security_group['id'])
        self.assertEquals(security_group_rule['ip_range']['cidr'],
                          "0.0.0.0/0")

    def test_create_with_invalid_group_id(self):
        rule = security_group_rule_template(group_id='invalid')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_empty_group_id(self):
        rule = security_group_rule_template(group_id='')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_with_nonexist_group_id(self):
        rule = security_group_rule_template(group_id='222222')

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_rule_with_same_group_parent_id(self):
        rule = security_group_rule_template(group_id=2)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_delete(self):
        rule = security_group_rule_template(id=10)

        def security_group_rule_get(context, id):
            return security_group_rule_db(rule)

        def security_group_rule_destroy(context, id):
            pass

        self.stubs.Set(nova.db, 'security_group_rule_get',
                       security_group_rule_get)
        self.stubs.Set(nova.db, 'security_group_rule_destroy',
                       security_group_rule_destroy)

        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules/10')
        self.controller.delete(req, '10')

    def test_delete_invalid_rule_id(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules' +
                                      '/invalid')
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.delete,
                          req, 'invalid')

    def test_delete_non_existing_rule_id(self):
        req = fakes.HTTPRequest.blank('/v1.1/123/os-security-group-rules' +
                                      '/22222222222222')
        self.assertRaises(webob.exc.HTTPNotFound, self.controller.delete,
                          req, '22222222222222')


class TestSecurityGroupRulesXMLDeserializer(unittest.TestCase):

    def setUp(self):
        self.deserializer = security_groups.SecurityGroupRulesXMLDeserializer()

    def test_create_request(self):
        serial_request = """
<security_group_rule>
  <parent_group_id>12</parent_group_id>
  <from_port>22</from_port>
  <to_port>22</to_port>
  <group_id></group_id>
  <ip_protocol>tcp</ip_protocol>
  <cidr>10.0.0.0/24</cidr>
</security_group_rule>"""
        request = self.deserializer.deserialize(serial_request, 'create')
        expected = {
            "security_group_rule": {
                "parent_group_id": "12",
                "from_port": "22",
                "to_port": "22",
                "ip_protocol": "tcp",
                "group_id": "",
                "cidr": "10.0.0.0/24",
            },
        }
        self.assertEquals(request['body'], expected)

    def test_create_no_protocol_request(self):
        serial_request = """
<security_group_rule>
  <parent_group_id>12</parent_group_id>
  <from_port>22</from_port>
  <to_port>22</to_port>
  <group_id></group_id>
  <cidr>10.0.0.0/24</cidr>
</security_group_rule>"""
        request = self.deserializer.deserialize(serial_request, 'create')
        expected = {
            "security_group_rule": {
                "parent_group_id": "12",
                "from_port": "22",
                "to_port": "22",
                "group_id": "",
                "cidr": "10.0.0.0/24",
            },
        }
        self.assertEquals(request['body'], expected)


class TestSecurityGroupXMLDeserializer(unittest.TestCase):

    def setUp(self):
        self.deserializer = security_groups.SecurityGroupXMLDeserializer()

    def test_create_request(self):
        serial_request = """
<security_group name="test">
   <description>test</description>
</security_group>"""
        request = self.deserializer.deserialize(serial_request, 'create')
        expected = {
            "security_group": {
                "name": "test",
                "description": "test",
            },
        }
        self.assertEquals(request['body'], expected)

    def test_create_no_description_request(self):
        serial_request = """
<security_group name="test">
</security_group>"""
        request = self.deserializer.deserialize(serial_request, 'create')
        expected = {
            "security_group": {
                "name": "test",
            },
        }
        self.assertEquals(request['body'], expected)

    def test_create_no_name_request(self):
        serial_request = """
<security_group>
<description>test</description>
</security_group>"""
        request = self.deserializer.deserialize(serial_request, 'create')
        expected = {
            "security_group": {
                "description": "test",
            },
        }
        self.assertEquals(request['body'], expected)
