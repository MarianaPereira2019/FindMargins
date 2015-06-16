import os
import unittest
from __main__ import vtk, qt, ctk, slicer
import numpy as np

#
# RegistrationHierarchy

class RegistrationHierarchyLogic:
    """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget
  """

    def __init__(self):
        pass

    def automaticRegistration(self, ct1, ct2):
        if not regHierarchy:
            print "No registration Hierarchy"
            return

        warpedOn = False
        cbtOn = False
        mhaOn = False
        patientName = regHierarchy.GetAttribute("PatientName")

        refPhaseNode = self.getReferencePhaseFromHierarchy(regHierarchy)
        referenceNumber = regHierarchy.GetAttribute("ReferenceNumber")
        if not refPhaseNode:
            print "Can't get reference node."
            return

        nPhases = regHierarchy.GetNumberOfChildrenNodes()
        if nPhases < 1:
            print "No children nodes."
            return

        regParameters = registrationParameters(patientName, refPhaseNode, referenceNumber, resample)

        regParameters.warpDirectory = regHierarchy.GetAttribute("DIR" + NAME_WARP)
        regParameters.vectorDirectory = regHierarchy.GetAttribute("DIR" + NAME_VECTOR)

        if not os.path.exists(regParameters.warpDirectory):
            print regParameters.warpDirectory + " directory doesn't exist - create!"
            return

        if not os.path.exists(regParameters.vectorDirectory):
            print regParameters.vectorDirectory + " directory doesn't exist - create!"
            return

        if warpedOn:
            regParameters.setWarpVolume()

        if cbtOn:
            regParameters.setVectorVolume()

        regParameters.mhaOn = mhaOn

        beginPhase = 0


        # Loop through all phases:
        for i in range(beginPhase, nPhases):
            phaseHierarchyNode = regHierarchy.GetNthChildNode(i)

            phaseNumber = phaseHierarchyNode.GetAttribute('PhaseNumber')

            #phaseNode = nextPhaseVolume

            #if not i == nPhases:
            #nextPhaseVolume = self.getVolumeFromChild(regHierarchy.GetNthChildNode(i+1),NAME_CT)

            if phaseHierarchyNode.GetID() == regHierarchy.GetAttribute(NAME_REFPHASE):
                print "Skipping reference phase"
                continue

            #If there's already vector hierarchy node, then eithen remove node or skip this phase :
            if phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_VECTOR):
                #If inverse registration wasn't completed or if we have overwrite option, repeat registration
                #Otherwise skip.
                if overwrite or not phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_INVVECTOR):
                    slicer.mrmlScene.RemoveNode(phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_VECTOR))
                    if phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_INVVECTOR):
                        slicer.mrmlScene.RemoveNode(
                            phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_INVVECTOR))
                    if phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_WARP):
                        slicer.mrmlScene.RemoveNode(phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_WARP))
                    if phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_INVWARP):
                        slicer.mrmlScene.RemoveNode(
                            phaseHierarchyNode.GetChildWithName(phaseHierarchyNode, NAME_INVWARP))
                else:
                    print "Skipping phase: " + phaseHierarchyNode.GetNameWithoutPostfix()
                    continue

            phaseNode = self.getVolumeFromChild(phaseHierarchyNode, NAME_CT)
            if not phaseNode:
                print "Can't load phase from: " + phaseHierarchyNode.GetNameWithoutPostfix()
                continue

            regParameters.movingNode = phaseNode
            regParameters.movingNumber = phaseNumber
            regParameters.movingHierarchy = phaseHierarchyNode

            regParameters.register()
            slicer.mrmlScene.RemoveNode(phaseNode)


        #Remove all volumes from scene, to free memory
        slicer.mrmlScene.RemoveNode(regParameters.warpVolume)
        slicer.mrmlScene.RemoveNode(regParameters.vectorVolume)
        #slicer.mrmlScene.RemoveNode(refPhaseNode)

        self.createTrafo(regParameters.vectorDirectory, patientName, nPhases, int(referenceNumber))


    def writeData(self, regHierarchy):
        output_str = "DIRQA for: " + regHierarchy.GetNameWithoutPostfix() + " \n"
        for i in range(0, regHierarchy.GetNumberOfChildrenNodes()):
            phaseNode = regHierarchy.GetNthChildNode(i)
            if phaseNode.GetNumberOfChildrenNodes() > 0:
                for j in range(0, phaseNode.GetNumberOfChildrenNodes()):
                    dirqaNode = phaseNode.GetNthChildNode(j)
                    dirqaName = dirqaNode.GetNameWithoutPostfix()
                    # Look for statistics:
                    stringList = []
                    if dirqaName == NAME_ABSDIFF or dirqaName == NAME_JACOBIAN or dirqaName == NAME_INVCONSIST:
                        stringList = ["Mean", "STD", "Max", "Min"]

                    if dirqaName == NAME_VECTOR or dirqaName == NAME_INVVECTOR:
                        stringList = ["x", "y", "z"]

                    if stringList and dirqaNode.GetAttribute(stringList[0]):
                        output_str += dirqaName + " \n"
                        for i in range(0, len(stringList)):
                            if not dirqaNode.GetAttribute(stringList[i]):
                                continue
                            output_str += stringList[i] + ': ' + dirqaNode.GetAttribute(stringList[i]) + " "
                            output_str += " \n"
        directoryPath = regHierarchy.GetAttribute("DIR" + NAME_DIRQA)
        if not directoryPath:
            print "Can't get Dirqa directory."
            return
        filePath = directoryPath + 'DirqaData.txt'
        f = open(filePath, "wb+")
        f.write(output_str)
        f.close()
        print "Wrote dirqa data to: " + filePath

    def writeStatistics(self, hierarchyNode, statisticsArray, vector=False):
        if vector:
            stringList = ["x", "y", "z"]
        else:
            stringList = ["Mean", "STD", "Max", "Min"]
        if len(stringList) > len(statisticsArray):
            print "Cannot write statistics, not enough data."
            return
        for i in range(0, len(stringList)):
            hierarchyNode.SetAttribute(stringList[i], str(round(statisticsArray[i], 2)))


    def createChild(self, hierarchyNode, string):
        newHierarchy = slicer.vtkMRMLSubjectHierarchyNode()
        newHierarchy.SetParentNodeID(hierarchyNode.GetID())
        newHierarchy.SetName(string)
        newHierarchy.SetLevel('Subseries')
        # TODO: Addd directories
        #newHierarchy.SetAttribute('FilePath',ctDirectory+fileName)
        #newHierarchy.SetOwnerPluginName('Volumes')
        slicer.mrmlScene.AddNode(newHierarchy)
        return newHierarchy

    def showVolumeFromHierarchyNode(self, hierarchyNode):

        volume = self.loadVolumeFromHierarchyNode(hierarchyNode)

        if not volume:
            print "No volume"
            return

        if volume.IsA('vtkMRMLVolumeNode'):
            if not volume.GetDisplayNodeID():
                displayNode = None
                if volume.IsA('vtkMRMLScalarVolumeNode'):
                    displayNode = slicer.vtkMRMLScalarVolumeDisplayNode()
                    displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
                if volume.IsA('vtkMRMLVectorVolumeNode'):
                    displayNode = slicer.vtkMRMLVectorVolumeDisplayNode()
                    displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
                if displayNode:
                    slicer.mrmlScene.AddNode(displayNode)
                    volume.SetAndObserveDisplayNodeID(displayNode.GetID())
            else:
                volume.GetDisplayNode().SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
            selectionNode = slicer.app.applicationLogic().GetSelectionNode()
            selectionNode.SetReferenceActiveVolumeID(volume.GetID())
            slicer.app.applicationLogic().PropagateVolumeSelection(0)

    def getReferencePhaseFromHierarchy(self, hierarchyNode):

        # Find out reference phase
        referenceID = hierarchyNode.GetAttribute(NAME_REFPHASE)
        if not referenceID:
            print "Can't find reference node from: " + hierarchyNode.GetNameWithoutPostfix()
            return None

        referenceHierarchyNode = slicer.util.getNode(referenceID)
        if not referenceHierarchyNode:
            print "Can't get reference Hierarchy node"
            return None

        referenceNode = self.getVolumeFromChild(referenceHierarchyNode, NAME_CT)
        if not referenceNode:
            print "Can't load reference volume from: " + referenceHierarchyNode.GetNameWithoutPostfix()
            return None

        return referenceNode

    def loadAllChildren(self, hierarchyNode, string):
        for i in range(0, hierarchyNode.GetNumberOfChildrenNodes()):
            volume = self.getVolumeFromChild(hierarchyNode.GetNthChildNode(i), string)

    def getVolumeFromChild(self, hierarchyNode, string):
        volume = None
        childNode = hierarchyNode.GetChildWithName(hierarchyNode, string)
        if not childNode:
            print "Can't get childNode: " + string + "from " + hierarchyNode.GetNameWithoutPostfix()
            return None
        volume = self.loadVolumeFromHierarchyNode(childNode)
        if not volume:
            print "Can't load  " + string + " from hierarchy childNode: " + childNode.GetNameWithoutPostfix()
            return None
        return volume

    # Loads volume from hierarchyNode. Can find it there or tries to load it from disk.
    def loadVolumeFromHierarchyNode(self, hierarchyNode):
        #Look for existing associated nodes:
        if hierarchyNode.GetAssociatedNodeID():
            volume = slicer.util.getNode(hierarchyNode.GetAssociatedNodeID())
            if volume:
                return volume

        filePath = hierarchyNode.GetAttribute('FilePath')
        volume = None
        if filePath:
            #Special case for ctx files
            if filePath.find('ctx') > -1:
                import LoadCTX

                loadLogic = LoadCTX.LoadCTXLogic()
                volume = slicer.util.getNode(loadLogic.loadCube(filePath, 0))
                if volume:
                    #Write it in hierarchy node for later use
                    hierarchyNode.SetAssociatedNodeID(volume.GetID())
                    return volume
            elif filePath.find('cbt') > -1:
                import LoadCTX

                loadLogic = LoadCTX.LoadCTXLogic()
                volume = slicer.util.getNode(loadLogic.loadCube(filePath, 3))
                if volume:
                    #Write it in hierarchy node for later use
                    hierarchyNode.SetAssociatedNodeID(volume.GetID())
                    return volume
            else:
                volumesLogic = slicer.vtkSlicerVolumesLogic()
                volumesLogic.SetMRMLScene(slicer.mrmlScene)
                slicerVolumeName = os.path.splitext(os.path.basename(filePath))[0]
                volume = volumesLogic.AddArchetypeVolume(filePath, slicerVolumeName)
                if not volume:
                    print "Can't load volume " + os.path.basename(filePath)
                    return None
                #Write it in hierarchy node for later use
                hierarchyNode.SetAssociatedNodeID(volume.GetID())

        else:
            print "Can't get file Path from: " + hierarchyNode.GetNameWithoutPostfix()
            return None

        return volume


    #Save node to disk and write it to subject hierarchy
    def saveAndWriteNode(self, node, hierarchyNode, string, filePath, cbtOn=False, resample=[]):
        if not node or not hierarchyNode or not string:
            print "Not enough input parameters."
            return False

        childNode = self.createChild(hierarchyNode, string)
        childNode.SetAttribute("FilePath", filePath)

        directory = os.path.dirname(os.path.realpath(filePath))
        if not os.path.exists(directory):
            print "No path: " + directory
            return False

        print "Saving " + node.GetName()
        #Special Case
        if cbtOn:
            import SaveTRiP

            saveTripLogic = SaveTRiP.SaveTRiPLogic()
            saveTripLogic.writeTRiPdata(directory, extension='.cbt', nodeID=node.GetID(), aix=True, resample=resample)
            return True

        if slicer.util.saveNode(node, filePath):
            childNode.SetAttribute("FilePath", filePath)
            return True


