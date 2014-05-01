'''
Created on Jan 23, 2013

@package: gateway
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the gateway service setup patch.
'''

from ally.container import ioc
from ally.support.api.util_service import nameForModel
from gateway.api.gateway import Gateway
import logging

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

# --------------------------------------------------------------------

try:
    from __setup__ import ally_gateway  # @UnusedImport
    from __setup__ import ally_core_http  # @UnusedImport
except ImportError: log.info('No gateway component available, thus no need to publish the gateway data')
else:
    from __setup__.ally_gateway.processor import gateway_uri, gateway_check_session_active
    from __setup__.ally_core_http.server import root_uri_resources
    
    @ioc.replace(gateway_uri)
    def gateway_uri_anonymous():
        '''
        The anonymous gateway URI.
        '''
        uri = []
        if root_uri_resources():
            uri.append(root_uri_resources())
        uri.append(nameForModel(Gateway))
        return '/'.join(uri)

    @ioc.replace(gateway_check_session_active)
    def gateway_uri_check_active():
        '''
        The anonymous gateway URI.
        '''
        uri = []
        if root_uri_resources():
            uri.append(root_uri_resources())
        uri.append('Security/Login/%s')
        return '/'.join(uri)

