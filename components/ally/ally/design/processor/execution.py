'''
Created on Feb 11, 2013

@package: ally base
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Contains the classes used in the execution of processors.
'''

from .spec import ContextMetaClass, isNameForClass
from ally.support.util_sys import locationStack
from collections import Iterable, deque
import itertools
import logging

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

CONSUMED = 'chain consumed'  # Flag indicating if the chain is consumed.
CANCELED = 'chain canceled'  # Flag indicating if the chain is canceled.
EXCEPTION = 'exception in chain'  # Flag indicating if the chain is in exception.
FLAGS_STATUS = frozenset((CONSUMED, CANCELED, EXCEPTION))  # All the status flags.

FILL_CLASSES = 'fill in chain classes' 
# Flag indicating if the chain should fill in the classes, is done only if the context name start with a capital letter
# then the class is provided as a value
FILL_VALUES = 'fill in chain values' 
# Flag indicating if the chain should fill in the values, is done only if the context names starts with a lower case
# then an instance is created for the class and used as a value.
FILL_ALL = 'fill all in chain'  # Flag indicating if the chain should fill in the values and classes.
FLAGS_FILL = frozenset((FILL_CLASSES, FILL_VALUES, FILL_ALL))  # All the fill flags.

# --------------------------------------------------------------------

class Abort(Exception):
    '''
    Known exception that triggers a controlled abort of the execution.
    '''
    
    def __init__(self, *reasons):
        '''
        Creates the abort exception.
        
        @param reasons: argument[object]
            The abort reasons.
        '''
        super().__init__()
        self.reasons = list(reasons)
        
    def add(self, *reasons):
        '''
        Adds new reasons for the abort.
        
        @param reasons: argument[object]
            The abort reasons.
        @return: self
            The same exception instance for rerasing.
        '''
        assert reasons, 'At least a reason is required'
        self.reasons.extend(reasons)
        return self

# --------------------------------------------------------------------

