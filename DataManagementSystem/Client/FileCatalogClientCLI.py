#!/usr/bin/env python
########################################################################
# $HeadURL$
########################################################################
""" File Catalog Client Command Line Interface. """

__RCSID__ = "$Id$"

import stat
import sys
import cmd
import commands
import os.path
import string
from types  import *
from DIRAC  import gConfig, gLogger, S_OK, S_ERROR
from DIRAC.Core.Security import CS
from DIRAC.Core.Security.ProxyInfo import getProxyInfo
from DIRAC.Core.Utilities.List import uniqueElements
from DIRAC.Interfaces.API.Dirac import Dirac

def int_with_commas(i):
  s = str(i)
  news = ''
  while len(s) > 0:
    news = s[-3:]+","+news
    s = s[:-3] 
  return news[:-1]

class DirectoryListing:
  
  def __init__(self):
    
    self.entries = []
  
  def addFile(self,name,fileDict,numericid):
    """ Pretty print of the file ls output
    """        
    perm = fileDict['Mode']
    date = fileDict['ModificationDate']
    nlinks = fileDict.get('NumberOfLinks',0)
    size = fileDict['Size']
    if fileDict.has_key('Owner'):
      uname = fileDict['Owner']
    elif fileDict.has_key('OwnerDN'):
      result = CS.getUsernameForDN(fileDict['OwnerDN'])
      if result['OK']:
        uname = result['Value']
      else:
        uname = 'unknown' 
    else:
      uname = 'unknown'
    if numericid:
      uname = str(fileDict['UID'])
    if fileDict.has_key('OwnerGroup'):
      gname = fileDict['OwnerGroup']
    elif fileDict.has_key('OwnerRole'):
      groups = CS.getGroupsWithVOMSAttribute('/'+fileDict['OwnerRole'])
      if groups: 
        if len(groups) > 1:
          gname = groups[0]
          default_group = gConfig.getValue('/Registry/DefaultGroup','unknown')
          if default_group in groups:
            gname = default_group
        else:
          gname = groups[0]
      else:
        gname = 'unknown' 
    else:
      gname = 'unknown'     
    if numericid:
      gname = str(fileDict['GID'])
    
    self.entries.append( ('-'+self.__getModeString(perm),nlinks,uname,gname,size,date,name) )
    
  def addDirectory(self,name,dirDict,numericid):
    """ Pretty print of the file ls output
    """    
    perm = dirDict['Mode']
    date = dirDict['ModificationDate']
    nlinks = 0
    size = 0
    if dirDict.has_key('Owner'):
      uname = dirDict['Owner']
    elif dirDict.has_key('OwnerDN'):
      result = CS.getUsernameForDN(dirDict['OwnerDN'])
      if result['OK']:
        uname = result['Value']
      else:
        uname = 'unknown'
    else:
      uname = 'unknown'
    if numericid:
      uname = str(dirDict['UID'])
    if dirDict.has_key('OwnerGroup'):
      gname = dirDict['OwnerGroup']
    elif dirDict.has_key('OwnerRole'):
      groups = CS.getGroupsWithVOMSAttribute('/'+dirDict['OwnerRole'])
      if groups:
        if len(groups) > 1:
          gname = groups[0]
          default_group = gConfig.getValue('/Registry/DefaultGroup','unknown')
          if default_group in groups:
            gname = default_group
        else:
          gname = groups[0]
      else:
        gname = 'unknown'
    if numericid:
      gname = str(dirDict['GID'])
    
    self.entries.append( ('d'+self.__getModeString(perm),nlinks,uname,gname,size,date,name) )  
    
  def __getModeString(self,perm):
    """ Get string representation of the file/directory mode
    """  
    
    pstring = ''
    if perm & stat.S_IRUSR:
      pstring += 'r'
    else:
      pstring += '-'
    if perm & stat.S_IWUSR:
      pstring += 'w'
    else:
      pstring += '-'
    if perm & stat.S_IXUSR:
      pstring += 'x'
    else:
      pstring += '-'    
    if perm & stat.S_IRGRP:
      pstring += 'r'
    else:
      pstring += '-'
    if perm & stat.S_IWGRP:
      pstring += 'w'
    else:
      pstring += '-'
    if perm & stat.S_IXGRP:
      pstring += 'x'
    else:
      pstring += '-'    
    if perm & stat.S_IROTH:
      pstring += 'r'
    else:
      pstring += '-'
    if perm & stat.S_IWOTH:
      pstring += 'w'
    else:
      pstring += '-'
    if perm & stat.S_IXOTH:
      pstring += 'x'
    else:
      pstring += '-'    
      
    return pstring  
  
  def printListing(self,reverse,timeorder):
    """
    """
    if timeorder:
      if reverse:
        self.entries.sort(key=lambda x: x[5]) 
      else:  
        self.entries.sort(key=lambda x: x[5],reverse=True) 
    else:  
      if reverse:
        self.entries.sort(key=lambda x: x[6],reverse=True) 
      else:  
        self.entries.sort(key=lambda x: x[6]) 
        
    # Determine the field widths
    wList = [ 0 for x in range(7) ]
    for d in self.entries:
      for i in range(7):
        if len(str(d[i])) > wList[i]:
          wList[i] = len(str(d[i]))
        
    for e in self.entries:
      print str(e[0]),
      print str(e[1]).rjust(wList[1]),
      print str(e[2]).ljust(wList[2]),
      print str(e[3]).ljust(wList[3]),
      print str(e[4]).rjust(wList[2]),
      print str(e[5]).rjust(wList[3]),
      print str(e[6])
      

