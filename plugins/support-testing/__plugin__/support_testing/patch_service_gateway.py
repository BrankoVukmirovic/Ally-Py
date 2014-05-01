'''
Created on Mar 25, 2014

@package: support testing
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the service gateway patch.
'''

import logging

from __setup__.ally_core_http.server import root_uri_resources
from __setup__.ally_http.server import assemblyServer
from ally.container import ioc
from ally.design.processor.handler import Handler

from .patch_server import root_uri_test_resources
from .patch_server import routerTesting, testing_allowed
from .patch_server import updateAssemblyServerForTesting


# --------------------------------------------------------------------
log = logging.getLogger(__name__)

# --------------------------------------------------------------------

try: from __setup__ import ally_gateway  # @UnusedImport
except ImportError: log.info('No Gateway service available to patch.')
else:
    from __setup__.ally_gateway.patch_ally_core_http import updateAssemblyForwardForResources, \
        isInternal
    from __setup__.ally_gateway.processor import assemblyForward
    from __setup__.ally_gateway.patch_ally_core_http import updateAssemblyRESTRequestForResources
    from __setup__.ally_gateway.processor import assemblyRESTRequest
    from __setup__.ally_gateway.processor import cleanup_interval
    from __setup__.ally_gateway.processor import requesterRESTGetJSON, \
        cleanup_authorized_interval, gateway_authorized_uri, gateway_uri, \
        gateway_check_session_active
    from __setup__.ally_gateway.processor import updateAssemblyGateway, assemblyGateway, \
    gatewayRepository, gatewayAuthorizedRepository
    from ally.gateway.http.impl.processor.respository import GatewayRepositoryHandler
    from ally.gateway.http.impl.processor.respository_authorized import GatewayAuthorizedRepositoryHandler
    
    @ioc.entity
    def gatewayTestRepository() -> Handler:
        b = GatewayRepositoryHandler()
        b.uri = '%s%s' % (root_uri_test_resources(), gateway_uri()[len(root_uri_resources()):])
        b.cleanupInterval = cleanup_interval()
        b.requesterGetJSON = requesterRESTGetJSON()
        return b
    
    @ioc.entity
    def gatewayTestAuthorizedRepository() -> Handler:
        b = GatewayAuthorizedRepositoryHandler()
        b.uri = '%s%s' % (root_uri_test_resources(), gateway_authorized_uri()[len(root_uri_resources()):])
        b.cleanupInterval = cleanup_authorized_interval()
        b.gateway_check_session_active = '%s%s' % (root_uri_test_resources(), gateway_check_session_active()[len(root_uri_resources()):])
        b.requesterGetJSON = requesterRESTGetJSON()
        return b

    # ----------------------------------------------------------------

    @ioc.after(updateAssemblyRESTRequestForResources)
    def updateAssemblyRESTRequestForTestResources():
        if isInternal() and testing_allowed(): assemblyRESTRequest().add(routerTesting())
        
    @ioc.after(updateAssemblyForwardForResources)
    def updateAssemblyForwardForTestResources():
        if isInternal() and testing_allowed(): assemblyForward().add(routerTesting())
    
    @ioc.after(updateAssemblyGateway)
    def updateAssemblyGatewayForTest():
        if testing_allowed():
            assemblyGateway().add(gatewayTestRepository(), after=gatewayRepository())
            assemblyGateway().add(gatewayTestAuthorizedRepository(), after=gatewayAuthorizedRepository())
            
    @ioc.after(updateAssemblyServerForTesting)
    def updateAssemblyServerForTestingInternal():
        if isInternal() and testing_allowed(): assemblyServer().remove(routerTesting())
        
