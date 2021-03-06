""" File catalog client for the LFC service combined with multiple read-only mirrors """

import DIRAC
from DIRAC                                              import gLogger, gConfig, S_OK, S_ERROR
from DIRAC.Resources.Catalog.LcgFileCatalogClient       import LcgFileCatalogClient
from DIRAC.Core.Utilities.Subprocess                    import pythonCall
from DIRAC.Core.Utilities.ResolveCatalog                import getLocationOrderedCatalogs
import random, time,os

class LcgFileCatalogCombinedClient:

  ro_methods = ['exists','isLink','readLink','isFile','getFileMetadata','getReplicas',
                'getReplicaStatus','getFileSize','isDirectory','getDirectoryReplicas',
                'listDirectory','getDirectoryMetadata','getDirectorySize','getDirectoryContents',
                'resolveDataset','getPathPermissions','getLFNForPFN']

  write_methods = ['createLink','removeLink','addFile','addReplica','removeReplica',
                   'removeFile','setReplicaStatus','setReplicaHost','createDirectory',
                   'removeDirectory','removeDataset','removeFileFromDataset','createDataset']

  def __init__(self, infosys=None, master_host=None, mirrors = []):
    """ Default constructor
    """
    if not infosys:
      configPath = '/Resources/FileCatalogs/LcgFileCatalogCombined/LcgGfalInfosys'
      infosys = gConfig.getValue(configPath)

    self.valid = False
    if not master_host:
      configPath = '/Resources/FileCatalogs/LcgFileCatalogCombined/MasterHost'
      master_host = gConfig.getValue(configPath)
    if master_host:
      # Create the master LFC client first
      self.lfc = LcgFileCatalogClient(infosys,master_host)
      if self.lfc.isOK():
        self.valid = True

      if not mirrors:
        siteName = DIRAC.siteName()
        res = getLocationOrderedCatalogs(siteName=siteName)
        if not res['OK']:
          mirrors = []
        else:
          mirrors = res['Value']
      # Create the mirror LFC instances
      self.mirrors = []
      for mirror in mirrors:
        lfc = LcgFileCatalogClient(infosys,mirror)
        self.mirrors.append(lfc)
      self.nmirrors = len(self.mirrors)

      # Keep the environment for the master instance
      self.master_host = self.lfc.host
      os.environ['LFC_HOST'] = self.master_host
      os.environ['LCG_GFAL_INFOSYS'] = infosys
      self.name = 'LFC'
      self.timeout = 3000

  def isOK(self):
    return self.valid

  def getName(self,DN=''):
    """ Get the file catalog type name
    """
    return self.name

  def __getattr__(self, name):
    self.call = name
    if name in LcgFileCatalogCombinedClient.write_methods:
      return self.w_execute
    elif name in LcgFileCatalogCombinedClient.ro_methods:
      return self.r_execute
    else:
      raise AttributeError

  def w_execute(self, *parms, **kws):
    """ Write method executor.
        Dispatches execution of the methods which need Read/Write
        access to the master LFC instance
    """

    # If the DN argument is given, this is an operation on behalf
    # of the user with this DN, prepare setAuthorizationId call
    userDN = ''
    if kws.has_key('DN'):
      userDN = kws['DN']
      del kws['DN']

    # Try the method 3 times just in case of intermittent errors
    max_retry = 2
    count = 0
    result = S_ERROR()

    while (not result['OK']) and (count <= max_retry):
      if count > 0:
        # If retrying, wait a bit
        time.sleep(1)
      try:
        result = S_OK()
        if userDN:
          resAuth = pythonCall(self.timeout,self.lfc.setAuthorizationId,userDN)
          if not resAuth['OK']:
            result = S_ERROR('Failed to set user authorization')
        if result['OK']:
          method = getattr(self.lfc,self.call)
          resMeth = method(*parms,**kws)
          if not resMeth['OK']:
            return resMeth
          else:
            result = resMeth
      except Exception,x:
        gLogger.exception('Exception while calling LFC Master service','',x)
        result = S_ERROR('Exception while calling LFC Master service '+str(x))
      count += 1
    return result

  def r_execute(self, *parms, **kws):
    """ Read-only method executor.
        Dispatches execution of the methods which need Read-only
        access to the mirror LFC instances
    """

    # If the DN argument is given, this is an operation on behalf
    # of the user with this DN, prepare setAuthorizationId call
    userDN = ''
    if kws.has_key('DN'):
      userDN = kws['DN']
      del kws['DN']

    result = S_ERROR()
    # Try the method 3 times just in case of intermittent errors
    max_retry = 2
    count = 0

    while (not result['OK']) and (count <= max_retry):
      i = 0
      while not result['OK'] and i < self.nmirrors:
        # Switch environment to the mirror instance
        os.environ['LFC_HOST'] = self.mirrors[i].host
        try:
          result = S_OK()
          if userDN:
            resAuth = pythonCall(self.timeout,self.mirrors[i].setAuthorizationId,userDN)
            if not resAuth['OK']:
              result = S_ERROR('Failed to set user authorization')
          if result['OK']:
            method = getattr(self.mirrors[i],self.call)
            resMeth = method(*parms,**kws)
            if not resMeth['OK']:
              return resMeth
            else:
              result = resMeth
        except Exception,x:
          gLogger.exception('Exception while calling LFC Mirror service')
          result = S_ERROR('Exception while calling LFC Mirror service '+str(x))
        i += 1
      count += 1

    # Return environment to the master LFC instance
    os.environ['LFC_HOST'] = self.master_host

    # Call the master LFC if all the mirrors failed
    if not result['OK']:
      try:
        result = S_OK()
        if userDN:
          resAuth = pythonCall(self.timeout,self.lfc.setAuthorizationId,userDN)
          if not resAuth['OK']:
            result = S_ERROR('Failed to set user authorization')
        if result['OK']:
          method = getattr(self.lfc,self.call)
          resMeth = method(*parms,**kws)
          if not resMeth['OK']:
            result = S_ERROR('Timout calling '+self.call+" method")
          else:
            result = resMeth
      except Exception,x:
        gLogger.exception('Exception while calling LFC Master service')
        result = S_ERROR('Exception while calling LFC Master service '+str(x))

    return result