class FileCatalogClientCLI(cmd.Cmd):
  """ usage: FileCatalogClientCLI.py xmlrpc-url.

    The URL should use HTTP protocol, and specify a port.  e.g.::

        http://localhost:7777

    This provides a command line interface to the FileCatalog Exported API::

        ls(path) - lists the directory path

    The command line interface to these functions can be listed by typing "help"
    at the prompt.

    Other modules which want access to the FileCatalog API should simply make
    their own internal connection to the XMLRPC server using code like::

        server = xmlrpclib.Server(xmlrpc_url)
        server.exported_function(args)
  """

  intro = """
File Catalog Client $Revision: 1.17 $Date: 
            """

  def __init__(self, client):
    cmd.Cmd.__init__(self)
    self.fc = client
    self.cwd = '/'
    self.prompt = 'FC:'+self.cwd+'> '
    self.previous_cwd = '/'

  def getPath(self,apath):

    if apath.find('/') == 0:
      path = apath
    else:
      path = self.cwd+'/'+apath
      path = path.replace('//','/')

    return os.path.normpath(path)
  
  def do_register(self,args):
    """ Register a record to the File Catalog
    
        usage:
          register file <lfn> <pfn> <size> <SE> [<guid>]  - register new file record in the catalog
          register replica <lfn> <pfn> <SE>   - register new replica in the catalog
    """
    
    argss = args.split()
    option = argss[0]
    del argss[0]
    if option == 'file':
      return self.registerFile(argss)
    elif option == 'pfn' or option == "replica":
      return self.registerReplica(argss)
    else:
      print "Unknown option:",option
  
  def do_add(self,args):
    """ Upload a new file to a SE and register in the File Catalog
    
        usage:
        
          add <lfn> <pfn> <SE> [<guid>] 
    """
    
    # ToDo - adding directories
    
    argss = args.split()
    
    if len(argss) < 3:
      print "Error: unsufficient number of arguments"
    
    lfn = argss[0]
    lfn = self.getPath(lfn)
    pfn = argss[1]
    se = argss[2]
    guid = None
    if len(argss)>3:
      guid = argss[3]
        
    dirac = Dirac()
    result = dirac.addFile(lfn,pfn,se,guid,printOutput=False)
    if not result['OK']:
      print 'Error: %s' %(result['Message'])
    else:
      print "File %s successfully uploaded to the %s SE" % (lfn,se)  
      
  def do_get(self,args):
    """ Download file from grid and store in a local directory
    
        usage:
        
          get <lfn> [<local_directory>] 
    """
    
    argss = args.split()
    lfn = argss[0]
    lfn = self.getPath(lfn)
    dir = ''
    if len(argss)>1:
      dir = argss[1]
        
    dirac = Dirac()
    localCWD = ''
    if dir:
      localCWD = os.getcwd()
      os.chdir(dir)
    result = dirac.getFile(lfn)
    if localCWD:
      os.chdir(localCWD)
      
    if not result['OK']:
      print 'Error: %s' %(result['Message'])
    else:
      print "File %s successfully downloaded" % lfn      

  def do_unregister(self,args):
    """ Unregister records in the File Catalog
    
        usage:
          unregister replica  <lfn> <se>
          unregister file <lfn>
          unregister dir <path>
    """        
    argss = args.split()
    option = argss[0]
    del argss[0]
    if option == 'replica':
      return self.removeReplica(argss)
    elif option == 'file': 
      return self.removeFile(argss)
    elif option == "dir" or option == "directory":
      return self.removeDirectory(argss)    
    else:
      print "Error: illegal option %s" % option
      
  def do_rmreplica(self,args):
    """ Remove LFN replica from the storage and from the File Catalog
    
        usage:
          rmreplica <lfn> <se>
    """        
    argss = args.split()
    lfn = argss[0]
    lfn = self.getPath(lfn)
    print "lfn:",lfn
    se = argss[1]
    try:
      result =  self.fc.setReplicaStatus( {lfn:{'SE':se,'Status':'Trash'}} )
      done = 1
      if result['OK']:
        print "Replica at",se,"moved to Trash Bin"
      else:
        print "Failed to remove replica at",se
        print result['Message']
    except Exception, x:
      print "Error: rmreplica failed with exception: ", x
    
  def do_rm(self,args):
    """ Remove file from the storage and from the File Catalog
    
        usage:
          rm <lfn>
          
        NB: this method is not fully implemented !    
    """  
    # Not yet really implemented
    argss = args.split()
    self.removeFile(argss)
    
  def do_rmdir(self,args):
    """ Remove directory from the storage and from the File Catalog
    
        usage:
          rmdir <path>
          
        NB: this method is not fully implemented !  
    """  
    # Not yet really implemented yet
    argss = args.split()
    self.removeDirectory(argss)  
          
  def removeReplica(self,args):
    """ Remove replica from the catalog
    """          
    
    path = args[0]
    lfn = self.getPath(path)
    print "lfn:",lfn
    rmse = args[1]
    try:
      result =  self.fc.removeReplica( {lfn:{'SE':rmse}} )
      done = 1
      if result['OK']:
        print "Replica at",rmse,"removed from the catalog"
      else:
        print "Failed to remove replica at",rmse
        print result['Message']
    except Exception, x:
      print "Error: rmpfn failed with exception: ", x
      
  def removeFile(self,args):
    """ Remove file from the catalog
    """  
    
    path = args[0]
    lfn = self.getPath(path)
    print "lfn:",lfn
    try:
      result =  self.fc.removeFile(lfn)
      if result['OK']:
        print "File",lfn,"removed from the catalog"
      else:
        print "Failed to remove file from the catalog"  
        print result['Message']
    except Exception, x:
      print "Error: rm failed with exception: ", x       
      
  def removeDirectory(self,args):
    """ Remove file from the catalog
    """  
    
    path = args[0]
    lfn = self.getPath(path)
    print "lfn:",lfn
    try:
      result =  self.fc.removeDirectory(lfn)
      if result['OK']:
        print "Directory",lfn,"removed from the catalog"
      else:
        print "Failed to remove directory from the catalog"  
        print result['Message']
    except Exception, x:
      print "Error: rm failed with exception: ", x            
      
  def do_replicate(self,args):
    """ Replicate a given file to a given SE
        
        usage:
          replicate <LFN> <SE> [<SourceSE>]
    """
    argss = args.split()
    if len(args) < 2:
      print "Error: unsufficient number of arguments"
    lfn = argss[0]
    lfn = self.getPath(lfn)
    se = argss[1]
    sourceSE = ''
    if len(argss)>2:
      sourceSE=argss[2]
    if len(argss)>3: 
      localCache=argss[3]
    try:
      dirac = Dirac()
      result = dirac.replicate(lfn,se,sourceSE,printOutput=True)      
      if not result['OK']:
        print 'Error: %s' %(result['Message'])
      elif not result['Value']:
        print "Replica is already present at the target SE"
      else:  
        print "File %s successfully replicated to the %s SE" % (lfn,se)  
    except Exception, x:
      print "Error: replicate failed with exception: ", x      
      
  def do_replicas(self,args):
    """ Get replicas for the given file specified by its LFN

        usage: replicas <lfn>
    """
    apath = args.split()[0]
    path = self.getPath(apath)
    print "lfn:",path
    try:
      result =  self.fc.getReplicas(path)    
      if result['OK']:
        if result['Value']['Successful']:
          for se,entry in result['Value']['Successful'][path].items():
            print se.ljust(15),entry
      else:
        print "Replicas: ",result['Message']
    except Exception, x:
      print "replicas failed: ", x
        
  def registerFile(self,args):
    """ Add a file to the catatlog 

        usage: add <lfn> <pfn> <size> <SE> [<guid>]
    """      
       
    path = args[0]
    infoDict = {}
    lfn = self.getPath(path)
    infoDict['PFN'] = args[1]
    infoDict['Size'] = int(args[2])
    infoDict['SE'] = args[3]
    if len(args) == 5:
      guid = args[4]
    else:
      status,guid = commands.getstatusoutput('uuidgen')
    infoDict['GUID'] = guid
    infoDict['Checksum'] = ''    
      
    fileDict = {}
    fileDict[lfn] = infoDict  
      
    try:
      result = self.fc.addFile(fileDict)         
      if not result['OK']:
        print "Failed to add file to the catalog: ",
        print result['Message']
      elif result['Value']['Failed']:
        if result['Value']['Failed'].has_key(lfn):
          print 'Failed to add file:',result['Value']['Failed'][lfn]  
      elif result['Value']['Successful']:
        if result['Value']['Successful'].has_key(lfn):
          print "File successfully added to the catalog"    
    except Exception, x:
      print "add file failed: ", str(x)    
    
  def registerReplica(self,args):
    """ Add a file to the catatlog 

        usage: addpfn <lfn> <pfn> <SE> 
    """      
    path = args[0]
    infoDict = {}
    lfn = self.getPath(path)
    infoDict['PFN'] = args[1]
    if infoDict['PFN'] == "''" or infoDict['PFN'] == '""':
      infoDict['PFN'] = ''
    infoDict['SE'] = args[2]
      
    repDict = {}
    repDict[lfn] = infoDict    
      
    try:
      result = self.fc.addReplica(repDict)                    
      if not result['OK']:
        print "Failed to add replica to the catalog: ",
        print result['Message']
      elif result['Value']['Failed']:
        print 'Failed to add replica:',result['Value']['Failed'][lfn]   
      else:
        print "Replica added successfully:", result['Value']['Successful'][lfn]    
    except Exception, x:
      print "add pfn failed: ", str(x)    
      
  def do_ancestorset(self,args):
    """ Set ancestors for the given file
    
        usage: ancestorset <lfn> <ancestor_lfn> [<ancestor_lfn>...]
    """            
    
    argss = args.split()    
    lfn = argss[0]
    if lfn[0] != '/':
      lfn = self.cwd + '/' + lfn
    ancestors = argss[1:]
    tmpList = []
    for a in ancestors:
      if a[0] != '/':
        a = self.cwd + '/' + a
      tmpList.append(a)
    ancestors = tmpList       
    
    try:
      result = self.fc.addFileAncestors({lfn:{'Ancestors':ancestors}})
      if not result['OK']:
        print "Failed to add file ancestors to the catalog: ",
        print result['Message']
      elif result['Value']['Failed']:
        print "Failed to add file ancestors to the catalog: ",
        print result['Value']['Failed'][lfn]
      else:
        print "Added %d ancestors to file %s" % (len(ancestors),lfn)
    except Exception, x:
      print "Exception while adding ancestors: ", str(x)                
                         
      
  def do_ancestor(self,args):
    """ Get ancestors of the given file
    
        usage: ancestor <lfn> [depth]
    """            
    
    argss = args.split()
    lfn = argss[0]
    if lfn[0] != '/':
      lfn = self.cwd + '/' + lfn
    depth = [1]
    if len(argss) > 1:
      depth = int(argss[1])
      depth = range(1,depth+1)
        
    try:      
      result = self.fc.getFileAncestors([lfn],depth)
      if not result['OK']:
        print "ERROR: Failed to get ancestors: ",
        print result['Message']       
      elif result['Value']['Failed']:
        print "Failed to get ancestors: ",
        print result['Value']['Failed'][lfn]
      else:
        depthDict = {}  
        depSet = set()    
        for lfn,ancestorDict in  result['Value']['Successful'].items():
           for ancestor,dep in ancestorDict.items():     
             depthDict.setdefault(dep,[])
             depthDict[dep].append(ancestor)
             depSet.add(dep)
        depList = list(depSet)
        depList.sort()
        print lfn   
        for dep in depList:
          for lfn in depthDict[dep]:      
            print dep,' '*dep*5, lfn
    except Exception, x:
      print "Exception while getting ancestors: ", str(x)    
                                                                     
  def do_descendent(self,args):
    """ Get descendents of the given file
    
        usage: descendent <lfn> [depth]
    """            
    
    argss = args.split()
    lfn = argss[0]
    if lfn[0] != '/':
      lfn = self.cwd + '/' + lfn
    depth = [1]
    if len(argss) > 1:
      depth = int(argss[1])
      depth = range(1,depth+1)
        
    try:
      result = self.fc.getFileDescendents([lfn],depth)
      if not result['OK']:
        print "ERROR: Failed to get descendents: ",
        print result['Message']       
      elif result['Value']['Failed']:
        print "Failed to get descendents: ",
        print result['Value']['Failed'][lfn]
      else:
        depthDict = {}  
        depSet = set()    
        for lfn,descDict in  result['Value']['Successful'].items():
           for desc,dep in descDict.items():     
             depthDict.setdefault(dep,[])
             depthDict[dep].append(desc)
             depSet.add(dep)
        depList = list(depSet)
        depList.sort()
        print lfn   
        for dep in depList:
          for lfn in depthDict[dep]:      
            print dep,' '*dep*5, lfn
    except Exception, x:
      print "Exception while getting descendents: ", str(x)              
      
