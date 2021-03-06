########################################################################
# $HeadURL$
########################################################################
__RCSID__ = "$Id$"

from DIRAC                                                          import S_OK, S_ERROR, gConfig, gMonitor, gLogger, rootPath
from DIRAC.Core.Base.AgentModule                                    import AgentModule
from DIRAC.Core.Utilities.List                                      import sortList
from DIRAC.TransformationSystem.Client.TransformationClient         import TransformationClient

AGENT_NAME = 'Transformation/MCExtensionAgent'

class MCExtensionAgent( AgentModule ):

  #############################################################################
  def initialize( self ):
    """Sets defaults """
    self.transClient = TransformationClient()

    # This sets the Default Proxy to used as that defined under 
    # /Operations/Shifter/DataManager
    # the shifterProxy option in the Configuration can be used to change this default.
    self.am_setOption( 'shifterProxy', 'DataManager' )

    self.transformationTypes = sortList( self.am_getOption( 'TransformationTypes', ['MCSimulation', 'Simulation'] ) )
    gLogger.info( "Will consider the following transformation types: %s" % str( self.transformationTypes ) )
    self.maxIterationTasks = self.am_getOption( 'TasksPerIteration', 50 )
    gLogger.info( "Will create a maximum of %s tasks per iteration" % self.maxIterationTasks )
    self.maxFailRate = self.am_getOption( 'MaxFailureRate', 30 )
    gLogger.info( "Will not submit tasks for transformations with failure rate greater than %s%s" % ( self.maxFailRate, '%' ) )
    self.maxWaitingJobs = self.am_getOption( 'MaxWaitingJobs', 1000 )
    gLogger.info( "Will not submit tasks for transformations with more than %d waiting jobs" % self.maxWaitingJobs )
    return S_OK()

  #############################################################################
  def execute( self ):
    """ The MCExtensionAgent execution method."""

    self.enableFlag = self.am_getOption( 'EnableFlag', 'True' )
    if not self.enableFlag == 'True':
      self.log.info( 'TransformationCleaningAgent is disabled by configuration option %s/EnableFlag' % ( self.section ) )
      return S_OK( 'Disabled via CS flag' )

    # Obtain the transformations in Cleaning status and remove any mention of the jobs/files
    res = self.transClient.getTransformations( {'Status':'Active', 'Type':self.transformationTypes} )
    if res['OK']:
      for transDict in res['Value']:
        transID = transDict['TransformationID']
        maxTasks = transDict['MaxNumberOfTasks']
        self.extendTransformation( transID, maxTasks )
    return S_OK()

  def extendTransformation( self, transID, maxTasks ):
    gLogger.info( "Considering extension of transformation %d" % transID )
    # Get the current count of tasks submitted for this transformation
    res = self.transClient.getTransformationTaskStats( transID )
    if not res['OK']:
      if res['Message'] != 'No records found':
        gLogger.error( "Failed to get task statistics", "%s %s" % ( transID, res['Message'] ) )
        return res
      else:
        statusDict = {}
    else:
      statusDict = res['Value']
    gLogger.verbose( "Current task count for transformation %d" % transID )
    for status in sortList( statusDict.keys() ):
      statusCount = statusDict[status]
      gLogger.verbose( "%s : %s" % ( status.ljust( 20 ), str( statusCount ).rjust( 8 ) ) )
    # Determine the number of tasks to be created
    numberOfTasks = self.calculateTaskNumber( maxTasks, statusDict )
    if not numberOfTasks:
      gLogger.info( "No tasks required for transformation %d" % transID )
      return S_OK()
    # Extend the transformation by the determined number of tasks
    res = self.transClient.extendTransformation( transID, numberOfTasks )
    if not res['OK']:
      gLogger.error( "Failed to extend transformation", "%s %s" % ( transID, res['Message'] ) )
      return res
    gLogger.info( "Successfully extended transformation %d by %d tasks" % ( transID, numberOfTasks ) )
    return S_OK()

  def calculateTaskNumber( self, maxTasks, statusDict ):
    done = statusDict.get( 'Done', 0 )
    failed = statusDict.get( 'Failed', 0 )
    running = statusDict.get( 'Running', 0 )
    waiting = statusDict.get( 'Waiting', 0 )
    total = statusDict.get( 'Created', 0 )
    # If the failure rate is higher than acceptable
    if ( total != 0 ) and ( ( 100.0 * float( failed ) / float( total ) ) > self.maxFailRate ):
      return 0
    # If we already have enough completed jobs
    if done >= maxTasks:
      return 0
    if waiting > self.maxWaitingJobs:
      return 0
    numberOfTasks = maxTasks - ( total - failed )
    if numberOfTasks > self.maxIterationTasks:
      numberOfTasks = self.maxIterationTasks
    return numberOfTasks
