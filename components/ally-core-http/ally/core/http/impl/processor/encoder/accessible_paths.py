'''
Created on Mar 18, 2013

@package: ally core http
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the accessible paths for a model.
'''

from ally.api.operator.type import TypeModel
from ally.container.ioc import injected
from ally.core.http.impl.index import NAME_BLOCK_REST, ACTION_REFERENCE
from ally.core.spec.transform import ITransfrom, IRender
from ally.design.processor.attribute import requires, defines
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from ally.support.util import firstOf
from ally.support.util_sys import locationStack
from collections import OrderedDict
import logging
from ally.support.util_spec import IDo

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class Node(Context):
    '''
    The node context.
    '''
    # ---------------------------------------------------------------- Required
    invokersAccessible = requires(list)
    
class Invoker(Context):
    '''
    The invoker context.
    '''
    # ---------------------------------------------------------------- Required
    target = requires(TypeModel)
    doEncodePath = requires(IDo)

class Create(Context):
    '''
    The create encoder context.
    '''
    # ---------------------------------------------------------------- Defined
    encoder = defines(ITransfrom, doc='''
    @rtype: ITransfrom
    The encoder for the accessible paths.
    ''')
    
# --------------------------------------------------------------------

@injected
class AccessiblePathEncode(HandlerProcessor):
    '''
    Implementation for a handler that provides the accessible paths encoding.
    '''
    
    nameRef = 'href'
    # The reference attribute name.
    
    def __init__(self):
        assert isinstance(self.nameRef, str), 'Invalid reference name %s' % self.nameRef
        super().__init__()
        
    def process(self, chain, node:Node, invoker:Invoker, create:Create, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Create the accesible path encoder.
        '''
        assert isinstance(node, Node), 'Invalid node %s' % node
        assert isinstance(invoker, Invoker), 'Invalid invoker %s' % invoker
        assert isinstance(create, Create), 'Invalid create %s' % create
        
        if not node.invokersAccessible: return  # No accessible paths
        if not invoker.target: return  # No target available
        if create.encoder is not None: return  # There is already an encoder, nothing to do.
        assert isinstance(invoker.target, TypeModel), 'Invalid target %s' % invoker.target
        
        accessible = []
        for name, ainvoker in node.invokersAccessible:
            assert isinstance(ainvoker, Invoker), 'Invalid invoker %s' % ainvoker
            
            corrupted = False
            for pname in ainvoker.target.properties:
                if pname.startswith(ainvoker.target.name):
                    log.error('Illegal property name \'%s\', is not allowed to start with the model name, at:%s',
                              pname, locationStack(ainvoker.target.clazz))
                    corrupted = True
                    break
                
            if corrupted: continue

            accessible.append(('%s%s' % (invoker.target.name, name), ainvoker))
        accessible.sort(key=firstOf)
        create.encoder = EncoderAccessiblePath(self.nameRef, OrderedDict(accessible))
        
# --------------------------------------------------------------------

class EncoderAccessiblePath(ITransfrom):
    '''
    Implementation for a @see: ITransfrom for model paths.
    '''
    
    def __init__(self, nameRef, accessible):
        '''
        Construct the model paths encoder.
        '''
        assert isinstance(nameRef, str), 'Invalid reference name %s' % nameRef
        assert isinstance(accessible, OrderedDict) and accessible, 'Invalid accessible invokers %s' % accessible
        
        self.nameRef = nameRef
        self.accessible = accessible
    
    def transform(self, value, target, support):
        '''
        @see: ITransfrom.transform
        '''
        assert isinstance(target, IRender), 'Invalid target %s' % target

        indexes = dict(indexBlock=NAME_BLOCK_REST, indexAttributesCapture={self.nameRef: ACTION_REFERENCE})
        for name, invoker in self.accessible.items():
            assert isinstance(invoker, Invoker), 'Invalid invoker %s' % invoker
            assert isinstance(invoker.doEncodePath, IDo), 'Invalid path encode %s' % invoker.doEncodePath
            target.beginObject(name, attributes={self.nameRef: invoker.doEncodePath(support)}, **indexes).end()
