'''
Created on Oct 10, 2013
 
@package: pypi publish
@copyright: 2013 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Cristian Domsa
 
Simple implementation for publishing components/plugins on pypi.
'''
from ally.distribution.util import PYTHON_CLI, SETUP_FILENAME, BUILD_EGG, runCmd
import logging

OFFICIAL_REP = '-r pypi'
REGISTER = 'register'
SOURCE = 'sdist'
BUILD_WIN = 'bdist_wininst'
UPLOAD = 'upload'

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class Publisher:
    
    packagePath = str
    #path to the current package
    packageName = str
    #name of the package
    
    def __init__(self):
        '''
        do nothing
        '''
        
    def publish(self):
        '''
        Register and update a pypi component
        '''
        assert logging.info('*** PUBLISH package *** {0}'.format(self.packageName)) or True
        
        cmd = ' '.join([PYTHON_CLI, SETUP_FILENAME, REGISTER, OFFICIAL_REP, \
                        SOURCE, BUILD_EGG, UPLOAD, OFFICIAL_REP])
        runCmd(self.packagePath, cmd)