'''
Created on Feb 11, 2013

@package: ally base
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Module containing processors.
'''

from .branch import IBranch
from .context import Context, create
from .execution import Processing
from .resolvers import checkIf, reportFor, merge, solve, resolverFor, \
    resolversFor, extractContexts
from .spec import AssemblyError, IProcessor, ContextMetaClass, ProcessorError, \
    IReport, IResolver, LIST_UNAVAILABLE
from .structure import restructureData, restructureResolvers
from ally.design.processor.spec import isNameForClass
from ally.support.util_sys import locationStack, updateWrapper
from collections import Iterable
from inspect import ismethod, isfunction, getfullargspec
import itertools

# --------------------------------------------------------------------

class Processor(IProcessor):
    '''
    Implementation for @see: IProcessor that takes as the call a function and uses the annotations on the function arguments 
    to extract the contexts.
    '''
    
    def __init__(self, contexts, call):
        '''
        Construct the processor for the provided context having the provided call.
        
        @param contexts: key arguments of ContextMetaClass or IResolver
            The contexts to be associated with the processor.
        @param call: callable
            The call of the processor.
        '''
        assert isinstance(contexts, dict), 'Invalid contexts %s' % contexts
        assert callable(call), 'Invalid call %s' % call

        self.contexts = resolversFor(contexts)
        self.call = call

    def register(self, sources, resolvers, extensions, calls, report):
        '''
        @see: IProcessor.register
        '''
        assert isinstance(calls, list), 'Invalid calls %s' % calls
        
        merge(resolvers, self.contexts)
        calls.append(self.call)
        
    # ----------------------------------------------------------------
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__): return False
        return self.contexts == other.contexts and self.call == other.call

class Contextual(Processor):
    '''
    Implementation for @see: IProcessor that takes as the call a function and uses the annotations on the function arguments 
    to extract the contexts.
    '''

    def __init__(self, function):
        '''
        Constructs a processor based on a function.
        @see: Processor.__init__
        
        @param function: function|method
            The function of the processor with the arguments annotated.
        '''
        assert isfunction(function) or ismethod(function), 'Invalid function %s' % function
        
        self.function = function
        
        fnArgs = getfullargspec(function)
        arguments, annotations = self.processArguments(fnArgs.args, fnArgs.annotations)
        
        assert isinstance(arguments, Iterable), 'Invalid arguments %s' % arguments
        assert isinstance(annotations, dict), 'Invalid annotations %s' % annotations
        contexts = {}
        for name in arguments:
            assert isinstance(name, str), 'Invalid argument name %s' % name
            annot = annotations.get(name)
            if annot is None:
                raise ProcessorError('Context class required for argument %s, at:%s' % (name, locationStack(self.function)))
            if not isinstance(annot, tuple): annot = (annot,)
            if not annot:
                raise ProcessorError('At least one context class is required for argument %s, at:%s' % 
                                     (name, locationStack(self.function)))
            
            context = None
            for clazz in annot:
                if clazz is Context: continue
                if not isinstance(clazz, ContextMetaClass):
                    raise ProcessorError('Not a context class %s for argument %s, at:%s' % 
                                         (clazz, name, locationStack(self.function)))
                if context is None: context = resolverFor(clazz)
                else: context = context.solve(resolverFor(clazz))
            if context is not None: contexts[name] = context
        
        super().__init__(contexts, function)
    
    def register(self, sources, resolvers, extensions, calls, report):
        '''
        @see: IProcessor.register
        '''
        assert isinstance(calls, list), 'Invalid calls %s' % calls
        
        try: merge(resolvers, self.contexts)
        except: raise AssemblyError('Cannot merge contexts at:%s' % locationStack(self.function))
        calls.append(self.call)
        
    # ----------------------------------------------------------------
     
    def processArguments(self, arguments, annotations):
        '''
        Process the context arguments as seen fit.
        
        @param arguments: list[string]|tuple(string)
            The arguments to process.
        @param annotations: dictionary{string, object}
            The annotations to process.
        @return: tuple(list[string], dictionary{string, object})
            A tuple containing the list of processed arguments names and second value the dictionary containing the 
            annotation for arguments.
        '''
        assert isinstance(arguments, (list, tuple)), 'Invalid arguments %s' % arguments
        assert isinstance(annotations, dict), 'Invalid annotations %s' % annotations

        if len(arguments) >= 2 and 'self' == arguments[0] and 'chain' == arguments[1]: return arguments[2:], annotations
        raise ProcessorError('Required function of form \'def processor(self, chain, contex:Context ...)\' for:%s' % 
                             locationStack(self.function))
    
    # ----------------------------------------------------------------
    
    def __str__(self):
        ctxs = '\n'.join(('%s=%s' % item for item in self.contexts.items()))
        if ismethod(self.function):
            return '%s with:\n%s\n, defined at:%s\n, in instance %s' % \
                (self.__class__.__name__, ctxs, locationStack(self.function), self.function.__self__)
        return '%s with:\n%s\n, defined at:%s' % (self.__class__.__name__, ctxs, locationStack(self.function))

