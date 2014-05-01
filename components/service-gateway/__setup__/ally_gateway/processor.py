'''
Created on Jan 5, 2012

@package: gateway service
@copyright: 2012 Sourcefabric o.p.s.
@license http://www.gnu.org/licenses/gpl - 3.0.txt
@author: Gabriel Nistor

Provides the configurations for delivering files from the local file system.
'''


from ..ally_http.processor import acceptRequestEncode, internalError, \
    contentLengthDecode
from ally.container import ioc
from ally.design.processor.assembly import Assembly
from ally.design.processor.handler import Handler
from ally.gateway.http.impl.processor.filter import GatewayFilterHandler
from ally.gateway.http.impl.processor.forward import GatewayForwardHandler
from ally.gateway.http.impl.processor.place_error import GatewayErrorHandler
from ally.gateway.http.impl.processor.respository import \
    GatewayRepositoryHandler
from ally.gateway.http.impl.processor.respository_authorized import \
    GatewayAuthorizedRepositoryHandler, AUTHORIZATION
from ally.gateway.http.impl.processor.selector import GatewaySelectorHandler
from ally.http.impl.processor.forward import ForwardHTTPHandler
from ally.http.impl.processor.header_parameter import HeaderParameterHandler, \
    HeaderParameterOptionsHandler
from ally.support.http.request import RequesterOptions, RequesterGetJSON
    
# --------------------------------------------------------------------

GATEWAY_INTERNAL = 'internal'
# The internal gateway name
GATEWAY_EXTERNAL = 'external'
# The external gateway name

# --------------------------------------------------------------------

@ioc.config
def external_host() -> str:
    ''' The external host name, something like 'localhost' '''
    return 'localhost'

@ioc.config
def external_port():
    ''' The external server port'''
    return 8081

@ioc.config
def gateway_uri() -> str:
    ''' The gateway URI to fetch the Gateway objects from'''
    return 'resources/Gateway'

@ioc.config
def gateway_authorized_uri() -> str:
    '''
    The gateway URI to fetch the authorized Gateway objects from, this URI needs to have a marker '%s' where the actual
    authentication code will be placed
    '''
    return 'resources/Security/Login/%s/Gateway'

@ioc.config
def gateway_check_session_active() -> str:
    '''
    The gateway URI to check if the authorized Gateway is still active, this URI needs to have a marker '%s' where the actual authentication code will be placed
    '''
    return 'resources/Security/Login/%s'

@ioc.config
def server_provide_gateway():
    '''
    Indicates that this server should provide the gateway service, possible values are:
    "internal" - the gateway should be configured for using internal REST resources, this means that the
                 ally core http component is present in python path.
    "external" - the gateway will use an external REST resources server, you need to configure the external host and port
                 in order to make this work.
    "don't"    - if this or any other unknown value is provided then the server will not provide gateway service.
    '''
    return GATEWAY_INTERNAL

@ioc.config
def cleanup_interval() -> float:
    '''
    The anonymous gateway data cleanup interval in seconds, this is basically the interval the anonymous gateway refreshes
    the data
    '''
    return 60

@ioc.config
def cleanup_authorized_interval() -> float:
    '''
    The authorized gateway data cleanup interval in seconds, this is the inactivity time for an authorization until it
    gets cleared
    '''
    return 60
@ioc.config
def read_from_params():
    '''If true will allow the gateway proxy server to read the authorization headers also from parameters.'''
    return True

# --------------------------------------------------------------------

@ioc.entity
def assemblyRESTRequest() -> Assembly:
    '''
    The assembly containing the handlers that will be used in processing the gateway REST requests.
    '''
    return Assembly('Gateway REST data')

@ioc.entity
def assemblyForward() -> Assembly:
    '''
    The assembly containing the handlers that will be used for forwarding the request.
    '''
    return Assembly('Gateway forward')

@ioc.entity
def assemblyForwardByHost() -> Assembly:
    '''
    The assembly containing the handlers that will be used for forwarding the request based on the specified host.
    '''
    return Assembly('Gateway forward by host')

