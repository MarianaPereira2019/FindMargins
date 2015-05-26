import os
import unittest

from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

import time

import FindMarginsLib
reload(FindMarginsLib)

#
# FindMargins
#

class FindMargins(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "FindMargins" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Examples"]
    self.parent.dependencies = []
    self.parent.contributors = ["Kristjan Anderle (GSI)"] # replace with "Firstname Lastname (Org)"
    self.parent.helpText = """
    This is a module that finds tumor margins due to motion
    """
    self.parent.acknowledgementText = """
    This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc. and Steve Pieper, Isomics, Inc.  and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

#
# qFindMarginsWidget
#

class FindMarginsWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)


    #
    # Reload and Test area
    #
    reloadCollapsibleButton = ctk.ctkCollapsibleButton()
    reloadCollapsibleButton.text = "Reload && Test"
    self.layout.addWidget(reloadCollapsibleButton)
    reloadFormLayout = qt.QFormLayout(reloadCollapsibleButton)

    ## reload button
    ## (use this during development, but remove it when delivering
    ##  your module to users)
    self.reloadCTXButton = qt.QPushButton("Reload")
    self.reloadCTXButton.toolTip = "Reload this module."
    self.reloadCTXButton.name = "LoadCTX Reload"
    reloadFormLayout.addWidget(self.reloadCTXButton)
    self.reloadCTXButton.connect('clicked()', self.onReload)

    ## reload and test button
    ## (use this during development, but remove it when delivering
    ##  your module to users)
    self.reloadAndTestButton = qt.QPushButton("Reload and Test")
    self.reloadAndTestButton.toolTip = "Reload this module and then run the self tests."
    reloadFormLayout.addWidget(self.reloadAndTestButton)
    self.reloadAndTestButton.connect('clicked()', self.onReloadAndTest)

    self.tags = {}
    self.tags['seriesDescription'] = "0008,103e"
    self.tags['patientName'] = "0010,0010"
    self.tags['patientID'] = "0010,0020"
    self.tags['seriesDate'] = "0008,0022"

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    # Load all patients
    self.patientComboBox = qt.QComboBox()
    self.patientComboBox.setToolTip( "Select Patient" )
    self.patientComboBox.enabled = True
    #self.parametersFormLayout.addWidget("Patient:", self.patientComboBox)
    parametersFormLayout.addRow("Select Patient",self.patientComboBox)

    self.patientList = []
    self.getPatientList()

    for patient in self.patientList:
      self.patientComboBox.addItem(patient.name)

    # self.seriesComboBox = qt.QComboBox()
    # self.seriesComboBox.setToolTip("Select planning CT.")
    # parametersFormLayout.addRow("Select planning CT:",self.seriesComboBox)
    #
    # self.setSeriesComboBox(0)


    #
    # input volume selector
    #
    self.inputSelector = slicer.qMRMLNodeComboBox()
    self.inputSelector.nodeTypes = ( ("vtkMRMLContourNode"), "" )
    # self.inputSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.inputSelector.selectNodeUponCreation = True
    self.inputSelector.addEnabled = False
    self.inputSelector.removeEnabled = False
    self.inputSelector.noneEnabled = False
    self.inputSelector.showHidden = False
    self.inputSelector.showChildNodeTypes = False
    self.inputSelector.setMRMLScene( slicer.mrmlScene )
    self.inputSelector.setToolTip( "Pick the CTV voi." )
    self.inputSelector.enabled = False
    parametersFormLayout.addRow("Desired Contour: ", self.inputSelector)


    #
    # Select if contour is already in 4D CT

    self.contourIn4D = qt.QCheckBox()
    self.contourIn4D.toolTip = "Select if selected contour was already deliniated in 4D CT (it will skip the planning registration."
    parametersFormLayout.addRow("Contour deliniated in 4D: ",self.contourIn4D)

    
    #
    # Select reference phase:
    #
    
    self.refPhaseSpinBox = qt.QSpinBox()     
    self.refPhaseSpinBox.setToolTip( "Reference phase to base registration and mid ventilation." )
    self.refPhaseSpinBox.setValue(6)
    self.refPhaseSpinBox.setRange(0, 9)
    parametersFormLayout.addRow("Reference phase:", self.refPhaseSpinBox)
    #
    # Do registration
    #
    self.registerButton = qt.QPushButton("Register")
    self.registerButton.toolTip = "Does the registration on planning CT and 4DCT."
    parametersFormLayout.addRow(self.registerButton)

    #
    # Load DICOM
    #
    self.loadDicomButton = qt.QPushButton("Load Dicom data")
    self.loadDicomButton.toolTip = "Loads the dicom planning CT and contours."
    parametersFormLayout.addRow(self.loadDicomButton)
    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Find amplitudes")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    #
    # MidV Button
    #
    self.midVButton = qt.QPushButton("Create MidV CT")
    self.midVButton.toolTip = "Creates the Mid ventilation CT from 4DCT and registration files."
    self.midVButton.enabled = True
    parametersFormLayout.addRow(self.midVButton)

    #
    # Table with amplitudes
    #

    self.table = qt.QTableWidget()
    self.table.setColumnCount(3)
    self.table.setHorizontalHeaderLabels(["L-R","A-P","I-S"])
    self.table.setRowCount(2)
    self.table.setVerticalHeaderLabels(["Max","Min"])
    self.table.setEditTriggers(qt.QAbstractItemView.NoEditTriggers)
    # self.table.enabled = False
    parametersFormLayout.addRow(self.table)



    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.loadDicomButton.connect('clicked(bool)', self.onLoadDicomButton)
    self.registerButton.connect('clicked(bool)', self.onRegisterButton)
    self.midVButton.connect('clicked(bool)', self.onMidVButton)
    # self.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    # self.patientComboBox.connect('currentIndexChanged(QString)', self.setSeriesComboBox)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector.currentNode()
    self.inputSelector.enabled = self.inputSelector.currentNode()

  def onApplyButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]
    targetContour = self.inputSelector.currentNode()

    if patient is None:
      print "Can't find patient."
      return

    skipPlanRegistration = False
    if self.contourIn4D.checkState() == 2:
        skipPlanRegistration = True


    if targetContour is None:
      print "Can't find target contour."
      return

    patient.fourDCT[10].contour = targetContour

    # logic.run(patientNumber,seriesNumber,self.inputSelector.currentNode())

    maxminAmplitudes = logic.run(patient, skipPlanRegistration, self.refPhaseSpinBox.value)
    print maxminAmplitudes

    if not maxminAmplitudes:
        print "Can't get amplitudes."
        return
    self.item={}
    n = 0
    for i in range(0,2):
        for j in range(0,3):
            self.item[n] = qt.QTableWidgetItem()
            self.item[n].setText(str(round(maxminAmplitudes[i][j], 2)))
            self.table.setItem(i, j, self.item[n])
            n += 1


  def onLoadDicomButton(self):
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if  len(patient.structureSet.uid) == 0:
      print "Can't Structure Set DICOM data for " + patient.name
      return

    if not patient.loadStructureSet():
      print "Can't load Structure Set"
      return


    self.applyButton.enabled = True
    self.inputSelector.enabled = True

  def onRegisterButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      print "Can't find patient."
      return

    logic.register(patient, self.refPhaseSpinBox.value)

  def onMidVButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      print "Can't find patient."
      return

    logic.createMidVentilation(patient, self.refPhaseSpinBox.value)

  def getPatientList(self):

    nPatient = 0

    self.patientList = []
    for patient in slicer.dicomDatabase.patients():
      newPatient = FindMarginsLib.Patient()
      for study in slicer.dicomDatabase.studiesForPatient(patient):
        for series in slicer.dicomDatabase.seriesForStudy(study):
          files = slicer.dicomDatabase.filesForSeries(series)
          if len(files) > 0:
            instance = slicer.dicomDatabase.instanceForFile(files[0])
            try:
              patientName = slicer.dicomDatabase.instanceValue(instance,self.tags['patientID'])
            except RuntimeError:
                # this indicates that the particular instance is no longer
                # accessible to the dicom database, so we should ignore it here
              continue
            serialDescription = slicer.dicomDatabase.instanceValue(instance,self.tags['seriesDescription'])
            # print "Series date: " + slicer.dicomDatabase.instanceValue(instance,self.tags['seriesDate'])
            # if len(slicer.dicomDatabase.instanceValue(instance,self.tags['seriesDate'])) > 0:
            #   print "Hello"
            #   newPatient.planCT.uid = series
            #   newPatient.planCT.file = files[0]

            # print serialDescription
            if serialDescription.find('Structure Sets') > -1:
              newPatient.structureSet.uid = series

            if serialDescription.find('%') > -1:
              for i in range(0,100,10):
                tmpName = str(i) + ".0%"
                if serialDescription == tmpName:
                  newPatient.fourDCT[i/10].uid = series
                  newPatient.fourDCT[i/10].file = files[0]

      newPatient.databaseNumber = nPatient
      newPatient.name = patientName
      self.patientList.append(newPatient)

      nPatient += 1

# def setSeriesComboBox(self,index):
  #   for serial in self.patientList[index].series:
  #     self.seriesComboBox.addItem(serial.description)

  def onReload(self,moduleName="FindMargins"):
    """Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    globals()[moduleName] = slicer.util.reloadScriptedModule(moduleName)

  def onReloadAndTest(self,moduleName="FingMargins"):
    try:
      self.onReload()
      evalString = 'globals()["%s"].%sTest()' % (moduleName, moduleName)
      tester = eval(evalString)
      tester.runTest()
    except Exception, e:
      import traceback
      traceback.print_exc()
      qt.QMessageBox.warning(slicer.util.mainWindow(),
          "Reload and Test", 'Exception!\n\n' + str(e) + "\n\nSee Python Console for Stack Trace")




#
# FindMarginsLogic
#




class FindMarginsLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """


  def register(self,patient, referencePosition = 6):


    dicomDir = os.path.dirname(patient.fourDCT[referencePosition].file)
    vectorDir = dicomDir + "/VectorFields/"

    if not os.path.exists(vectorDir):
      os.makedirs(vectorDir)
      print "Created " + vectorDir

    patient.createPlanParameters(referencePosition,vectorDir)
    if patient.getTransform(10):
      print "Planning transform already exist."
      slicer.mrmlScene.RemoveNode(patient.fourDCT[10].transform)
      patient.fourDCT[10].transform = None
    else:
      print "Registering planning CT"
      patient.findNode(10)
      if not patient.loadDicom(10):
        print "Cant load planning CT."
        return

      if not patient.loadDicom(referencePosition):
        print "Can't load reference phase"
        return

      patient.regParameters.movingNode = patient.fourDCT[10].node.GetID()
      patient.regParameters.referenceNumber = str(referencePosition) + "0"
      patient.regParameters.referenceNode = patient.fourDCT[referencePosition].node.GetID()
      patient.regParameters.register()
      # slicer.mrmlScene.RemoveNode(patient.fourDCT[10].node)
      # patient.fourDCT[10].node = None

    # Prepare everything for 4D registration
    patient.create4DParameters(referencePosition,vectorDir)

    for i in range(0,10):
      if i == referencePosition:
        continue

      patient.regParameters.referenceNumber = str(i) + "0"
      if patient.getTransform(i):
        print "Transform for phase " + str(i) + "0% already exist."
        slicer.mrmlScene.RemoveNode(patient.fourDCT[i].transform)
        patient.fourDCT[i].transform = None
        continue
      else:
        print "Registering phase " + str(i) + "0%."
        patient.regParameters.referenceNumber = str(i) + "0"
        if not patient.loadDicom(referencePosition):
          print "Can't load reference phase"
          continue
        if not patient.loadDicom(i):
          print "Can't load phase " + str(i) + "0%."
          continue

        patient.regParameters.movingNode = patient.fourDCT[referencePosition].node.GetID()
        patient.regParameters.referenceNode = patient.fourDCT[i].node.GetID()
        patient.regParameters.register()

        slicer.mrmlScene.RemoveNode(patient.fourDCT[i].node)
        patient.fourDCT[i].node = None

        slicer.mrmlScene.RemoveNode(patient.fourDCT[referencePosition].node)
        patient.fourDCT[referencePosition].node = None
    print "Finished"
    return


  def run(self, patient, skipPlanRegistration, referencePosition):
    """
    Run the actual algorithm
    """
    from vtkSlicerContoursModuleMRML import vtkMRMLContourNode
    transformLogic = slicer.modules.transforms.logic()

    logging.info('Processing started')

    origins = {}
    relOrigins = {}
    minmaxAmplitudes = [[0,0,0],[0,0,0]]

    transform = None

    showContours = False

    # Set vector directory

    dicomDir = os.path.dirname(patient.fourDCT[referencePosition].file)
    vectorDir = dicomDir + "/VectorFields/"

    # Register planning CT to reference phase

    if skipPlanRegistration:
        contour = patient.fourDCT[10].contour
    else:
        #Propagate contour
        patient.createPlanParameters(referencePosition, vectorDir)

        if not patient.getTransform(10):
          print "Can't load transform"
          return None

        transform = vtk.vtkGeneralTransform()

        print patient.fourDCT[10].transform.GetID()
        patient.fourDCT[10].transform.GetTransformToWorld(transform)
        transform.Update()

        # Load contour
        contour = vtkMRMLContourNode()
        contour.DeepCopy(patient.fourDCT[10].contour)

        contour.SetName(patient.fourDCT[10].contour.GetName() + "_refPosition")

        slicer.mrmlScene.AddNode(contour)

        if showContours:
          self.setDisplayNode(contour)

        print contour.GetID()
        print patient.fourDCT[10].contour.GetID()
        # contour.ApplyTransform(transform)
        contour.SetAndObserveTransformNodeID(patient.fourDCT[10].transform.GetID())
        print contour.GetTransformNodeID()
        if not transformLogic.hardenTransform(contour):
            print "Can't harden transform."
            return None
        #
        # slicer.mrmlScene.RemoveNode(bsplinePlan)

    patient.fourDCT[referencePosition].contour = contour
    origins[referencePosition] = self.getCenterOfMass(contour)
    relOrigins[referencePosition] = [0,0,0]

    # Propagation in 4D
    # TODO: Add option to display contours, otherwise delete nodes

    patient.create4DParameters(referencePosition,vectorDir)
    for i in range(0,10):
      print "We are at phase " + str(i)
      if i == referencePosition:
        print origins[i]
        print relOrigins[i]
        continue
      patient.regParameters.referenceNumber = str(i) + "0"
      #Check contour
      if not patient.getTransform(i):
        print "Can't find transform for phase "+ str(i) +"0 %"
        continue

      if transform is None:
        transform = vtk.vtkGeneralTransform()

      patient.fourDCT[i].transform.GetTransformToWorld(transform)
      transform.Update()

      #Create contour
      contour = None
      contour = vtkMRMLContourNode()
      slicer.mrmlScene.AddNode(contour)
      contour.DeepCopy(patient.fourDCT[referencePosition].contour)
      contour.SetName(patient.fourDCT[referencePosition].contour.GetName() + "_phase" + str(i))
      if showContours:
        self.setDisplayNode(contour)

      contour.SetAndObserveTransformNodeID(patient.fourDCT[i].transform.GetID())
      if not transformLogic.hardenTransform(contour):
          print "Can't harden transform for phase: " + str(i) + "0 %"
          continue

      patient.fourDCT[i].contour = contour

      origins[i] = self.getCenterOfMass(contour)
      relOriginsTmp = [0,0,0]
      for j in range(0,3):
        relOriginsTmp[j] = origins[i][j] - origins[referencePosition][j]
        if relOriginsTmp[j] > minmaxAmplitudes[0][j]:
            minmaxAmplitudes[0][j] = relOriginsTmp[j]
        elif relOriginsTmp[j] < minmaxAmplitudes[1][j]:
            minmaxAmplitudes[1][j] = relOriginsTmp[j]
      relOrigins[i] = relOriginsTmp


      print origins[i]
      print relOrigins[i]

      patient.fourDCT[i].origin = origins[i]
      patient.fourDCT[i].relOrigin = relOrigins[i]


    # Plots
    ln = slicer.util.getNode(pattern='vtkMRMLLayoutNode*')
    ln.SetViewArrangement(24)

    # Get the first ChartView node
    cvn = slicer.util.getNode(pattern='vtkMRMLChartViewNode*')

    # Create arrays of data
    dn = {}
    for i in range(0,3):
      dn[i] = slicer.mrmlScene.AddNode(slicer.vtkMRMLDoubleArrayNode())
      a = dn[i].GetArray()
      a.SetNumberOfTuples(10)
      for j in range(0,10):
        a.SetComponent(j, 0, j)
        a.SetComponent(j, 1, relOrigins[j][i])
        a.SetComponent(j, 2, 0)

    # Create the ChartNode,
    cn = slicer.mrmlScene.AddNode(slicer.vtkMRMLChartNode())

    # Add data to the Chart
    cn.AddArray('x', dn[0].GetID())
    cn.AddArray('y', dn[1].GetID())
    cn.AddArray('z', dn[2].GetID())

    # Configure properties of the Chart
    cn.SetProperty('default', 'title','Relative tumor motion')
    cn.SetProperty('default', 'xAxisLabel', 'phase')
    cn.SetProperty('default', 'yAxisLabel', 'position [mm]')

    cn.SetProperty('x', 'color', '#0000ff')
    cn.SetProperty('y', 'color', '#00ff00')
    cn.SetProperty('z', 'color', '#ff0000')

    # Set the chart to display
    cvn.SetChartNodeID(cn.GetID())
    logging.info('Processing completed')

    return minmaxAmplitudes

  def createMidVentilation(self,patient, referencePosition = 6):
    transformLogic = slicer.modules.transforms.logic()
    mathMultiply = vtk.vtkImageMathematics()
    mathAddVector = vtk.vtkImageMathematics()
    mathAddCT = vtk.vtkImageMathematics()

    vectorImageData = vtk.vtkImageData()
    ctImageData = vtk.vtkImageData()

    gridAverageTransform = slicer.vtkOrientedGridTransform()

    dicomDir = os.path.dirname(patient.fourDCT[referencePosition].file)
    vectorDir = dicomDir + "/VectorFields/"

    patient.create4DParameters(referencePosition,vectorDir)

    print "Starting process"

    firstRun = True
    # vector = slicer.vtkMRMLVectorVolumeNode()
    # slicer.mrmlScene.AddNode(vector)
    for i in range(0, 10):

        if i == referencePosition:
            continue

        patient.regParameters.referenceNumber = str(i) + "0"
        print "Getting transformation for phase" + str(i) + "0 %"
        if not patient.getVectorField(i):
            print "Can't get vector field for phase " + str(i) + "0 %"
            continue

        mathMultiply.RemoveAllInputs()
        mathAddVector.RemoveAllInputs()

        mathMultiply.SetOperationToMultiplyByK()
        mathMultiply.SetConstantK(0.1)


        vectorField = patient.fourDCT[i].vectorField
        mathMultiply.SetInput1Data(vectorField.GetImageData())
        mathMultiply.Modified()
        mathMultiply.Update()

        if firstRun:
            vectorImageData.DeepCopy(mathMultiply.GetOutput())


            matrix = vtk.vtkMatrix4x4()
            vectorField.GetIJKToRASDirectionMatrix(matrix)
            gridAverageTransform.SetGridDirectionMatrix(matrix)

            # vector.SetOrigin(vectorField.GetOrigin())
            # vector.SetSpacing(vectorField.GetSpacing())
            # vector.SetIJKToRASDirectionMatrix(matrix)

            firstRun = False
        else:
            mathAddVector.SetOperationToAdd()
            mathAddVector.SetInput1Data( mathMultiply.GetOutput())
            mathAddVector.SetInput2Data( vectorImageData)
            mathAddVector.Modified()
            mathAddVector.Update()
            vectorImageData.DeepCopy(mathAddVector.GetOutput())

        vectorImageData.SetSpacing(vectorField.GetSpacing())
        vectorImageData.SetOrigin(vectorField.GetOrigin())
        slicer.mrmlScene.RemoveNode(vectorField)
        patient.fourDCT[i].vectorField = None



    # print vector.GetID()
    #
    # vector.SetAndObserveImageData(vectorImageData)
    gridAverageTransform.SetDisplacementGridData(vectorImageData)
    gridAverageTransform.SetInterpolationModeToCubic()
    gridAverageTransform.Inverse()
    gridAverageTransform.Update()
    transformNode = slicer.vtkMRMLGridTransformNode()
    slicer.mrmlScene.AddNode(transformNode)
    transformNode.SetAndObserveTransformFromParent(gridAverageTransform)
    # return



    midVCT = slicer.vtkMRMLScalarVolumeNode()
    slicer.mrmlScene.AddNode(midVCT)
    midVCT.SetName(patient.name + "_midV_ref"+str(referencePosition))


    firstRun = True
    for i in range(0, 10):
        print "Propagating phase " + str(i) + "0 % to midV position."
        patient.regParameters.referenceNumber = str(i) + "0"
        # if i == referencePosition:
        #     displacmentGridImageData.ShallowCopy(vectorImageData)
        #     # if exportVector:
        #     #     gridTransform.SetDisplacementGridData(vectorImageData)
        #     #     gridTransform.SetInterpolationModeToCubic()
        #     #     gridTransform.Inverse()
        #     #     gridTransform.Update()
        #     #     transformNode = slicer.vtkMRMLGridTransformNode()
        #     #     slicer.mrmlScene.AddNode(transformNode)
        #     #     transformNode.SetAndObserveTransformFromParent(gridTransform)
        #
        # else:
        #     mathMultiply.SetOperationToSubtract()
        #     if not patient.getVectorField(i):
        #       print "Can't get vector field for phase " + str(i) + "0 %"
        #       continue
        #
        #     vectorField = patient.fourDCT[i].vectorField
        #     mathMultiply.SetInput1Data(vectorImageData)
        #     mathMultiply.SetInput2Data(vectorField.GetImageData())
        #     mathMultiply.Modified()
        #     mathMultiply.Update()
        #     displacmentGridImageData.DeepCopy(mathMultiply.GetOutput())
        #
        # print displacmentGridImageData.GetOrigin()
        #
        #
        # gridTransform.SetDisplacementGridData(displacmentGridImageData)
        # gridTransform.SetInterpolationModeToCubic()
        # gridTransform.Inverse()
        # gridTransform.Update()
        # if exportVector:
        #     transformNode = slicer.vtkMRMLGridTransformNode()
        #     slicer.mrmlScene.AddNode(transformNode)
        #     transformNode.SetName("Transform_" + str(i))
        #     transformNode.SetAndObserveTransformFromParent(gridTransform)
        #
        #     vv = slicer.vtkMRMLVectorVolumeNode()
        #     vv.SetSpacing(displacmentGridImageData.GetSpacing())
        #     vv.SetOrigin(displacmentGridImageData.GetOrigin())
        #     vv.SetIJKToRASDirectionMatrix(matrix)
        #     vv.SetAndObserveImageData(displacmentGridImageData)
        #     vv.SetName("Phase_" + str(i))
        #     slicer.mrmlScene.AddNode(vv)


        if vectorField:
          slicer.mrmlScene.RemoveNode(vectorField)
          patient.fourDCT[i].vectorField = None

        if not patient.loadDicom(i):
            print "Can't get CT for phase " + str(i) + "0 %"
            return

        ctNode = patient.fourDCT[i].node

        if not i == referencePosition:
            if not patient.getTransform(i):
                print "Can't get transform for phase " + str(i) + "0 %"
                return
            patient.fourDCT[i].transform.Inverse()
            ctNode.SetAndObserveTransformNodeID(patient.fourDCT[i].transform.GetID())
            if not transformLogic.hardenTransform(ctNode):
                print "Can't harden transform for phase " + str(i) + "0 %"
                return

            slicer.mrmlScene.RemoveNode(patient.fourDCT[i].transform)
            patient.fourDCT[i].transform = None


        # ctNode.ApplyTransform(gridAverageTransform)
        ctNode.SetAndObserveTransformNodeID(transformNode.GetID())
        if not transformLogic.hardenTransform(ctNode):
            print "Can't harden transform for phase " + str(i) + "0 %"
            return

        mathMultiply.RemoveAllInputs()
        mathAddCT.RemoveAllInputs()

        mathMultiply.SetOperationToMultiplyByK()
        mathMultiply.SetConstantK(0.1)

        mathMultiply.SetInput1Data(ctNode.GetImageData())

        mathMultiply.Modified()
        mathMultiply.Update()

        if firstRun:
          ctImageData.DeepCopy(mathMultiply.GetOutput())
          midVCT.SetSpacing(ctNode.GetSpacing())
          midVCT.SetOrigin(ctNode.GetOrigin())

          matrix = vtk.vtkMatrix4x4()
          ctNode.GetIJKToRASDirectionMatrix(matrix)
          midVCT.SetIJKToRASDirectionMatrix(matrix)
          firstRun = False
        else:
          mathAddCT.SetOperationToAdd()
          mathAddCT.SetInput1Data( mathMultiply.GetOutput())
          mathAddCT.SetInput2Data( ctImageData)
          mathAddCT.Modified()
          mathAddCT.Update()
          ctImageData.DeepCopy(mathAddCT.GetOutput())

        slicer.mrmlScene.RemoveNode(ctNode)
        patient.fourDCT[i].node = None


    midVCT.SetAndObserveImageData(ctImageData)
  def createAverageFrom4DCT(self,patient):


    mathMultiply = vtk.vtkImageMathematics()
    mathAddVector = vtk.vtkImageMathematics()
    mathAddCT = vtk.vtkImageMathematics()


    ctImageData = vtk.vtkImageData()


    referencePosition = 6

    dicomDir = os.path.dirname(patient.fourDCT[referencePosition].file)
    vectorDir = dicomDir + "/VectorFields/"

    patient.create4DParameters(referencePosition,vectorDir)

    print "Starting process"

    firstRun = True

    midVCT = slicer.vtkMRMLScalarVolumeNode()
    slicer.mrmlScene.AddNode(midVCT)
    midVCT.SetName(patient.name + "average4DCT")


    firstRun = True
    for i in range(0, 10):
        if not patient.loadDicom(i):
            print "Can't get CT for phase " + str(i) + "0 %"
            continue
        ctNode = patient.fourDCT[i].node

        mathMultiply.RemoveAllInputs()
        mathAddCT.RemoveAllInputs()

        mathMultiply.SetOperationToMultiplyByK()
        mathMultiply.SetConstantK(0.1)

        mathMultiply.SetInput1Data(ctNode.GetImageData())

        mathMultiply.Modified()
        mathMultiply.Update()

        if firstRun:
          ctImageData.DeepCopy(mathMultiply.GetOutput())
          midVCT.SetSpacing(ctNode.GetSpacing())
          midVCT.SetOrigin(ctNode.GetOrigin())

          matrix = vtk.vtkMatrix4x4()
          ctNode.GetIJKToRASDirectionMatrix(matrix)
          midVCT.SetIJKToRASDirectionMatrix(matrix)
          firstRun = False
        else:
          mathAddCT.SetOperationToAdd()
          mathAddCT.SetInput1Data(mathMultiply.GetOutput())
          mathAddCT.SetInput2Data(ctImageData)
          mathAddCT.Modified()
          mathAddCT.Update()
          ctImageData.DeepCopy(mathAddCT.GetOutput())

        slicer.mrmlScene.RemoveNode(ctNode)
        patient.fourDCT[i].node = None


    midVCT.SetAndObserveImageData(ctImageData)

  def setDisplayNode(self,contour):
      from vtkSlicerContoursModuleMRML import vtkMRMLContourModelDisplayNode

      if contour is None:
          print "No input contour"
          return
      displayNode = vtkMRMLContourModelDisplayNode()
      slicer.mrmlScene.AddNode(displayNode)
      contour.SetAndObserveDisplayNodeID(displayNode.GetID())
      contour.CreateRibbonModelDisplayNode()



  def getCenterOfMass(self,contour):
      comFilter = vtk.vtkCenterOfMass()
      comFilter.SetInputData(contour.GetRibbonModelPolyData())
      comFilter.SetUseScalarsAsWeights(False)
      comFilter.Update()
      return comFilter.GetCenter()

  def delayDisplay(self,message,msec=1000):
    """This utility method displays a small dialog and waits.
    This does two things: 1) it lets the event loop catch up
    to the state of the test so that rendering and widget updates
    have all taken place before the test continues and 2) it
    shows the user/developer/tester the state of the test
    so that we'll know when it breaks.
    """
    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message,self.info)
    self.infoLayout.addWidget(self.label)
    qt.QTimer.singleShot(msec, self.info.close)
    self.info.exec_()

class FindMarginsTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_FindMargins1()

  def test_FindMargins1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = FindMarginsLogic()
    self.assertTrue( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')