# --------------------------------------------------------------------

class Brancher(Contextual):
    '''
    Implementation for @see: IProcessor that provides branching of other processors containers.
    '''
    
    def __init__(self, function, *branches):
        '''
        Construct the branching processor.
        @see: Contextual.__init__
        
        @param branches: arguments[IBranch]
            The branches to use in branching.
        '''
        assert branches, 'At least one branch is required'
        if __debug__:
            for branch in branches: assert isinstance(branch, IBranch), 'Invalid branch %s' % branch
        self.branches = branches
        super().__init__(function)
    
    def register(self, sources, resolvers, extensions, calls, report):
        '''
        @see: IProcessor.register
        '''
        assert isinstance(calls, list), 'Invalid calls %s' % calls
        assert isinstance(report, IReport), 'Invalid report %s' % report
        
        try: merge(resolvers, self.contexts)
        except: raise AssemblyError('Cannot merge contexts at:%s' % locationStack(self.function))
        
        report = report.open('Branching processor at:%s' % locationStack(self.function))
        
        processings = []
        for branch in self.branches:
            assert isinstance(branch, IBranch), 'Invalid branch %s' % branch
            try: processing = branch.process(sources, resolvers, extensions, report)
            except: raise AssemblyError('Cannot create processing at:%s' % locationStack(self.function))
            assert processing is None or isinstance(processing, Processing), 'Invalid processing %s' % processing
            processings.append(processing)
        
        def wrapper(*args, **keyargs): self.call(*itertools.chain(args, processings), **keyargs)
        updateWrapper(wrapper, self.call)
        calls.append(wrapper)
        
    # ----------------------------------------------------------------
        
    def processArguments(self, arguments, annotations):
        '''
        @see: Contextual.processArguments
        '''
        arguments, annotations = super().processArguments(arguments, annotations)
        
        n = len(self.branches)
        if len(arguments) >= n: return arguments[n:], annotations
        raise ProcessorError('Required function of form \'def processor(self, [chain], '
                             'processing, ..., contex:Context ...)\' for:%s' % locationStack(self.function))

# --------------------------------------------------------------------
    