#######################################################################################
# User and group methods      
      
  def do_user(self,args):
    """ User related commands
    
        usage:
          user add <username>  - register new user in the catalog
          user delete <username>  - delete user from the catalog
          user show - show all users registered in the catalog
    """    
    argss = args.split()
    option = argss[0]
    del argss[0]
    if option == 'add':
      return self.registerUser(argss) 
    elif option == 'delete':
      return self.deleteUser(argss) 
    elif option == "show":
      result = self.fc.getUsers()
      if not result['OK']:
        print ("Error: %s" % result['Message'])            
      else:  
        if not result['Value']:
          print "No entries found"
        else:  
          for user,id in result['Value'].items():
            print user.rjust(20),':',id
    else:
      print "Unknown option:",option
    
  def do_group(self,args):
    """ Group related commands
    
        usage:
          group add <groupname>  - register new group in the catalog
          group delete <groupname>  - delete group from the catalog
          group show - how all groups registered in the catalog
    """    
    argss = args.split()
    option = argss[0]
    del argss[0]
    if option == 'add':
      return self.registerGroup(argss) 
    elif option == 'delete':
      return self.deleteGroup(argss) 
    elif option == "show":
      result = self.fc.getGroups()
      if not result['OK']:
        print ("Error: %s" % result['Message'])            
      else:  
        if not result['Value']:
          print "No entries found"
        else:  
          for user,id in result['Value'].items():
            print user.rjust(20),':',id
    else:
      print "Unknown option:",option  
  
  def registerUser(self,argss):
    """ Add new user to the File Catalog
    
        usage: adduser <user_name>
    """
 
    username = argss[0] 
    
    result =  self.fc.addUser(username)
    if not result['OK']:
      print ("Error: %s" % result['Message'])
    else:
      print "User ID:",result['Value']  
      
  def deleteUser(self,args):
    """ Delete user from the File Catalog
    
        usage: deleteuser <user_name>
    """
 
    username = args[0] 
    
    result =  self.fc.deleteUser(username)
    if not result['OK']:
      print ("Error: %s" % result['Message'])    
      
  def registerGroup(self,argss):
    """ Add new group to the File Catalog
    
        usage: addgroup <group_name>
    """
 
    gname = argss[0] 
    
    result =  self.fc.addGroup(gname)
    if not result['OK']:
      print ("Error: %s" % result['Message'])
    else:
      print "Group ID:",result['Value']    
      
  def deleteGroup(self,args):
    """ Delete group from the File Catalog
    
        usage: deletegroup <group_name>
    """
 
    gname = args[0] 
    
    result =  self.fc.deleteGroup(gname)
    if not result['OK']:
      print ("Error: %s" % result['Message'])         
         
  def do_mkdir(self,args):
    """ Make directory
    
        usage: mkdir <path>
    """
    
    argss = args.split()
    path = argss[0] 
    if path.find('/') == 0:
      newdir = path
    else:
      newdir = self.cwd + '/' + path
      
    newdir = newdir.replace(r'//','/')
    
    result =  self.fc.createDirectory(newdir)    
    if result['OK']:
      if result['Value']['Successful']:
        if result['Value']['Successful'].has_key(newdir):
          print "Successfully created directory:", newdir
      elif result['Value']['Failed']:
        if result['Value']['Failed'].has_key(newdir):  
          print 'Failed to create directory:',result['Value']['Failed'][newdir]
    else:
      print 'Failed to create directory:',result['Message']

  def do_cd(self,args):
    """ Change directory to <path>
    
        usage: cd <path>
               cd -
    """
 
    argss = args.split()
    if len(argss) == 0:
      path = '/'
    else:  
      path = argss[0] 
      
    if path == '-':
      path = self.previous_cwd
      
    newcwd = self.getPath(path)
    if len(newcwd)>1 and not newcwd.find('..') == 0 :
      newcwd=newcwd.rstrip("/")
    
    result =  self.fc.isDirectory(newcwd)        
    if result['OK']:
      if result['Value']['Successful']:
        if result['Value']['Successful'][newcwd]:
        #if result['Type'] == "Directory":
          self.previous_cwd = self.cwd
          self.cwd = newcwd
          self.prompt = 'FC:'+self.cwd+'>'
        else:
          print newcwd,'does not exist or is not a directory'
      else:
        print newcwd,'is not found'
    else:
      print 'Server failed to find the directory',newcwd

  def do_id(self,args):
    """ Get user identity
    """
    result = getProxyInfo()
    if not result['OK']:
      print "Error: %s" % result['Message']
      return
    user = result['Value']['username']
    group = result['Value']['group']
    result = self.fc.getUsers()
    if not result['OK']:
      print "Error: %s" % result['Message']
      return
    userDict = result['Value']
    result = self.fc.getGroups()
    if not result['OK']:
      print "Error: %s" % result['Message']
      return
    groupDict = result['Value']    
    idUser = userDict.get(user,0)
    idGroup = groupDict.get(group,0)
    print "user=%d(%s) group=%d(%s)" % (idUser,user,idGroup,group)
      
  def do_lcd(self,args):
    """ Change local directory
    
        usage:
          lcd <local_directory>
    """    
    localDir = args.split()[0]
    os.chdir(localDir)
    newDir = os.getcwd()
    print "Local directory: %s" % newDir
          
  def do_pwd(self,args):
    """ Print out the current directory
    
        usage: pwd
    """
    print self.cwd      

  def do_ls(self,args):
    """ Lists directory entries at <path> 

        usage: ls [-ltrn] <path>
    """
    
    argss = args.split()
    # Get switches
    long = False
    reverse = False
    timeorder = False
    numericid = False
    path = self.cwd
    if len(argss) > 0:
      if argss[0][0] == '-':
        if 'l' in argss[0]:
          long = True
        if 'r' in  argss[0]:
          reverse = True
        if 't' in argss[0]:
          timeorder = True
        if 'n' in argss[0]:
          numericid = True  
        del argss[0]  
          
      # Get path    
      if argss:        
        path = argss[0]       
        if path[0] != '/':
          path = self.cwd+'/'+path      
    path = path.replace(r'//','/')

    # remove last character if it is "/"    
    if path[-1] == '/' and path != '/':
      path = path[:-1]
    
    # Check if the target path is a file
    result =  self.fc.isFile(path)      
    if not result['OK']:
      print "Error: can not verify path"
      return
    elif result['Value']['Successful'][path]:
      result = self.fc.getFileMetadata(path)
      dList = DirectoryListing()
      fileDict = result['Value']['Successful'][path]
      dList.addFile(os.path.basename(path),fileDict,numericid)
      dList.printListing(reverse,timeorder)
      return         
    
    # Get directory contents now
    try:
      result =  self.fc.listDirectory(path,long)                     
      dList = DirectoryListing()
      if result['OK']:
        if result['Value']['Successful']:
          for entry in result['Value']['Successful'][path]['Files']:
            fname = entry.split('/')[-1]
            # print entry, fname
            # fname = entry.replace(self.cwd,'').replace('/','')
            if long:
              fileDict = result['Value']['Successful'][path]['Files'][entry]['MetaData']
              if fileDict:
                dList.addFile(fname,fileDict,numericid)
            else:  
              print fname
          for entry in result['Value']['Successful'][path]['SubDirs']:
            dname = entry.split('/')[-1]
            # print entry, dname
            # dname = entry.replace(self.cwd,'').replace('/','')  
            if long:
              dirDict = result['Value']['Successful'][path]['SubDirs'][entry]
              if dirDict:
                dList.addDirectory(dname,dirDict,numericid)
            else:    
              print dname
          for entry in result['Value']['Successful'][path]['Links']:
            pass
              
          if long:
            dList.printListing(reverse,timeorder)      
      else:
        print "Error:",result['Message']
    except Exception, x:
      print "Error:", str(x)
      
  def do_chown(self,args):
    """ Change owner of the given path

        usage: chown [-R] <owner> <path> 
    """         
    
    argss = args.split()
    recursive = False
    if argss[0] == '-R':
      recursive = True
      del argss[0]
    owner = argss[0]
    path = argss[1]
    lfn = self.getPath(path)
    pathDict = {}
    pathDict[lfn] = {'Owner':owner}
    
    try:
      result = self.fc.changePathOwner(pathDict,recursive)        
      if not result['OK']:
        print "Error:",result['Message']
        return
      if lfn in result['Value']['Failed']:
        print "Error:",result['Value']['Failed'][lfn]
        return  
    except Exception, x:
      print "Exception:", str(x)         
      
  def do_chgrp(self,args):
    """ Change group of the given path

        usage: chgrp [-R] <group> <path> 
    """         
    
    argss = args.split()
    recursive = False
    if argss[0] == '-R':
      recursive = True
      del argss[0]
    group = argss[0]
    path = argss[1]
    lfn = self.getPath(path)
    pathDict = {}
    pathDict[lfn] = {"Group":group}
    
    try:
      result = self.fc.changePathGroup(pathDict,recursive)         
      if not result['OK']:
        print "Error:",result['Message']
        return
      if lfn in result['Value']['Failed']:
        print "Error:",result['Value']['Failed'][lfn]
        return  
    except Exception, x:
      print "Exception:", str(x)    
      
  def do_chmod(self,args):
    """ Change permissions of the given path
        usage: chmod [-R] <mode> <path> 
    """         
    
    argss = args.split()
    recursive = False
    if argss[0] == '-R':
      recursive = True
      del argss[0]
    mode = argss[0]
    path = argss[1]
    lfn = self.getPath(path)
    pathDict = {}
    # treat mode as octal 
    pathDict[lfn] = {"Mode":eval('0'+mode)}
    
    try:
      result = self.fc.changePathMode(pathDict,recursive)             
      if not result['OK']:
        print "Error:",result['Message']
        return
      if lfn in result['Value']['Failed']:
        print "Error:",result['Value']['Failed'][lfn]
        return  
    except Exception, x:
      print "Exception:", str(x)       
      
  def do_size(self,args):
    """ Get file or directory size. If -l switch is specified, get also the total
        size per Storage Element 

        usage: size [-l] <lfn>|<dir_path> 
    """      
    
    argss = args.split()
    long = False
    if len(argss) > 0:
      if argss[0] == '-l':
        long = True
        del argss[0]
        
    if len(argss) == 1:
      path = argss[0]
      if path == '.':
        path = self.cwd    
    else:
      path = self.cwd
    path = self.getPath(path)
    
    try:
      result = self.fc.isFile(path)
      if not result['OK']:
        print "Error:",result['Message']
      if result['Value']['Successful']:
        if result['Value']['Successful'][path]:  
          print "lfn:",path
          result =  self.fc.getFileSize(path)
          if result['OK']:
            if result['Value']['Successful']:
              print "Size:",result['Value']['Successful'][path]
            else:
              print "File size failed:", result['Value']['Failed'][path]  
          else:
            print "File size failed:",result['Message']
        else:
          print "directory:",path
          result =  self.fc.getDirectorySize(path,long)          
          if result['OK']:
            if result['Value']['Successful']:
              print "Logical Size:",int_with_commas(result['Value']['Successful'][path]['LogicalSize'])
              if long:
                if "PhysicalSize" in result['Value']['Successful'][path]:
                  print "Physical Size:"
                  total = result['Value']['Successful'][path]['PhysicalSize']['Total']
                  for se,size in result['Value']['Successful'][path]['PhysicalSize'].items():
                    if se != "Total":
                      print se.rjust(20),':',int_with_commas(size)
                  print 'Total'.rjust(20),':',int_with_commas(total)   
            else:
              print "Directory size failed:", result['Value']['Failed'][path]
          else:
            print "Directory size failed:",result['Message']  
      else:
        print "Failed to determine path type"        
    except Exception, x:
      print "Size failed: ", x
      
  def do_guid(self,args):
    """ Get the file GUID 

        usage: guid <lfn> 
    """      
    
    path = args.split()[0]
    lfn = self.getPath(path)
    try:
      result =  self.fc.getFileMetadata(path)
      if result['OK']:
        if result['Value']['Successful']:
          print "GUID:",result['Value']['Successful'][path]['GUID']
        else:
          print "ERROR: getting guid failed"  
      else:
        print "ERROR:",result['Message']
    except Exception, x:
      print "guid failed: ", x   
 
