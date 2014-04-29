'''
Created on Apr 12, 2012

@package: gateway service
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the gateway repository processor.
'''

from . import respository
from .respository import GatewayRepositoryHandler, Repository, Identifier, \
    Response
from ally.container import ioc, wire
from ally.container.ioc import injected
from ally.design.processor.attribute import requires, defines
from ally.design.processor.context import Context
from ally.gateway.http.spec.gateway import RepositoryJoined
from ally.http.spec.codes import BAD_GATEWAY, UNAUTHORIZED_ACCESS 
from ally.http.spec.headers import HeaderRaw, HeadersRequire
from datetime import datetime, timedelta
from urllib.parse import quote
import logging

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

AUTHORIZATION = HeaderRaw('Authorization')
# The header for the session identifier. 

# --------------------------------------------------------------------


class Request(respository.Request, HeadersRequire):
    '''
    The request context.
    '''
    # ---------------------------------------------------------------- Defined
    match = defines(Context, doc='''
    @rtype: Context
    The error match in case of failure.
    ''')
    # ---------------------------------------------------------------- Required
    method = requires(str)
    uri = requires(str)

# --------------------------------------------------------------------

@injected
class GatewayAuthorizedRepositoryHandler(GatewayRepositoryHandler):
    '''
    Extension for @see: GatewayRepositoryHandler that provides the service for authorized gateways.
    '''
    
    nameAuthorization = 'Authorization'
    # The header name for the session identifier.
    gateway_check_session_active = 'api/Security/Login/%s/SessionActive'; wire.config('gateway_check_session_active', doc='''
            The gateway URI to check if the authorized Gateway is still active, this URI needs to have a marker '%s' where the actual authentication code will be placed
            ''')
    
    def __init__(self):
        assert isinstance(self.nameAuthorization, str), 'Invalid authorization name %s' % self.nameAuthorization
        super().__init__()
        
        self._timeOut = timedelta(seconds=self.cleanupInterval)

    def process(self, chain, request:Request, response:Response, Gateway:Context, Match:Context, **keyargs):
        '''
        @see: HandlerBranching.process
        
        Obtains the repository.
        '''
        assert isinstance(request, Request), 'Invalid request %s' % request
        assert isinstance(response, Response), 'Invalid response %s' % response
        if response.isSuccess is False: return  # Skip in case the response is in error
        
        authentication = AUTHORIZATION.fetch(request)
        if not authentication:
            return
        
        repository = self._repositories.get(authentication)
        if repository is None:
            jobj, error = self.requesterGetJSON.request(self.uri % quote(authentication), details=True)
            if jobj is None:
                BAD_GATEWAY.set(response)
                response.text = error.text
                return
                
            repository = Repository(request.clientIP, [self.populate(Identifier(Gateway()), obj)
                                                       for obj in jobj['collection']], Match)
            self._repositories[authentication] = repository
        else:
            jobj, error = self.requesterGetJSON.request(self.gateway_check_session_active % quote(authentication), details=True)
            if not jobj['collection']:
                UNAUTHORIZED_ACCESS.set(response)
                request.match = request.repository.find(request.method, request.headers, request.uri, UNAUTHORIZED_ACCESS.status)
                response.text = error.text
                self._repositories.pop(authentication, None)
                self._lastAccess.pop(authentication, None)
                return

        self._lastAccess[authentication] = datetime.now()
        
        if request.repository: request.repository = RepositoryJoined(repository, request.repository)
        else: request.repository = repository
    
    # ----------------------------------------------------------------
    
    def initialize(self):
        '''
        @see: GatewayRepositoryHandler.initialize
        '''
        self._repositories = {}
        self._lastAccess = {}