class Composite(IProcessor):
    '''
    Implementation for @see: IProcessor that contains other processors and registeres them as a single processor.
    '''
    
    def __init__(self, *processors):
        '''
        Construct the composite processor based on the provided processors.
        
        @param processors: arguments[IProcessor]
            The processors that need to be unified as one.
        '''
        assert processors, 'At least one processor is required'
        if __debug__:
            for processor in processors: assert isinstance(processor, IProcessor), 'Invalid processor %s' % processor

        self.processors = processors

    def register(self, sources, resolvers, extensions, calls, report):
        '''
        @see: IProcessor.register
        '''
        for processor in self.processors:
            assert isinstance(processor, IProcessor), 'Invalid processor %s' % processor
            processor.register(sources, resolvers, extensions, calls, report)
            
    def finalized(self, sources, resolvers, extensions, report):
        '''
        @see: IProcessor.finalized
        '''
        for processor in self.processors:
            assert isinstance(processor, IProcessor), 'Invalid processor %s' % processor
            processor.finalized(sources, resolvers, extensions, report)
        
    # ----------------------------------------------------------------

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return False
        return self.processors == other.processors

class Renamer(IProcessor):
    '''
    Implementation for @see: IProcessor that renames the context names for the provided processor.
    '''
    
    def __init__(self, processor, *mapping):
        '''
        Construct the processor that renames the context names for the provided processor.
        
        @param processor: IProcessor
            Restructures the provided processor.
        @param mapping: arguments[tuple(string string)]
            The mappings that the renamer needs to make, also the context to be passed along without renaming need to
            be provided as simple names, attention the order in which the context mappings are provided is crucial, examples:
                ('request', 'solicitation')
                    The wrapped processor will receive as the 'request' context the 'solicitation' context.
                ('request', 'solicitation'), ('request', 'response')
                    The wrapped processor will receive as the 'request' context the 'solicitation' and 'response' context.
                ('solicitation', 'request'), ('response', 'request')
                    The wrapped processor will receive as the 'solicitation' and 'response' context the 'request' context.
        '''
        assert isinstance(processor, IProcessor), 'Invalid processor %s' % processor
        assert mapping, 'At least one mapping is required'
        if __debug__:
            for name in mapping: assert isinstance(name, (str, tuple)), 'Invalid current context name %s' % name
        
        self.processor = processor
        self.mapping = mapping

    def register(self, sources, resolvers, extensions, calls, report):
        '''
        @see: IProcessor.register
        '''
        assert isinstance(calls, list), 'Invalid calls %s' % calls
        
        wsources = restructureResolvers(sources, self.mapping)
        wresolvers = restructureResolvers(resolvers, self.mapping)
        wextensions = restructureResolvers(extensions, self.mapping)
        wcalls = []
        self.processor.register(wsources, wresolvers, wextensions, wcalls, report)
        
        merge(resolvers, restructureResolvers(wresolvers, self.mapping, True))
        merge(extensions, restructureResolvers(wextensions, self.mapping, True))
        
        def wrapper(*args, **keyargs):
            keyargs = restructureData(keyargs, self.mapping)
            for call in wcalls: call(*args, **keyargs)
        
        calls.append(wrapper)
        
    def finalized(self, sources, resolvers, extensions, report):
        '''
        @see: IProcessor.finalized
        '''
        wsources = restructureResolvers(sources, self.mapping)
        wresolvers = restructureResolvers(resolvers, self.mapping)
        wextensions = restructureResolvers(extensions, self.mapping)
        
        self.processor.finalized(wsources, wresolvers, wextensions, report)
        
        merge(resolvers, restructureResolvers(wresolvers, self.mapping, True))
        merge(extensions, restructureResolvers(wextensions, self.mapping, True))
        
    # ----------------------------------------------------------------

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return False
        return self.processor == other.processor and self.mapping == other.mapping

