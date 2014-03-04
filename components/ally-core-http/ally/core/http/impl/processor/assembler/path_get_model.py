'''
Created on May 31, 2013

@package: ally core http
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Finds all get model invokers accessible from a node.
'''

from ally.api.operator.type import TypeProperty, TypeModel
from ally.design.processor.attribute import requires, defines
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from ally.http.spec.server import HTTP_GET, HTTP_POST, HTTP_PUT
from collections import deque

# --------------------------------------------------------------------

class Register(Context):
    '''
    The register context.
    '''
    # ---------------------------------------------------------------- Required
    invokers = requires(list)
    root = requires(Context)
    
class Invoker(Context):
    '''
    The invoker context.
    '''
    # ---------------------------------------------------------------- Defined
    invokerGet = defines(Context, doc='''
    @rtype: Context
    The invoker used for getting the target model.
    ''')
    # ---------------------------------------------------------------- Required
    node = requires(Context)
    isCollection = requires(bool)
    isModel = requires(bool)
    target = requires(TypeModel)
    path = requires(list)

class Element(Context):
    '''
    The element context.
    '''
    # ---------------------------------------------------------------- Required
    property = requires(TypeProperty)
    
class Node(Context):
    '''
    The node context.
    '''
    # ---------------------------------------------------------------- Defined
    invokersGet = defines(dict, doc='''
    @rtype: dictionary{TypeProperty: Context}
    The invokers contexts that can be used to get a model by a property model indexed by the property model that makes
    the invoker accessible based on the current node.
    ''')
    invokersPost = defines(dict, doc='''
    @rtype: dictionary{TypeModel: Context}
    The invokers contexts that can be used to insert a model indexed by the model received as input by the invoker.
    ''')
    invokersPut = defines(dict, doc='''
    @rtype: dictionary{TypeModel: Context}
    The invokers contexts that can be used to update a model indexed by the model received as input by the invoker.
    ''')
    # ---------------------------------------------------------------- Required
    child = requires(Context)
    childByName = requires(dict)
    invokers = requires(dict)
    
# --------------------------------------------------------------------

class PathGetModelHandler(HandlerProcessor):
    '''
    Implementation for a processor that provides all get model invokers accessible from a node.
    '''
    
    def __init__(self):
        super().__init__(Invoker=Invoker, Element=Element, Node=Node)

    def process(self, chain, register:Register, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Provides the accessible get model invokers.
        '''
        assert isinstance(register, Register), 'Invalid register %s' % register
        if register.root is None: return  # No root context to process
        
        # We get all the nodes
        stack, nstack = deque(), deque()
        stack.append((register.root, {}, {}, {}))
        while stack:
            current, invokersGet, invokersPost, invokersPut = stack.popleft()
            nstack.append(current)
            current.invokersGet, current.invokersPost, current.invokersPut = dict(invokersGet), dict(invokersPost), dict(invokersPut)
            while nstack:
                node = nstack.popleft()
                assert isinstance(node, Node), 'Invalid node %s' % node
                
                if node.childByName:
                    nstack.extend(node.childByName.values())
                    stack.extend((nod, current.invokersGet, current.invokersPost, current.invokersPut)
                                 for nod in node.childByName.values())
                    
                    for cnode in node.childByName.values():
                        if cnode.invokers and cnode.invokers.get(HTTP_POST):
                            invoker = cnode.invokers.get(HTTP_POST)
                            assert isinstance(invoker, Invoker), 'Invalid invoker %s' % invoker
                            if invoker.target:
                                assert isinstance(invoker.target, TypeModel)
                                current.invokersPost[invoker.target] = invoker
                elif node.child:
                    assert isinstance(node.child, Node), 'Invalid node %s' % node.child
                    if not node.child.invokers: continue  # Not invokers available for node
                    for method, invokers, propKey in ((HTTP_GET, current.invokersGet, True), (HTTP_PUT, current.invokersPut, False)):
                        invoker = node.child.invokers.get(method)
                        if not invoker: continue
                        assert isinstance(invoker, Invoker), 'Invalid invoker %s' % invoker
                        # Is a collection or is not a model so it cannot be used
                        if invoker.isCollection or not invoker.isModel or not invoker.target: continue
                        assert isinstance(invoker.target, TypeModel), 'Invalid target %s' % invoker.target
                        
                        for el in reversed(invoker.path):
                            assert isinstance(el, Element), 'Invalid element %s' % el
                            if not el.property: continue
                            assert isinstance(el.property, TypeProperty), 'Invalid element property %s' % el.property
                            if el.property.parent == invoker.target:
                                if propKey: invokers[el.property] = invoker
                                else: invokers[el.property.parent] = invoker
                            break
                    stack.append((node.child, current.invokersGet, current.invokersPost, current.invokersPut))
        
        for invoker in register.invokers:
            assert isinstance(invoker, Invoker), 'Invalid invoker %s' % invoker
            if not invoker.target: continue
            assert isinstance(invoker.target, TypeModel), 'Invalid target %s' % invoker.target
            if not invoker.target.propertyId: continue  # No property id for path
            if not invoker.node: continue
            assert isinstance(invoker.node, Node), 'Invalid node %s' % invoker.node
            if not invoker.node.invokersGet: continue
            
            invoker.invokerGet = invoker.node.invokersGet.get(invoker.target.propertyId)