@ioc.entity
def assemblyGateway() -> Assembly:
    '''
    The assembly containing the handlers that will be used in processing the gateway.
    '''
    return Assembly('Gateway')

# --------------------------------------------------------------------

@ioc.entity
def headersCorsAllow() -> set:
    '''
    Provides the cors header names defined by processors.
    '''
    return set()

@ioc.entity
def parametersAsHeaders() -> set:
    '''
    Provides the parameters headers names defined by processors.
    '''
    return set()

# --------------------------------------------------------------------
# Creating the processors used in handling the request

@ioc.entity
def requesterForwardOptions() -> RequesterOptions: return RequesterOptions(assemblyForward())

@ioc.entity
def requesterRESTGetJSON() -> RequesterGetJSON: return RequesterGetJSON(assemblyRESTRequest())

@ioc.entity
def headerParameter():
    b = HeaderParameterHandler()
    b.parameters = parametersAsHeaders()
    return b

@ioc.entity
def headerParameterOptions() -> Handler:
    b = HeaderParameterOptionsHandler()
    b.requesterOptions = requesterForwardOptions()
    return b

@ioc.entity
def gatewayRepository() -> Handler:
    b = GatewayRepositoryHandler()
    b.uri = gateway_uri()
    b.cleanupInterval = cleanup_interval()
    b.requesterGetJSON = requesterRESTGetJSON()
    return b

@ioc.entity
def gatewayAuthorizedRepository() -> Handler:
    b = GatewayAuthorizedRepositoryHandler()
    b.uri = gateway_authorized_uri()
    b.gateway_check_session_active = gateway_check_session_active()
    b.cleanupInterval = cleanup_authorized_interval()
    b.requesterGetJSON = requesterRESTGetJSON()
    return b

@ioc.entity
def gatewaySelector() -> Handler: return GatewaySelectorHandler()

@ioc.entity
def gatewayFilter() -> Handler:
    b = GatewayFilterHandler()
    b.requesterGetJSON = requesterRESTGetJSON()
    return b

@ioc.entity
def gatewayError() -> Handler: return GatewayErrorHandler()

@ioc.entity
def gatewayForward() -> Handler:
    b = GatewayForwardHandler()
    b.assembly = assemblyForward()
    b.assemblyByHost = assemblyForwardByHost()
    return b

@ioc.entity
def externalForward() -> Handler:
    b = ForwardHTTPHandler()
    b.externalHost = external_host()
    b.externalPort = external_port()
    return b

@ioc.entity
def externalForwardByHost() -> Handler: return ForwardHTTPHandler()

# --------------------------------------------------------------------

@ioc.before(headersCorsAllow)
def updateHeadersCors():
    headersCorsAllow().add(AUTHORIZATION.name)

@ioc.before(parametersAsHeaders)
def updateHeadersParameter():
    parametersAsHeaders().add(AUTHORIZATION.name)

@ioc.before(assemblyGateway)
def updateAssemblyGateway():
    assemblyGateway().add(internalError(), headerParameterOptions(), gatewayRepository(), gatewayAuthorizedRepository(),
                          gatewaySelector(), gatewayFilter(), gatewayError(), gatewayForward())
    if read_from_params(): assemblyGateway().add(headerParameter(), before=headerParameterOptions())
    
@ioc.before(assemblyRESTRequest)
def updateAssemblyRESTRequestForExternal():
    if server_provide_gateway() == GATEWAY_EXTERNAL:
        assemblyRESTRequest().add(acceptRequestEncode(), contentLengthDecode(), externalForward())
            
@ioc.before(assemblyForward)
def updateAssemblyForwardForExternal():
    if server_provide_gateway() == GATEWAY_EXTERNAL:
        assemblyForward().add(contentLengthDecode(), externalForward())
        
@ioc.before(assemblyForwardByHost)
def updateAssemblyForwardByHost():
    assemblyForwardByHost().add(contentLengthDecode(), externalForwardByHost())