##################################################################################
#  Metadata methods
      
  def do_meta(self,args):
    """ Metadata related operation
    
        usage:
          meta index <metaname> <metatype>  - add new metadata index. Possible types are:
                                              'int', 'float', 'string', 'date'
          meta set <directory> <metaname> <metavalue> - set metadata value for directory
          meta get [-e] [<directory>] - get metadata for the given directory
          meta tags <metaname> where <meta_selection> - get values (tags) of the given metaname compatible with 
                                                       the metadata selection
          meta metaset <metaset_name> <key>=<value> [<key>=<value>]
          meta show - show all defined metadata indice

    """     
    argss = args.split()
    option = argss[0]
    del argss[0]
    if option == 'set':
      return self.metaSet(argss)
    elif option == 'get':
      return self.metaGet(argss)  
    elif option[:3] == 'tag':
      return self.metaTag(argss)    
    elif option == 'index':
      return self.registerMeta(argss)
    elif option == 'metaset':
      return self.registerMetaset(argss)
    elif option == 'show':
      return self.showMeta()
    else:
      print "Unknown option:",option  
      
  def __processArgs(self,argss):
    """ Process the list of arguments to capture quoted strings
    """
    
    argString = " ".join(argss)
        
      
  def metaSet(self,argss):
    """ Set metadata value for a directory
    """      
    if len(argss) != 3:
      print "Error: command requires 3 arguments, %d given" % len(argss)
      return
    path = argss[0]
    if path == '.':
      path = self.cwd
    elif path[0] != '/':
      path = self.cwd+'/'+path  
    meta = argss[1]
    value = argss[2]
    print path,meta,value
    metadict = {}
    metadict[meta]=value
    result = self.fc.setMetadata(path,metadict)
    if not result['OK']:
      print ("Error: %s" % result['Message'])     
      
  def metaGet(self,argss):
    """ Get metadata for the given directory
    """            
    expandFlag = False
    dirFlag = True
    if len(argss) == 0:
      path ='.'
    else:  
      if argss[0] == "-e":
        expandFlag = True
        del argss[0]
      if len(argss) == 0:
        path ='.'  
      else:  
        path = argss[0]
        dirFlag = False
    if path == '.':
      path = self.cwd
    elif path[0] != '/':
      path = self.cwd+'/'+path
      
    if not dirFlag:
      # Have to decide if it is a file or not
      result = self.fc.isFile(path)
      if not result['OK']:
        print "ERROR: Failed to contact the catalog"      
      if not result['Value']['Successful']:
        print "ERROR: Path not found"
      dirFlag = not result['Value']['Successful'][path]        
        
    if dirFlag:    
            result = self.fc.getDirectoryMetadata(path)      
            if not result['OK']:
              print ("Error: %s" % result['Message']) 
              return
            if result['Value']:
              metaDict = result['MetadataOwner']
              metaTypeDict = result['MetadataType']
              for meta,value in result['Value'].items():
                setFlag = metaDict[meta] != 'OwnParameter' and metaTypeDict[meta] == "MetaSet"
                prefix = ''
                if setFlag:
                  prefix = "+"
                if metaDict[meta] == 'ParentMetadata':
                  prefix += "*"
                  print (prefix+meta).rjust(20),':',value
                elif metaDict[meta] == 'OwnMetadata':
                  prefix += "!"
                  print (prefix+meta).rjust(20),':',value   
                else:
                  print meta.rjust(20),':',value 
                if setFlag and expandFlag:
                  result = self.fc.getMetadataSet(value,expandFlag)
                  if not result['OK']:
                    print ("Error: %s" % result['Message']) 
                    return
                  for m,v in result['Value'].items():
                    print " "*10,m.rjust(20),':',v      
            else:
              print "No metadata defined for directory"   
    else:
      result = self.fc.getFileUserMetadata(path)      
      if not result['OK']:
        print ("Error: %s" % result['Message']) 
        return
      if result['Value']:      
        for meta,value in result['Value'].items():
          print meta.rjust(20),':', value
      else:
        print "No metadata found"        
      
  def metaTag(self,argss):
    """ Get values of a given metadata tag compatible with the given selection
    """    
    tag =  argss[0]
    del argss[0]
    
    # Evaluate the selection dictionary
    metaDict = {}
    if argss:
      if argss[0].lower() == 'where':
        result = self.fc.getMetadataFields()        
        if not result['OK']:
          print ("Error: %s" % result['Message']) 
          return
        if not result['Value']:
          print "Error: no metadata fields defined"
          return
        typeDict = result['Value']
        
        del argss[0]
        for arg in argss:
          try:
            name,value = arg.split('=')
            if not name in typeDict:
              print "Error: metadata field %s not defined" % name
              return
            mtype = typeDict[name]
            mvalue = value
            if mtype[0:3].lower() == 'int':
              mvalue = int(value)
            if mtype[0:5].lower() == 'float':
              mvalue = float(value)
            metaDict[name] = mvalue
          except Exception,x:
            print "Error:",str(x)
            return  
      else:
        print "Error: WHERE keyword is not found after the metadata tag name"
        return
      
    result = self.fc.getCompatibleMetadata(metaDict)  
    if not result['OK']:
      print ("Error: %s" % result['Message']) 
      return
    tagDict = result['Value']
    if tag in tagDict:
      if tagDict[tag]:
        print "Possible values for %s:" % tag
        for v in tagDict[tag]:
          print v
      else:
        print "No compatible values found for %s" % tag       

  def showMeta(self):
    """ Show defined metadata indices
    """
    result = self.fc.getMetadataFields()  
    if not result['OK']:
      print ("Error: %s" % result['Message'])            
    else:
      if not result['Value']:
        print "No entries found"
      else:  
        for meta,type in result['Value'].items():
          print meta.rjust(20),':',type

  def registerMeta(self,argss):
    """ Add metadata field. 
    """
 
    if len(argss) < 2:
      print "Unsufficient number of arguments"
      return
    mname = argss[0] 
    mtype = argss[1]
    
    if mtype.lower()[:3] == 'int':
      rtype = 'INT'
    elif mtype.lower()[:7] == 'varchar':
      rtype = mtype
    elif mtype.lower() == 'string':
      rtype = 'VARCHAR(128)'
    elif mtype.lower() == 'float':
      rtype = 'FLOAT'  
    elif mtype.lower() == 'date':
      rtype = 'DATETIME'
    elif mtype.lower() == 'metaset':
      rtype = 'MetaSet'  
    else:
      print "Error: illegal metadata type %s" % mtype
      return  
        
    result =  self.fc.addMetadataField(mname,rtype)
    if not result['OK']:
      print ("Error: %s" % result['Message'])
    else:
      print "Added metadata field %s of type %s" % (mname,mtype)        
  
  def registerMetaset(self,argss):
    """ Add metadata set
    """
    
    setDict = {}
    setName = argss[0]
    del argss[0]
    for arg in argss:
      key,value = arg.split('=')
      setDict[key] = value
      
    result =  self.fc.addMetadataSet(setName,setDict)
    if not result['OK']:
      print ("Error: %s" % result['Message'])  
    else:
      print "Added metadata set %s" % setName  
    
  def do_find(self,args):
    """ Find all files satisfying the given metadata information 
    
        usage: find <meta_name>=<meta_value> [<meta_name>=<meta_value>]
    """   
    
    if args[0] == '{':
      metaDict = eval(args)
    else:  
      metaDict = self.__createQuery(args)
      print "Query:",metaDict
          
    result = self.fc.findFilesByMetadata(metaDict)
    if not result['OK']:
      print ("Error: %s" % result['Message']) 
      return 
    for dir in result['Value']:
      print dir  
      
  def __createQuery(self,args):
    """ Create the metadata query out of the command line arguments
    """    
    argss = args.split()
    result = self.fc.getMetadataFields()
    if not result['OK']:
      print ("Error: %s" % result['Message']) 
      return None
    if not result['Value']:
      print "Error: no metadata fields defined"
      return None
    typeDict = result['Value']
    metaDict = {}
    contMode = False
    for arg in argss:
      if not contMode:
        operation = ''
        for op in ['>','<','>=','<=','!=','=']:
          if arg.find(op) != -1:
            operation = op
            break
        if not operation:
          
          print "Error: operation is not found in the query"
          return None
          
        name,value = arg.split(operation)
        if not name in typeDict:
          print "Error: metadata field %s not defined" % name
          return None
        mtype = typeDict[name]
      else:
        value += ' ' + arg
        value = value.replace(contMode,'')
        contMode = False  
      
      if value[0] == '"' or value[0] == "'":
        if value[-1] != '"' and value != "'":
          contMode = value[0]
          continue 
      
      if value.find(',') != -1:
        valueList = [ x.replace("'","").replace('"','') for x in value.split(',') ]
        mvalue = valueList
        if mtype[0:3].lower() == 'int':
          mvalue = [ int(x) for x in valueList if not x in ['Missing','Any'] ]
          mvalue += [ x for x in valueList if x in ['Missing','Any'] ]
        if mtype[0:5].lower() == 'float':
          mvalue = [ float(x) for x in valueList if not x in ['Missing','Any'] ]
          mvalue += [ x for x in valueList if x in ['Missing','Any'] ]
        if operation == "=":
          operation = 'in'
        if operation == "!=":
          operation = 'nin'    
        mvalue = {operation:mvalue}  
      else:            
        mvalue = value.replace("'","").replace('"','')
        if not value in ['Missing','Any']:
          if mtype[0:3].lower() == 'int':
            mvalue = int(value)
          if mtype[0:5].lower() == 'float':
            mvalue = float(value)               
        if operation != '=':     
          mvalue = {operation:mvalue}      
                                
      if name in metaDict:
        if type(metaDict[name]) == DictType:
          if type(mvalue) == DictType:
            op,value = mvalue.items()[0]
            if op in metaDict[name]:
              if type(metaDict[name][op]) == ListType:
                if type(value) == ListType:
                  metaDict[name][op] = uniqueElements(metaDict[name][op] + value)
                else:
                  metaDict[name][op] = uniqueElements(metaDict[name][op].append(value))     
              else:
                if type(value) == ListType:
                  metaDict[name][op] = uniqueElements([metaDict[name][op]] + value)
                else:
                  metaDict[name][op] = uniqueElements([metaDict[name][op],value])       
            else:
              metaDict[name].update(mvalue)
          else:
            if type(mvalue) == ListType:
              metaDict[name].update({'in':mvalue})
            else:  
              metaDict[name].update({'=':mvalue})
        elif type(metaDict[name]) == ListType:   
          if type(mvalue) == DictType:
            metaDict[name] = {'in':metaDict[name]}
            metaDict[name].update(mvalue)
          elif type(mvalue) == ListType:
            metaDict[name] = uniqueElements(metaDict[name] + mvalue)
          else:
            metaDict[name] = uniqueElements(metaDict[name].append(mvalue))      
        else:
          if type(mvalue) == DictType:
            metaDict[name] = {'=':metaDict[name]}
            metaDict[name].update(mvalue)
          elif type(mvalue) == ListType:
            metaDict[name] = uniqueElements([metaDict[name]] + mvalue)
          else:
            metaDict[name] = uniqueElements([metaDict[name],mvalue])          
      else:            
        metaDict[name] = mvalue         
    
    return metaDict 
      
  def do_exit(self, args):
    """ Exit the shell.

    usage: exit
    """
    sys.exit(0)

  def emptyline(self): 
    pass      
      
if __name__ == "__main__":
  
  if len(sys.argv) > 2:
    print FileCatalogClientCLI.__doc__
    sys.exit(2)      
  elif len(sys.argv) == 2:
    catype = sys.argv[1]
    if catype == "LFC":
      from DIRAC.Resources.Catalog.LcgFileCatalogProxyClient import LcgFileCatalogProxyClient
      cli = FileCatalogClientCLI(LcgFileCatalogProxyClient())
      print "Starting LFC Proxy FileCatalog client"
      cli.cmdloop() 
    elif catype == "DiracFC":
      from DIRAC.Resources.Catalog.FileCatalogClient import FileCatalogClient
      cli = FileCatalogClientCLI(FileCatalogClient())
      print "Starting ProcDB FileCatalog client"
      cli.cmdloop()  
    else:
      print "Unknown catalog type", catype