class Processing:
    '''
    Container for processor's, provides chains for their execution.
    !!! Attention, never ever use a processing in multiple threads, only one thread is allowed to execute 
    a processing at one time.
    '''

    class Ctx:
        '''
        Provides the contexts proxy for an easier access.
        '''
        if __debug__:
            def __setattr__(self, key, clazz):
                assert isinstance(key, str), 'Invalid context name %s' % key
                assert not key.startswith('_'), 'The context name \'%s\' cannot start with an _' % key
                assert isinstance(clazz, ContextMetaClass), 'Invalid context class %s for %s' % (clazz, key)
                object.__setattr__(self, key, clazz)

    def __init__(self, calls, contexts=None):
        '''
        Construct the processing.
        
        @param calls: Iterable(callable)
            The iterable of calls that consists this processing.
        @param contexts: dictionary{string, ContextMetaClass}|None
            The initial contexts to be associated.
        '''
        assert isinstance(calls, Iterable), 'Invalid calls %s' % calls
        
        self._calls = list(calls)
        assert self._calls, 'At least one call is required for processing'
        if __debug__:
            for call in self._calls: assert callable(call), 'Invalid call %s' % call
                
        self.ctx = Processing.Ctx()
        if contexts:
            assert isinstance(contexts, dict), 'Invalid contexts %s' % contexts
            if __debug__:
                for key, clazz in contexts.items():
                    assert isinstance(key, str), 'Invalid context name %s' % key
                    assert isinstance(clazz, ContextMetaClass), 'Invalid context class %s for %s' % (clazz, key)
            self.ctx.__dict__.update(contexts)
        
    contexts = property(lambda self: self.ctx.__dict__.items(), doc='''
    @rtype: Iterable(tuple(string, Context class))
    The iterable containing key: value pairs of the contained meta classes.
    ''')
    calls = property(lambda self: self._calls, doc='''
    @rtype: Iterable(call)
    The iterable containing the calls of this processing.
    ''')
    
    def update(self, **contexts):
        '''
        Used to update the contexts of the processing.

        @param contexts: dictionary{string, ContextMetaClass}
            The contexts to update with.
        @return: this processing
            This processing for chaining purposes.
        '''
        if __debug__:
            for key, clazz in contexts.items():
                assert isinstance(key, str), 'Invalid context name %s' % key
                assert isinstance(clazz, ContextMetaClass), 'Invalid context class %s for %s' % (clazz, key)
        self.ctx.__dict__.update(contexts)
        return self
    
    def execute(self, *flags, **keyargs):
        '''
        Executes the processing in a chain with the provided arguments.
        
        @param flags: arguments[string]
            The flags to associate the execution with.
        @param keyargs: key arguments
            The key arguments that will be processed.
        @return: object|tuple(boolean, object)
            The chain processed arguments, if any status flag is provided it will return the execution status
            and the processed arguments
        '''
        chain = Chain(self, *flags, **keyargs)
        if not FLAGS_STATUS.isdisjoint(flags):
            ret = chain.execute(*flags)
            return ret, chain.arg
        chain.execute()
        return chain.arg
    
    def wingIn(self, chain, reuse=False, **keyargs):
        '''
        Wings this processor into the provided chain.
        @see: Chain.wing
        
        @param chain: Chain
            The chain to wing in.
        @param reuse: boolean
            Flag indicating that the winged in chain should reuse the arguments from the winging chain that are not provided
            as key arguments.
        @param keyargs: key arguments
            The key arguments that will be processed by the winged chain.
        @return: Chain
            The winged chain.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert isinstance(reuse, bool), 'Invalid reuse flag %s' % reuse
        if reuse:
            for name, value in chain.keyargs:
                if name not in keyargs: keyargs[name] = value
        return chain.wing(Chain(self, False, **keyargs))

# --------------------------------------------------------------------

class Execution:
    '''
    A execution that contains a list of processors (callables) that are executed one by one.
    '''
    __slots__ = ('arg', '_calls', '_status')

    class Arg:
        '''
        Provides the arguments proxy for an easier access.
        '''
        if __debug__:
            def __setattr__(self, key, value):
                assert isinstance(key, str), 'Invalid argument name %s' % key
                assert not key.startswith('__'), 'The argument name \'%s\' cannot start with an \'__\'' % key
                object.__setattr__(self, key, value)

    def __init__(self, processing, arg=None):
        '''
        Initializes the execution with the processing to be executed.
        
        @param processing: Processing|Iterable(callable)|callable
            The processing to be handled by the chain. Attention the order in which the processors are provided
            is critical since one processor is responsible for delegating to the next.
        @param arg: object
            The argument object that are passed to the processors.
        '''
        self._calls = deque()
        self.arg = Execution.Arg() if arg is None else arg
        self._status = None

        if isinstance(processing, Processing):
            assert isinstance(processing, Processing)
            self._calls.extend(processing.calls)
        elif isinstance(processing, Iterable): self._calls.extend(processing)
        else: self._calls.append(processing)
        
        assert self._calls, 'Nothing to execute'
        if __debug__:
            for call in self._calls: assert callable(call), 'Invalid processor call %s' % call

    keyargs = property(lambda self: self.arg.__dict__.items(), doc='''
    @rtype: Iterable(tuple(string, object))
    The iterable containing key: value pairs of the key arguments.
    ''')
    
    def process(self, *args, **keyargs):
        '''
        Called in order to register the arguments to be processed.
        
        @param args: arguments[Execution.Arg|dictionary{string: object}]
        @param keyargs: key arguments
            The key arguments to update the processed arguments with.
        @return: this execution
            This execution for chaining purposes.
        '''
        assert self._status is None, 'Execution cannot process'
        for arg in itertools.chain(args, (keyargs,)):
            if isinstance(arg, Execution.Arg): arg = arg.__dict__
            assert isinstance(arg, dict), 'Invalid argument %s' % arg
            for key, value in arg.items(): setattr(self.arg, key, value)
        return self
    
    def do(self):
        '''
        Called in order to do the next chain element. A *process* method needs to be executed first.
        
        @return: boolean
            True if the chain has performed the execution of the next element, False if there is no more to be executed.
        '''
        while self._calls and isinstance(self._calls[0], Execution):
            if self._calls[0].do(): return True
            self._calls.popleft()
        
        if self._calls and self._status is None:
            call = self._calls.popleft()
            assert log.debug('Processing %s', call) or True
            try: call(self, **self.arg.__dict__)
            except Exception as e:
                if isinstance(e, TypeError) and 'arguments' in str(e):
                    raise TypeError('A problem occurred while invoking with arguments %s, at:%s' % 
                                    (', '.join(self.arg.__dict__), locationStack(call)))

                self._status = EXCEPTION
                if self._handleError(e): return True
                raise
            assert log.debug('Processing finalized \'%s\'', call) or True
            
        if self._status is None:
            if self._calls: return True
            self._status = CONSUMED
        if self._handleFinalization(): return True
        return False
    
    def execute(self, *flags):
        '''
        Executes the remaining processes using and returns True for the provided flags, otherwise return False.
        
        @param flags: arguments[string]
            Flags dictating when this method should return True.
        @return: boolean
            False if if one of the provided flags matches the execution, True otherwise.
        '''
        while True:
            if not self.do(): break
            
        if flags and self._status in flags: return True
        return False
    
    # ----------------------------------------------------------------
    
    def _handleError(self, exception):
        '''
        Handles the error that occurred while executing.
        !!! For internal use only.
        
        @param exception: Exception
            The exception that occurred.
        @return: boolean
            True if the error was handled and the error is not required to be propagated, False otherwise.
        '''
        return False
    
    def _handleFinalization(self):
        '''
        Handles the finalization for execution.
        !!! For internal use only.
        
        @return: boolean
            True if the finalization was handled and the chain should continue execution.
        '''
        return False
        
class Chain(Execution):
    '''
    A chain that contains a list of processors (callables) that are executed one by one.
    '''
    __slots__ = ('_errors', '_finalizers')

    def __init__(self, processing, *fill, **keyargs):
        '''
        Initializes the chain with the processing to be executed.
        @see: Execution.__init__
        
        @param fill: arguments[string]
            The fill in flags indicating the chain fill in. The fill in 
            process is done when a context name is not present in the provided arguments, the value added is being as follows:
                - if the context name start with a capital letter then the class is provided as a value
                - if the context names starts with a lower case then an instance is created for the class and used as a value.
        @param keyargs: key arguments
            The key arguments that will be processed.
        '''
        super().__init__(processing, arg=keyargs.pop('_arg', None))
        self._errors = []
        self._finalizers = []
        
        if fill:
            assert isinstance(processing, Processing), 'Invalid processing %s for fill in' % processing
            fillClasses, fillValues = FILL_CLASSES in fill, FILL_VALUES in fill
            if FILL_ALL in fill: fillClasses = fillValues = True
            for name, clazz in processing.contexts:
                if name not in keyargs and not name in self.arg.__dict__:
                    if isNameForClass(name):
                        if fillClasses: keyargs[name] = clazz
                    elif fillValues: keyargs[name] = clazz()
        
        if keyargs: self.process(**keyargs)
    
    def wing(self, chain):
        '''
        Adds a wing chain to be processed in this chain and automatically the chain will execute the wing as being part
        of this chain.
        !!! Attention if multiple wings are added in one go, then the last wing added will be the first executed.
        
        @param chain: Chain
            The chain to wing.
        @return: Chain
            The same wing chain.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert self._status is None, 'Execution cannot wing'
        assert chain._status is None, 'Execution cannot wing to %s' % chain
        self._calls.appendleft(chain)
        return chain
    
    def branch(self, processing):
        '''
        Create a branching chain that uses the same arguments as this chain and automatically the chain will execute the
        branching as being part of this chain.
        !!! Attention if multiple branches are added in one go, then the last branch added will be the first executed.
        
        @param processing: Processing|Iterable(callable)|callable
            The processing to be handled by the chain. Attention the order in which the processors are provided
            is critical since one processor is responsible for delegating to the next.
        @return: Chain
            The branching chain.
        '''
        assert self._status is None, 'Execution cannot branch'
        bchain = Chain(processing, False, _arg=self.arg)
        self._calls.appendleft(bchain)
        return bchain
    
    def route(self, processing):
        '''
        Route this chain on the provided processing, this means that any processing from this chain that has not
        been done they will be ignored.
        
        @param processing: Processing|Iterable(callable)|callable
            The processing to be handled by the chain. Attention the order in which the processors are provided
            is critical since one processor is responsible for delegating to the next.
        @return: this chain
            This chain for chaining purposes.
        '''
        assert self._status is None, 'Execution cannot route'
        self._calls.clear()
        
        if isinstance(processing, Processing):
            assert isinstance(processing, Processing)
            self._calls.extend(processing.calls)
        elif isinstance(processing, Iterable): self._calls.extend(processing)
        else: self._calls.append(processing)
        
        assert self._calls, 'Nothing to execute'
        if __debug__:
            for call in self._calls: assert callable(call), 'Invalid processor call %s' % call
            
        return self
     
    def cancel(self):
        '''
        Cancels the execution of this chain.
        '''
        if self._status is None:
            self._calls.clear()
            self._status = CANCELED
        
    def onError(self, processing):
        '''
        Register for chain error the provided processing calls. The error processing will be called every time an error
        occurs in this chain processing.
        
        @param processing: Processing|Iterable(callable)|callable
            The processing to be handled at the chain finalization. Attention the order in which the processors are provided
            is critical since one processor is responsible for delegating to the next.
        '''
        assert self._status is None, 'Execution cannot be altered'
        if isinstance(processing, Processing):
            assert isinstance(processing, Processing)
            self._errors.extend(processing.calls)
        elif isinstance(processing, Iterable): self._errors.extend(processing)
        else: self._errors.append(processing)
        if __debug__:
            for call in self._errors: assert callable(call), 'Invalid processor call %s' % call
       
    def onFinalize(self, processing):
        '''
        Register for chain finalization the provided processing calls. The finalization will be called only once when
        the chain is considered done.
        
        @param processing: Processing|Iterable(callable)|callable
            The processing to be handled at the chain finalization. Attention the order in which the processors are provided
            is critical since one processor is responsible for delegating to the next.
        '''
        assert self._status is None, 'Execution cannot be altered'
        if isinstance(processing, Processing):
            assert isinstance(processing, Processing)
            self._finalizers.extend(processing.calls)
        elif isinstance(processing, Iterable): self._finalizers.extend(processing)
        else: self._finalizers.append(processing)
        if __debug__:
            for call in self._finalizers: assert callable(call), 'Invalid processor call %s' % call
            
    # ----------------------------------------------------------------
    
    def _handleError(self, exception):
        '''
        @see: Execution._handleError
        '''
        if not self._errors: return False
        assert log.debug('Started error chain') or True
        error = Error(self, exception)
        error.execute()
        if not error.isSuppressed:
            self._calls.clear()
            if self._handleFinalization(): self.execute()
            raise error.exception
        return True
    
    def _handleFinalization(self):
        '''
        @see: Execution._handleFinalization
        '''
        if not self._finalizers: return False
        assert log.debug('Started finalization chain') or True
        self._finalizers.reverse()  # We need to reverse in order to start the finalization with the last registered.
        self._calls.appendleft(Execution(self._finalizers, self.arg))
        self._finalizers = None
        return True
        
class Error(Execution):
    '''
    A execution that contains a list of processors (callables) that are executed one by one that targets and error processing.
    '''
    __slots__ = ('chain', 'exception', '_retrying', '_suppressed')
    
    def __init__(self, chain, exception):
        '''
        Initializes the error execution with the processing to be executed.
        
        @param chain: Chain
            The chain that has the error. 
        @param exception: Exception
            The exception that generated the error.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert isinstance(exception, Exception), 'Invalid exception %s' % exception
        super().__init__(reversed(chain._errors), chain.arg)
        
        self.chain = chain
        self.exception = exception
        self._suppressed = False
        self._retrying = False
    
    isSuppressed = property(lambda self: self._suppressed, doc='''
    @rtype: boolean
    True if the error should be suppressed.
    ''')
    isRetrying = property(lambda self: self._retrying, doc='''
    @rtype: boolean
    True if the error chained will retry execution.
    ''')
    
    def suppress(self):
        '''
        Suppress the exception so it should not be propagated.
        '''
        self._suppressed = True
        
    def retry(self):
        '''
        Retries to execute the chain where it left of after an exception occurred.
        '''
        if not self._retrying:
            self._suppressed = True
            self._retrying = True
            self.chain._status = None
            