class Using(IProcessor):
    '''
    Implementation for @see: IProcessor that makes use of the provided context for the wrapped processors.
    '''
    
    def __init__(self, processor, **contexts):
        '''
        Construct the processor that renames the context names for the provided processor.
        
        @param processor: IProcessor
            Restructures the provided processor.
        @param contexts: key arguments of ContextMetaClass or IResolver
            The contexts to be used.
        '''
        assert isinstance(processor, IProcessor), 'Invalid processor %s' % processor
        assert contexts, 'At least one context is required'
        for name in contexts: assert isNameForClass(name), 'Only classes are allowed for using, invalid name %s' % name
        
        self.processor = processor
        self.contexts = resolversFor(contexts)

    def register(self, sources, resolvers, extensions, calls, report):
        '''
        @see: IProcessor.register
        '''
        assert isinstance(calls, list), 'Invalid calls %s' % calls
        
        names = set(self.contexts)
        if not names.isdisjoint(sources) or not names.isdisjoint(resolvers) or not names.isdisjoint(extensions):
            raise AssemblyError('The names \'%s\' are already present in current assembly' % ', '.join(names))
    
        solve(resolvers, self.contexts)
        wcalls = []
        self.processor.register(sources, resolvers, extensions, wcalls, report)
        
        using = extractContexts(sources, self.contexts)
        solve(using, extractContexts(resolvers, self.contexts))
        solve(using, extractContexts(extensions, self.contexts))
        if checkIf(using, LIST_UNAVAILABLE):
            raise AssemblyError('Using has unavailable attributes:%s' % reportFor(using, LIST_UNAVAILABLE))
        
        report.add(using)
        
        contexts = create(using)
        def wrapper(*args, **keyargs):
            keyargs.update(contexts)
            for call in wcalls: call(*args, **keyargs)
        calls.append(wrapper)
        
    def finalized(self, sources, resolvers, extensions, report):
        '''
        @see: IProcessor.finalized
        '''
        self.processor.finalized(sources, resolvers, extensions, report)
        
    # ----------------------------------------------------------------

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return False
        return self.processor == other.processor and self.mapping == other.mapping
    
class Structure(IProcessor):
    '''
    Implementation for @see: IProcessor that structure into a context other context(s).
    '''
    
    def __init__(self, **mapping):
        '''
        Construct the processor that structures the contexts.
        
        @param mapping: key arguments of string or tuple(string)
            The structure mapping, as a key is considered the target context and as a value is expected either the name
            of another context or tuple of contexts to be pushed in the target context, attention the order is crucial
            since if two or more contexts define the same attribute only the first one will be considered.
        '''
        self.mapping = {}
        for target, names in mapping.items():
            if isinstance(names, str): names = (names,)
            assert isinstance(names, tuple), 'Invalid mapping names %s for %s' % (names, target)
            assert len(names), 'At least one name is required'
            for name in names: assert isinstance(name, str), 'Invalid mapping name %s for %s' % (name, target)
            assert target not in names, 'Target %s cannot be in names %s' % (target, names)
            self.mapping[target] = names

    def register(self, sources, resolvers, extensions, calls, report):
        '''
        @see: IProcessor.register
        '''
        assert isinstance(sources, dict), 'Invalid sources %s' % sources
        assert isinstance(resolvers, dict), 'Invalid resolvers %s' % resolvers
        assert isinstance(extensions, dict), 'Invalid sources %s' % extensions
        
        jextensions = {}
        for target, names in self.mapping.items():
            self._join(target, names, sources, jextensions)
            self._join(target, names, resolvers, jextensions)
            self._join(target, names, extensions, jextensions)
        solve(extensions, jextensions)
    
    def _join(self, target, names, resolvers, extensions):
        '''
        Performs the joining for the target with names on the provided resolvers.
        '''
        tresolver = resolvers.get(target)
        if tresolver is None: return
        assert isinstance(tresolver, IResolver), 'Invalid resolver %s' % tresolver
        resolved = set(tresolver.list())
        for name in names:
            resolver = resolvers.get(name)
            if resolver is None: continue
            assert isinstance(resolver, IResolver), 'Invalid resolver %s' % resolver
            common = resolved.intersection(resolver.list())
            if not common: continue
            resolved.difference_update(common)
            merge(resolvers, {target: resolver.copy(common)})
            solve(extensions, {name: tresolver.copy(common)})
            if not resolved: break
        
    # ----------------------------------------------------------------

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return False
        return self.mapping == other.mapping
