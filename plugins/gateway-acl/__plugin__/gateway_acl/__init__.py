'''
Created on Nov 14, 2012

@package: gateway acl
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Contains the setup files for service access control layer gateway.
'''

# --------------------------------------------------------------------

NAME = 'ally-gateway-acl'
VERSION = '1.0'
AUTHOR = 'Gabriel Nistor'
AUTHOR_EMAIL = 'gabriel.nistor@sourcefabric.org'
DESCRIPTION = '''This plugin provides the service gateways.'''
LONG_DESCRIPTION = '''The ACL (access control layer) gateway plugin integrates gateways that are
designed based on published REST models and services, basically makes the conversion between access allowed on a
service call and a gateway REST model.'''
INSTALL_REQUIRES = ['ally-gateway >= 1.0', 'ally-core-http >= 1.0']