# Class that holds all info for registration
class registrationParameters():
    def __init__(self, patientName, resample = []):
        self.patientName = patientName
        self.referenceNode = ""
        self.referenceNumber = ""
        self.movingNode = None
        self.movingNumber = ''
        self.movingHierarchy = None
        self.parameters = {}
        self.warpVolume = None
        self.warpDirectory = ''
        self.vectorVolume = None
        self.vectorDirectory = ''
        self.vf_F_name = ''
        self.bspline_F_name = ''
        self.bspline = None
        self.mhaOn = False
        self.bsplineOn = False
        self.stageTwoOn = True
        self.stageThreeOn = False
        self.resample = resample

    def setWarpVolume(self):
        warpVolume = slicer.vtkMRMLScalarVolumeNode()
        slicer.mrmlScene.AddNode(warpVolume)
        storageNode = warpVolume.CreateDefaultStorageNode()
        slicer.mrmlScene.AddNode(storageNode)
        warpVolume.SetAndObserveStorageNodeID(storageNode.GetID())
        self.warpVolume = warpVolume

    def setVectorVolume(self):
        vectorVolume = slicer.vtkMRMLGridTransformNode()
        slicer.mrmlScene.AddNode(vectorVolume)
        storageNode = vectorVolume.CreateDefaultStorageNode()
        slicer.mrmlScene.AddNode(storageNode)
        vectorVolume.SetAndObserveStorageNodeID(storageNode.GetID())
        self.vectorVolume = vectorVolume

    def register(self):
        if not self.referenceNode or not self.movingNode:
            print "Not enough parameters"
            return

        registrationName = self.patientName + "_" + self.movingNumber + "to" + self.referenceNumber
        if self.warpVolume:
            self.warpVolume.SetName(registrationName + "_warped")
        if self.vectorVolume:
            self.vectorVolume.SetName(registrationName)
        if self.mhaOn:
            self.vf_F_name = self.vectorDirectory + registrationName + "_vf.mha"
        if self.bspline:
            self.bspline.SetName(registrationName + "_bspline")
        if self.bsplineOn:
            self.bspline_F_name = self.vectorDirectory + registrationName + "_bs.txt"

        self.setParameters()
        #run plastimatch registration
        plmslcRegistration = slicer.modules.plastimatch_slicer_bspline
        slicer.cli.run(plmslcRegistration, None, self.parameters, wait_for_completion=True)
        #Resample if neccesary
        #TODO: Descripton in process.
        #self.resampleVectorVolume()
        #save nodes
        self.saveNodes()
        #Switch

    def checkVf(self):
      fileName = self.vectorDirectory + self.patientName + "_" + self.movingNumber + "to" + self.referenceNumber +  "_vf.nrrd"
      self.vf_F_name = fileName
      if os.path.exists(fileName):
        return self.patientName + "_" + self.movingNumber + "to" + self.referenceNumber +  "_vf"
      else:
        return ""

    def checkBspline(self):
      fileName = self.vectorDirectory + self.patientName + "_" + self.movingNumber + "to" + self.referenceNumber +  "_bs.txt"
      self.bspline_F_name = fileName
      if os.path.exists(fileName):
        return self.patientName + "_" + self.movingNumber + "to" + self.referenceNumber +  "_bs"
      else:
        return ""

    def saveNodes(self, switch=False):
        logic = RegistrationHierarchyLogic()
        if self.warpVolume:
            if not self.warpDirectory:
                print "No directory"
                return
            if switch:
                name = NAME_INVWARP
            else:
                name = NAME_WARP
            filePath = self.warpDirectory + self.warpVolume.GetName() + ".nrrd"
            if logic.saveAndWriteNode(self.warpVolume, self.movingHierarchy, name, filePath):
                print "Saved Warped Image " + self.warpVolume.GetName()

        if self.vectorVolume:
            if not self.vectorDirectory:
                print "No directory"
                return
            if switch:
                name = NAME_VECTOR
            else:
                name = NAME_INVVECTOR
            filePath = self.vectorDirectory + self.vectorVolume.GetName() + "_x.ctx"
            if logic.saveAndWriteNode(self.vectorVolume, self.movingHierarchy, name, filePath, True, self.resample):
                print "Saved vector field."

    def switchPhase(self):
        if not self.parameters:
            print "No parameters"
            return

        self.parameters["plmslc_fixed_volume"] = self.movingNode.GetID()
        self.parameters["plmslc_moving_volume"] = self.referenceNode.GetID()

    def setParameters(self):
        parameters = {}

        parameters["plmslc_fixed_volume"] = self.referenceNode
        parameters["plmslc_moving_volume"] = self.movingNode

        parameters["plmslc_fixed_fiducials"] = ''
        parameters["plmslc_moving_fiducials"] = ''

        parameters["metric"] = "MSE"  #"MI

        if self.bspline:
          parameters["plmslc_output_bsp"] = self.bspline.GetID()
        if self.bspline_F_name:
          parameters["plmslc_output_bsp_f"] = self.bspline_F_name

        if self.warpVolume:
            parameters["plmslc_output_warped"] = self.warpVolume
        else:
            parameters["plmslc_output_warped"] = ''
        if self.vectorVolume:
            parameters["plmslc_output_vf"] = self.vectorVolume
        else:
            parameters["plmslc_output_vf"] = ''

        if not self.vectorVolume and self.vf_F_name:
            parameters["plmslc_output_vf_f"] = self.vf_F_name
        else:
            parameters["plmslc_output_vf_f"] = ''

        parameters["enable_stage_0"] = False

        parameters["stage_1_resolution"] = '4,4,2'
        parameters["stage_1_grid_size"] = '50'
        parameters["stage_1_regularization"] = '0.005'
        parameters["stage_1_its"] = '200'
        parameters["plmslc_output_warped_1"] = ''

        parameters["enable_stage_2"] = self.stageTwoOn
        parameters["stage_2_resolution"] = '2,2,1'
        parameters["stage_2_grid_size"] = '25'
        parameters["stage_1_regularization"] = '0.005'
        parameters["stage_2_its"] = '100'
        parameters["plmslc_output_warped_2"] = ''

        parameters["enable_stage_3"] = self.stageThreeOn
        parameters["stage_3_resolution"] = '1,1,1'
        parameters["stage_3_grid_size"] = '15'
        parameters["stage_1_regularization"] = '0.1'
        parameters["stage_3_its"] = '50'
        parameters["plmslc_output_warped_3"] = ''
        self.parameters = parameters

    def resampleVectorVolume(self):
        if not self.vectorVolume or not self.vectorVolume.IsA('vtkMRMLVectorVolumeNode'):
            print "No vector volume for resampling."
            return

        if self.resample == []:
            print "No resample values."
            return

        if not len(self.resample) == 3:
            print "Too many values for resampling."
            return

        oldVectorVolume = self.vectorVolume

        #Create new vector volume
        newVectorVolume = slicer.vtkMRMLVectorVolumeNode()
        newVectorVolume.SetName(oldVectorVolume.GetName())
        slicer.mrmlScene.AddNode(newVectorVolume)

        #Create strings for resampling
        spacing = ''
        size = ''
        for i in range(0, len(self.resample)):
            spacing += str(oldVectorVolume.GetSpacing()[i] * self.resample[i])
            #extent = oldVectorVolume.GetImageData().GetExtent[2*i+1]
            extent = oldVectorVolume.GetImageData().GetExtent()[2 * i + 1] + 1
            size += str(extent / self.resample[i])
            if i < 2:
                spacing += ','
                size += ','

        print "Resampling " + oldVectorVolume.GetName() + " to new pixel size " + size

        #Set parameters
        parameters = {}
        parameters["inputVolume"] = oldVectorVolume.GetID()
        parameters["outputVolume"] = newVectorVolume.GetID()
        parameters["referenceVolume"] = ''
        parameters["outputImageSpacing"] = spacing
        parameters["outputImageSize"] = size

        #Do resampling
        resampleScalarVolume = slicer.modules.resamplescalarvectordwivolume
        clNode = slicer.cli.run(resampleScalarVolume, None, parameters, wait_for_completion=True)

        #Remove old vector node and set new:
        self.vectorVolume = newVectorVolume
        slicer.mrmlScene.RemoveNode(oldVectorVolume)