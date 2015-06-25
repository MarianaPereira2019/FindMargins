import os
import unittest
import math
import numpy as np

from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

# import time
# import threading

import FindMarginsLib


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


    # #
    # # Reload and Test area
    # #
    # reloadCollapsibleButton = ctk.ctkCollapsibleButton()
    # reloadCollapsibleButton.text = "Reload && Test"
    # self.layout.addWidget(reloadCollapsibleButton)
    # reloadFormLayout = qt.QFormLayout(reloadCollapsibleButton)
    #
    # ## reload button
    # ## (use this during development, but remove it when delivering
    # ##  your module to users)
    # self.reloadCTXButton = qt.QPushButton("Reload")
    # self.reloadCTXButton.toolTip = "Reload this module."
    # self.reloadCTXButton.ID = "LoadCTX Reload"
    # reloadFormLayout.addWidget(self.reloadCTXButton)
    # self.reloadCTXButton.connect('clicked()', self.onReload)
    #
    # ## reload and test button
    # ## (use this during development, but remove it when delivering
    # ##  your module to users)
    # self.reloadAndTestButton = qt.QPushButton("Reload and Test")
    # self.reloadAndTestButton.toolTip = "Reload this module and then run the self tests."
    # reloadFormLayout.addWidget(self.reloadAndTestButton)
    # self.reloadAndTestButton.connect('clicked()', self.onReloadAndTest)

    self.tags = {}
    self.tags['seriesDescription'] = "0008,103e"
    self.tags['patientName'] = "0010,0010"
    self.tags['patientID'] = "0010,0020"
    self.tags['seriesDate'] = "0008,0022"
    self.tags['studyDescription'] = "0008,1030"
    self.tags['modality'] = "0008,0060"

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
      self.patientComboBox.addItem(patient.ID)

    #
    # input volume selector
    #
    self.inputContourSelector = slicer.qMRMLNodeComboBox()
    self.inputContourSelector.nodeTypes = ( ("vtkMRMLContourNode"), "" )
    # self.inputContourSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.inputContourSelector.selectNodeUponCreation = True
    self.inputContourSelector.addEnabled = False
    self.inputContourSelector.removeEnabled = False
    self.inputContourSelector.noneEnabled = False
    self.inputContourSelector.showHidden = False
    self.inputContourSelector.showChildNodeTypes = False
    self.inputContourSelector.setMRMLScene( slicer.mrmlScene )
    self.inputContourSelector.setToolTip( "Pick the CTV voi." )
    self.inputContourSelector.enabled = False
    parametersFormLayout.addRow("Desired Contour: ", self.inputContourSelector)
    
    #
    # planning CT selector
    #
    self.inputPlanCTSelector = slicer.qMRMLNodeComboBox()
    self.inputPlanCTSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
    # self.inputPlanCTSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.inputPlanCTSelector.selectNodeUponCreation = True
    self.inputPlanCTSelector.addEnabled = False
    self.inputPlanCTSelector.removeEnabled = False
    self.inputPlanCTSelector.noneEnabled = True
    self.inputPlanCTSelector.showHidden = False
    self.inputPlanCTSelector.showChildNodeTypes = False
    self.inputPlanCTSelector.setMRMLScene( slicer.mrmlScene )
    self.inputPlanCTSelector.setToolTip( "Pick the planning CT, if it can't be found by default." )
    self.inputPlanCTSelector.enabled = True
    parametersFormLayout.addRow("Planning CT: ", self.inputPlanCTSelector)


    #
    # Select if contour is already in 4D CT
    #

    self.contourIn4D = qt.QCheckBox()
    self.contourIn4D.toolTip = "Select if selected contour was already deliniated in 4D CT (it will skip the planning registration."
    self.contourIn4D.setCheckState(2)
    parametersFormLayout.addRow("Contour deliniated in 4D: ",self.contourIn4D)

    #
    # Display contours
    #

    self.showContours = qt.QCheckBox()
    self.showContours.toolTip = "Select if you want to display all the generated contours."
    self.showContours.setCheckState(0)
    parametersFormLayout.addRow("Show created ontours: ",self.showContours)

    #
    # Registration from planning CT to all ref phase
    #

    self.planToAll = qt.QCheckBox()
    self.planToAll.toolTip = "Select if you want to register planning CT to all phases of 4D CT."
    self.planToAll.setCheckState(0)
    parametersFormLayout.addRow("MidV from planning CT: ",self.planToAll)
    
    #
    # Keep amplitudes 
    #

    self.keepAmplituedCheckBox = qt.QCheckBox()
    self.keepAmplituedCheckBox.toolTip = "Select if you want to use motion from markers or some other organs for PTV definition."
    self.keepAmplituedCheckBox.setCheckState(0)
    parametersFormLayout.addRow("Keep amplitudes: ",self.keepAmplituedCheckBox)
    
    #
    # Find axis of motion 
    #

    self.axisOfMotionCheckBox = qt.QCheckBox()
    self.axisOfMotionCheckBox.toolTip = "Select if you want to find axis of motion with principal component analysis."
    self.axisOfMotionCheckBox.setCheckState(0)
    parametersFormLayout.addRow("Find Axis of Motion: ",self.axisOfMotionCheckBox)

    
    #
    # Select reference phase:
    #
    
    self.refPhaseSpinBox = qt.QSpinBox()     
    self.refPhaseSpinBox.setToolTip( "Reference phase to base registration and mid ventilation." )
    self.refPhaseSpinBox.setValue(3)
    self.refPhaseSpinBox.setRange(0, 9)
    parametersFormLayout.addRow("Reference phase:", self.refPhaseSpinBox)
    
    #
    # Select systematic error:
    #
    
    self.SSigmaSpinBox = qt.QSpinBox()     
    self.SSigmaSpinBox.setToolTip("Systematic error to be used in PTV calculations.")
    self.SSigmaSpinBox.setValue(2)
    self.SSigmaSpinBox.setRange(0, 10)
    parametersFormLayout.addRow("Systematic Error [mm]:", self.SSigmaSpinBox)
    
    #
    # Select random error:
    #
    
    self.RsigmaSpinBox = qt.QSpinBox()     
    self.RsigmaSpinBox.setToolTip("Random error to be used in PTV calculations.")
    self.RsigmaSpinBox.setValue(0)
    self.RsigmaSpinBox.setRange(0, 10)
    parametersFormLayout.addRow("Random Error [mm]:", self.RsigmaSpinBox)
    
    #
    # Do registration
    #
    self.registerButton = qt.QPushButton("1: Register planCT and 4DCT")
    self.registerButton.toolTip = "Does the registration on planning CT and 4DCT."
    parametersFormLayout.addRow(self.registerButton)

    #
    # MidV Button
    #
    self.midVButton = qt.QPushButton("2a: Create MidVentilation CT")
    self.midVButton.toolTip = "Creates the Mid ventilation CT from 4DCT and registration files."
    self.midVButton.enabled = True
    parametersFormLayout.addRow(self.midVButton)

    #
    # Export MidV Button
    #
    self.exportMidVButton = qt.QPushButton("Export MidV CT as DICOM")
    self.exportMidVButton.toolTip = "Exports mid ventilation as dicom series."
    self.exportMidVButton.enabled = True
    parametersFormLayout.addRow(self.exportMidVButton)
    
    #
    # Average 4DCT Button
    #
    self.averageButton = qt.QPushButton("3a: Create Average of 4D CT")
    self.averageButton.toolTip = "Creates time average CT from 4DCTs."
    self.averageButton.enabled = True
    parametersFormLayout.addRow(self.averageButton)

    #
    # Register planning CT to midV Button
    #
    self.registerMidButton = qt.QPushButton("4a: Register Planning CT to MidV")
    self.registerMidButton.toolTip = "Register planning CT to mid ventilation phase."
    self.registerMidButton.enabled = True
    self.registerMidButton.visible = True
    parametersFormLayout.addRow(self.registerMidButton)
    
    #
    # Load DICOM
    #
    self.loadContoursButton = qt.QPushButton("2b: Load Contours")
    self.loadContoursButton.toolTip = "Loads contours from DICOM data."
    parametersFormLayout.addRow(self.loadContoursButton)
    #
    # Amplitudes Button
    #
    self.findAmplitudesButton = qt.QPushButton("2c: Find breathing amplitudes of slected volume")
    self.findAmplitudesButton.toolTip = "Run the algorithm."
    self.findAmplitudesButton.enabled = False
    parametersFormLayout.addRow(self.findAmplitudesButton)
    
    #
    # Calculate margins
    #
    self.calcMarginsButton = qt.QPushButton("2d: Calculate margins according to M = 2.1SIGMA+0.8sigma")
    self.calcMarginsButton.toolTip = "Calculates margins from the margin recepie."
    self.calcMarginsButton.enabled = True
    parametersFormLayout.addRow(self.calcMarginsButton)
    #
    # PTV Button
    #
    self.createPTVButton = qt.QPushButton("2e: Create margin PTV")
    self.createPTVButton.toolTip = "Creates the PTV from CTV and registration files (needs planning CT)."
    self.createPTVButton.enabled = False
    parametersFormLayout.addRow(self.createPTVButton)
    
    #
    # ITV Button
    #
    self.itvButton = qt.QPushButton("2f: Create oldfashioned ITV from CTV and registration")
    self.itvButton.toolTip = "Creates the ITV from CTV and registration files."
    self.itvButton.enabled = False
    self.itvButton.visible = False
    parametersFormLayout.addRow(self.itvButton)

    #
    # Color Button
    #
    self.colorButton = qt.QPushButton("Change contour color and thickness")
    self.colorButton.toolTip = "Changes contour color and thickness of closed surface for better display."
    self.colorButton.enabled = False
    parametersFormLayout.addRow(self.colorButton)

    #
    # Table with amplitudes
    #

    self.table = qt.QTableWidget()
    self.table.setColumnCount(3)
    self.table.setHorizontalHeaderLabels(["L-R", "A-P", "I-S"])
    self.table.setRowCount(2)
    self.table.setVerticalHeaderLabels(["Amplitude", "Margin"])
    # self.table.setEditTriggers(qt.QAbstractItemView.NoEditTriggers)
    self.table.enabled = True
    parametersFormLayout.addRow(self.table)
    #Table items
    self.item={}
    n = 0
    for i in range(2):
        for j in range(3):
            self.item[n] = qt.QTableWidgetItem()
            self.table.setItem(i, j, self.item[n])
            n += 1

    # connections
    self.findAmplitudesButton.connect('clicked(bool)', self.onFindAmplitudes)
    self.loadContoursButton.connect('clicked(bool)', self.onLoadContoursButton)
    self.registerButton.connect('clicked(bool)', self.onRegisterButton)
    self.midVButton.connect('clicked(bool)', self.onMidVButton)
    self.exportMidVButton.connect('clicked(bool)', self.onExportMidVButton)
    self.averageButton.connect('clicked(bool)', self.onAverageButton)
    self.itvButton.connect('clicked(bool)', self.onItvButton)
    self.calcMarginsButton.connect('clicked(bool)', self.onCalcMarginsButton)
    self.createPTVButton.connect('clicked(bool)', self.onCreatePTVButton)
    self.colorButton.connect('clicked(bool)', self.onColorButton)
    self.registerMidButton.connect('clicked(bool)', self.onRegisterMidButton)
    self.inputPlanCTSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onPlanCTChange)
    self.inputContourSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onContourChange)
    self.refPhaseSpinBox.connect("valueChanged(int)", self.onRefPhaseChange)
    # self.patientComboBox.connect('currentIndexChanged(QString)', self.setSeriesComboBox)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh buttons state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    self.findAmplitudesButton.enabled = self.inputContourSelector.currentNode()
    self.itvButton.enabled = self.inputContourSelector.currentNode()
    self.inputContourSelector.enabled = self.inputContourSelector.currentNode()
    self.createPTVButton.enabled = self.inputContourSelector.currentNode() and self.inputPlanCTSelector.currentNode()
    self.colorButton.enabled = self.inputContourSelector.currentNode()

  def onPlanCTChange(self, planningCT):
    if planningCT is None:
      self.createPTVButton.enabled = False
      return
    self.createPTVButton.enabled = self.inputContourSelector.currentNode()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]
    if patient is not None:
      patient.fourDCT[10].node = planningCT

  def onContourChange(self, targetContour):
      if targetContour is not None:
          patientNumber = self.patientComboBox.currentIndex
          patient = self.patientList[patientNumber]
          if patient is not None:
            patient.fourDCT[10].contour = targetContour
            # print patient.ID + "has now" + patient.fourDCT[10].node.GetName()
      self.findAmplitudesButton.enabled = True
      self.createPTVButton.enabled = self.inputPlanCTSelector.currentNode()
      self.colorButton.enabled = True

  def onRefPhaseChange(self, refPhase):
      patientNumber = self.patientComboBox.currentIndex
      patient = self.patientList[patientNumber]
      if patient is not None:
          patient.refPhase = refPhase
  
  def onFindAmplitudes(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    skipPlanRegistration = False
    if self.contourIn4D.checkState() == 2:
      skipPlanRegistration = True

    showContours = False
    if self.showContours.checkState() == 2:
      showContours = True

    axisOfMotion = False
    if self.axisOfMotionCheckBox.checkState() == 2:
      axisOfMotion = True

    if patient.fourDCT[10].contour is None:
      self.qtMessage("No contour was set.")
      return
    
    #Calculate amplitudes
    exitString = logic.calculateMotion(patient, skipPlanRegistration, showContours, axisOfMotion)
    if exitString:
      self.qtMessage(exitString)
      return
    n = 0
    for i in range(3):
      self.item[n].setText(str(round(patient.amplitudes[i], 2)))
      self.item[n+3].setText("")
      n += 1


  def onLoadContoursButton(self):
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if  len(patient.structureSet.uid) == 0:
      self.qtMessage("Can't get Structure Set DICOM data for " + patient.ID)
      return

    if not patient.loadStructureSet():
      self.qtMessage("Can't load Contours - check python console")
      return

    self.findAmplitudesButton.enabled = True
    self.inputContourSelector.enabled = True
    self.itvButton.enabled = True

  def onRegisterButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    planToAll = False
    if self.planToAll.checkState() == 2:
      planToAll = True
    exitString = logic.register(patient, planToAll)
    if exitString:
      self.qtMessage(exitString)
      return

  def onMidVButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    if self.planToAll.checkState() == 2:
      exitString = logic.createMidVentilationFromPlanningCT(patient)
    else:
      exitString = logic.createMidVentilation(patient)
    if exitString:
      self.qtMessage(exitString)
      return

  def onExportMidVButton(self):
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]
    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    #Load mid Ventilation first
    if patient.midVentilation.node is None:
      self.onMidVButton()
      if patient.midVentilation.node is None:
        self.qtMessage("Can't load/make midVentilation CT.")
        return

    #And export it
    if patient.exportMidV():
      self.qtMessage("Exported MidVentilation as DICOM to: " + patient.midVentilation.directory)
    else:
      self.qtMessage("Can't export MidVentilation, check python console")

  def onAverageButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    exitString = logic.createAverageFrom4DCT(patient)
    if exitString:
      self.qtMessage(exitString)
      return

  def onRegisterMidButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    exitString = logic.registerMidV(patient)
    if exitString:
      self.qtMessage(exitString)
      return


  def onItvButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]

    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    skipPlanRegistration = False
    if self.contourIn4D.checkState() == 2:
        skipPlanRegistration = True

    showContours = False
    if self.showContours.checkState() == 2:
        showContours = True

    exitString = logic.createITV(patient, skipPlanRegistration, showContours)
    if exitString:
      self.qtMessage(exitString)
      return

  def onCalcMarginsButton(self):
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]
    #Copy values from table to patient (user can also change this values)
    for i in range(3):
      if not self.item[i].text():
        self.qtMessage("No inputs in table.")
        return
      try:
        number = float(self.item[i].text())
      except AttributeError or ValueError:
        self.qtMessage("Please input numbers for amplitude")
      patient.amplitudes[i] = number
    SSigma = self.SSigmaSpinBox.value
    Rsigma = self.RsigmaSpinBox.value
    if not patient.calculatePTVmargins(SSigma, Rsigma):
      self.qtMessage("Can't calculate PTV margins")
      return
    for i in range(3):
      self.item[i+3].setText(str(round(patient.ptvMargins[i], 2)))

  def onCreatePTVButton(self):
    logic = FindMarginsLogic()
    patientNumber = self.patientComboBox.currentIndex
    patient = self.patientList[patientNumber]
    targetContour = self.inputContourSelector.currentNode()

    if patient is None:
      self.qtMessage("Can't find patient.")
      return

    SSigma = self.SSigmaSpinBox.value
    Rsigma = self.RsigmaSpinBox.value

    patient.fourDCT[10].contour = targetContour

    if self.keepAmplituedCheckBox.checkState() == 2:
      keepAmplitudes = True
    else:
      keepAmplitudes = False

    axisOfMotion = False
    if self.axisOfMotionCheckBox.checkState() == 2:
      axisOfMotion = True

    exitString = logic.createPTV(patient, SSigma, Rsigma, keepAmplitudes, axisOfMotion)
    if exitString and exitString.find("Created ") < 0:
      self.qtMessage(exitString)
      return

    for i in range(3):
      self.item[i].setText(str(round(patient.amplitudes[i], 2)))
      self.item[i+3].setText(str(round(patient.ptvMargins[i], 2)))

    self.qtMessage(exitString)

  def onColorButton(self):
    logic = FindMarginsLogic()
    targetContour = self.inputContourSelector.currentNode()
    exitString = logic.setColorAndThickness(targetContour)
    if exitString:
      self.qtMessage(exitString)
      return

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
              patientID = slicer.dicomDatabase.instanceValue(instance, self.tags['patientID'])
            except RuntimeError:
                # this indicates that the particular instance is no longer
                # accessible to the dicom database, so we should ignore it here
              continue
            serialDescription = slicer.dicomDatabase.instanceValue(instance, self.tags['seriesDescription'])
            studyDescription = slicer.dicomDatabase.instanceValue(instance, self.tags['studyDescription'])
            modality = slicer.dicomDatabase.instanceValue(instance, self.tags['modality'])
            if studyDescription.upper().find('PLAN') > -1 and studyDescription.upper().find('REPLAN') <= -1 and modality == "CT" and serialDescription.find('%') <= -1:
              newPatient.fourDCT[10].uid = series
              newPatient.fourDCT[10].file = files[0]
              newPatient.fourDCT[10].name = serialDescription
              print "CT plan for patient " + patientName + ": " + studyDescription + ", seriesID: ", series

            # print "Series date: " + slicer.dicomDatabase.instanceValue(instance,self.tags['seriesDate'])
            # if len(slicer.dicomDatabase.instanceValue(instance,self.tags['seriesDate'])) > 0:
            #   print "Hello"
            #   newPatient.planCT.uid = series
            #   newPatient.planCT.file = files[0]

            # print serialDescription
            if serialDescription.find('Structure Sets') > -1:
              newPatient.structureSet.uid = series

            if serialDescription.find('%') > -1:        # phase of 4D scan
              for i in range(0, 100, 10):
                tmpName = str(i) + ".0%"
                if serialDescription.find(tmpName) > -1:
                  #Special case for 0.0%
                  if i == 0:
                    position = serialDescription.find(tmpName)
                    try:
                      int(serialDescription[position-1])
                      continue
                    except ValueError:
                      if serialDescription.find(" " + tmpName) < 0 and not serialDescription == tmpName:
                        continue
                  # print patientID + " found " + serialDescription + " so " + files[0]
                  newPatient.fourDCT[i/10].uid = series
                  # print "4D phase found: ", i/10
                  newPatient.fourDCT[i/10].file = files[0]
                  if len(newPatient.patientDir) == 0:
                    newPatient.patientDir = os.path.dirname(files[0])

                if len(newPatient.vectorDir) == 0 and os.path.exists(files[0]):
                    dicomDir = os.path.dirname(files[0])
                    newPatient.vectorDir = dicomDir + "/VectorFields/"
                    if not os.path.exists(newPatient.vectorDir):
                        os.makedirs(newPatient.vectorDir)
                        print "Created " + newPatient.vectorDir

      newPatient.databaseNumber = nPatient
      newPatient.ID = patientID
      newPatient.name = slicer.dicomDatabase.instanceValue(instance, self.tags['patientName'])
      self.patientList.append(newPatient)

      nPatient += 1

  def qtMessage(self, message):
    print(message)
    self.info = qt.QMessageBox()
    self.info.setText(message)
    self.info.exec_()
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

  def register(self, patient, planToAll = False):
    refPhase = patient.refPhase

    self.delayDisplay("Starting registration")

    for i in range(0, 10):
      #This is when we want register all phases to planning ct
      if not planToAll:
        if not i == refPhase:
          continue

      patient.refPhase = i
      patient.createPlanParameters()
      if patient.getTransform(10):
        print "Planning transform already exist."
        slicer.mrmlScene.RemoveNode(patient.fourDCT[10].transform)
        patient.fourDCT[10].transform = None
      else:
        print "Registering planning CT"
        if not patient.loadDicom(10):
          self.setDisplay()
          return "Cant load planning CT."

        if not patient.loadDicom(patient.refPhase):
          self.setDisplay()
          return "Can't load reference phase"

        self.setDisplay("Registering planning CT to reference phase: " + str(refPhase))
        patient.regParameters.movingNode = patient.fourDCT[10].node.GetID()
        patient.regParameters.referenceNode = patient.fourDCT[patient.refPhase].node.GetID()
        patient.regParameters.register()

        if planToAll:
          slicer.mrmlScene.RemoveNode(patient.fourDCT[i].node)
          patient.fourDCT[i].node = None

    #We don't need 4D registration, when plan to all
    if planToAll:
      self.setDisplay()
      return "Finished with registration"

    # Prepare everything for 4D registration
    patient.refPhase = refPhase
    patient.create4DParameters()

    for i in range(0,10):
      if i == refPhase:
        continue

      patient.regParameters.referenceNumber = str(i) + "0"
      if patient.getTransform(i):
        self.delayDisplay("Transform for phase " + str(i) + "0% already exist.")
        slicer.mrmlScene.RemoveNode(patient.fourDCT[i].transform)
        patient.fourDCT[i].transform = None
        continue
      else:
        self.setDisplay( "Registering phase " + str(i) + "0%.")
        patient.regParameters.referenceNumber = str(i) + "0"
        if not patient.loadDicom(refPhase):
          self.setDisplay("Can't load reference phase")
          continue
        if not patient.loadDicom(i):
          self.setDisplay("Can't load phase " + str(i) + "0%.")
          continue

        patient.regParameters.movingNode = patient.fourDCT[refPhase].node.GetID()
        patient.regParameters.referenceNode = patient.fourDCT[i].node.GetID()
        patient.regParameters.register()

        slicer.mrmlScene.RemoveNode(patient.fourDCT[i].node)
        patient.fourDCT[i].node = None

        slicer.mrmlScene.RemoveNode(patient.fourDCT[refPhase].node)
        patient.fourDCT[refPhase].node = None
    self.setDisplay()
    return "Finished with registration."

  def calculateMotion(self, patient, skipPlanRegistration, showContours, axisOfMotion = False, showPlot = True):
    # logging.info('Processing started')

    origins = np.zeros([3, 10])
    relOrigins = np.zeros([3, 10])
    minmaxAmplitudes = [[-1e3, -1e3, -1e3], [1e3, 1e3, 1e3]]
    amplitudes = [0, 0, 0]
    patient.amplitudes = {}
    parentNodeID = ""

    refPhase = patient.refPhase

    #This is the relative difference between planning CT and reference position
    #Amplitudes are shifted for this value, so we can get an estimate, where is our planning CT in 4DCT
    if patient.fourDCT[10].contour is None:
      return "Can't find contour"

    planOrigins = self.getCenterOfMass(patient.fourDCT[10].contour)
    print "planorigins: ", planOrigins
    contourName = patient.fourDCT[10].contour.GetName().replace("_Contour", "")
    self.setDisplay("Calculating motion of " + contourName)

    #Find parent hierarchy, if we want to show contours
    if showContours:
      subjectHierarchyNode = slicer.util.getNode(contourName + "*_SubjectHierarchy")
      if subjectHierarchyNode:
        parentNodeID = subjectHierarchyNode.GetParentNodeID()

    #If there's a labelmap, then contours are not propagated right.
    #This is a workaround
    contourLabelmap = patient.fourDCT[10].contour.GetLabelmapImageData()
    if contourLabelmap:
      patient.fourDCT[10].contour.SetAndObserveLabelmapImageData(None)
    
    if skipPlanRegistration:
        contour = patient.fourDCT[10].contour
    else:
        #Propagate contour
        contour = self.propagateContour(patient, 10, showContours, None, parentNodeID)
        if contour is None:
          self.setDisplay()
          return "Can't propagate contour to reference phase."

    patient.fourDCT[refPhase].contour = contour
    origins[:, refPhase] = self.getCenterOfMass(contour)
    print "reference origins: ", origins[:, refPhase]
    relOrigins[:, refPhase] = [0, 0, 0]
    relOrigins[:, refPhase] += origins[:, refPhase] - planOrigins

    # Propagation in 4D
    patient.create4DParameters()
    for i in range(0, 10):
      if i == refPhase:
        continue

      #Create & propagate contour
      contour = self.propagateContour(patient, i, showContours, None, parentNodeID)
      if contour is None:
        print "Can't propagate contour for phase " + str(i) + "0 %"
        continue
      patient.fourDCT[i].contour = contour
      origins[:, i] = self.getCenterOfMass(contour)
      if not showContours:
          slicer.mrmlScene.RemoveNode(contour)
          patient.fourDCT[i].contour = None
    if not showContours and not skipPlanRegistration:
        slicer.mrmlScene.RemoveNode(patient.fourDCT[refPhase].contour)
        patient.fourDCT[refPhase].contour = None

    # Find axis of motion
    if axisOfMotion:
      matrix_W = self.findAxisOfMotion(origins)
      if matrix_W is None:
        self.setDisplay()
        return "Can't calculate axis of motion"
      #This is turned off for the moment, because we can't add margins in arbitrary direction
      origins = np.dot(matrix_W.T, origins)
      patient.matrix = matrix_W

    #Find relative motion
    for i in range(0, 10):
      relOrigins[:, i] = origins[:, i] - origins[:, refPhase] + relOrigins[:, refPhase]

    # Absolute motion & max & min motion
    relOrigins = np.vstack([relOrigins, np.zeros([1, 10])])
    for j in range(0, 10):
      amplitude = 0
      for i in range(0, 3):
        #Max
        if relOrigins[i, j] > minmaxAmplitudes[0][i]:
          minmaxAmplitudes[0][i] = relOrigins[i, j]
        #Min
        if relOrigins[i, j] < minmaxAmplitudes[1][i]:
          minmaxAmplitudes[1][i] = relOrigins[i, j]
        amplitude += relOrigins[i, j]*relOrigins[i, j]
      relOrigins[3, j] = np.sqrt(amplitude)
      patient.fourDCT[j].origin = origins[:, i]
      patient.fourDCT[j].relOrigin = relOrigins[:, i]

    #Find & save peak-to-peak amplitudes
    amplitudesTmp = [-1, -1, -1]
    for j in range(3):
      amplitudesTmp[j] = abs(minmaxAmplitudes[0][j] - minmaxAmplitudes[1][j])
      if amplitudesTmp[j] > amplitudes[j]:
        amplitudes[j] = amplitudesTmp[j]
    patient.amplitudes = amplitudes
    patient.minmaxAmplitudes = minmaxAmplitudes
    print amplitudes
    # Plot
    if showPlot:
      self.plotMotion(relOrigins, contourName)

    if contourLabelmap:
      patient.fourDCT[10].contour.SetAndObserveLabelmapImageData(contourLabelmap)

    self.setDisplay()
    self.delayDisplay("Finished with calculating motion.")
    return 

  def createMidVentilation(self, patient):

    transformLogic = slicer.modules.transforms.logic()
    mathMultiply = vtk.vtkImageMathematics()
    mathAddVector = vtk.vtkImageMathematics()
    mathAddCT = vtk.vtkImageMathematics()

    vectorImageData = vtk.vtkImageData()
    ctImageData = vtk.vtkImageData()

    gridAverageTransform = slicer.vtkOrientedGridTransform()

    refPhase = patient.refPhase

    #Check if midVentilation is already on disk
    if patient.loadMidV(refPhase):
      return "Loaded mid Ventilation."

    patient.create4DParameters()
    self.delayDisplay("Starting calculation of mid Ventilation")

    firstRun = True
    # vector = slicer.vtkMRMLVectorVolumeNode()
    # slicer.mrmlScene.AddNode(vector)
    for i in range(0, 10):

        if i == refPhase:
            continue

        patient.regParameters.referenceNumber = str(i) + "0"
        self.setDisplay("Getting vector field for phase" + str(i) + "0 %")
        if not patient.getVectorField(i):
          self.setDisplay()
          return "Can't get vector field for phase " + str(i) + "0 %"

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
    storageNode = slicer.vtkMRMLTransformStorageNode()
    slicer.mrmlScene.AddNode(storageNode)
    transformNode.SetAndObserveStorageNodeID(storageNode.GetID())
    transformNode.SetName('MidV_ref' + str(refPhase))
    slicer.mrmlScene.AddNode(transformNode)
    transformNode.SetAndObserveTransformFromParent(gridAverageTransform)
    # return

    midVCT = slicer.vtkMRMLScalarVolumeNode()
    slicer.mrmlScene.AddNode(midVCT)
    midVCT.SetName(patient.ID + "_midV_ref"+str(refPhase))

    firstRun = True
    for i in range(0, 10):
        self.setDisplay("Propagating phase " + str(i) + "0 % to midV position.")
        patient.regParameters.referenceNumber = str(i) + "0"

        if not patient.loadDicom(i):
          self.setDisplay()
          return "Can't get CT for phase " + str(i) + "0 %"

        ctNode = patient.fourDCT[i].node

        if not i == refPhase:
            if not patient.getTransform(i):
              self.setDisplay()
              return "Can't get transform for phase " + str(i) + "0 %"

            patient.fourDCT[i].transform.Inverse()
            ctNode.SetAndObserveTransformNodeID(patient.fourDCT[i].transform.GetID())
            if not transformLogic.hardenTransform(ctNode):
              self.setDisplay()
              return "Can't harden transform for phase " + str(i) + "0 %"

            slicer.mrmlScene.RemoveNode(patient.fourDCT[i].transform)
            patient.fourDCT[i].transform = None

        # ctNode.ApplyTransform(gridAverageTransform)
        ctNode.SetAndObserveTransformNodeID(transformNode.GetID())
        if not transformLogic.hardenTransform(ctNode):
          self.setDisplay()
          return "Can't harden transform for phase " + str(i) + "0 %"

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
    patient.midVentilation.node = midVCT

    #Save midVCT

    slicer.util.saveNode(midVCT, patient.patientDir + "/" + midVCT.GetName() + ".nrrd")

    #Save transformation as vector field (it crashes when saving as transform)
    transformLogic = slicer.modules.transforms.logic()
    if not patient.loadDicom(refPhase):
      self.setDisplay()
      return "Can't get CT for phase " + str(i) + "0 %"
    vf = transformLogic.CreateDisplacementVolumeFromTransform(transformNode, patient.fourDCT[refPhase].node, False)
    slicer.mrmlScene.RemoveNode(patient.fourDCT[refPhase].node)
    patient.fourDCT[refPhase].node = None
    slicer.util.saveNode(vf,patient.vectorDir + "/" + vf.GetName() + ".nrrd")
    slicer.mrmlScene.RemoveNode(vf)
    self.setDisplay()
    return "Created mid Ventilation."

  def createMidVentilationFromPlanningCT(self, patient):

    mathMultiply = vtk.vtkImageMathematics()
    mathAddVector = vtk.vtkImageMathematics()

    vectorImageData = vtk.vtkImageData()

    gridAverageTransform = slicer.vtkOrientedGridTransform()

    #Check if midVentilation is already on disk
    if patient.loadMidV(10):
      return "Loaded mid Ventilation from disk"

    self.delayDisplay("Starting calculation of mid Ventilation from planning CT")

    firstRun = True
    # vector = slicer.vtkMRMLVectorVolumeNode()
    # slicer.mrmlScene.AddNode(vector)
    for i in range(0, 10):
        patient.refPhase = i
        patient.createPlanParameters()
        self.setDisplay("Getting vector field for phase" + str(i) + "0 %")
        if not patient.getVectorField(i):
          return "Can't get vector field for phase " + str(i) + "0 %"
          self.setDisplay()

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
            firstRun = False
        else:
            mathAddVector.SetOperationToAdd()
            mathAddVector.SetInput1Data(mathMultiply.GetOutput())
            mathAddVector.SetInput2Data(vectorImageData)
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

    # Load planning CT
    self.setDisplay("Propagating planning CT to MidV phase.")
    if not patient.loadDicom(10):
      self.setDisplay()
      return "Can't find planning CT."
    #Save transformation as vector field (it crashes when saving as transform)
    transformLogic = slicer.modules.transforms.logic()
    vf = transformLogic.CreateDisplacementVolumeFromTransform(transformNode, patient.fourDCT[10].node, False)
    slicer.util.saveNode(vf, patient.vectorDir + "/" + vf.GetName() + ".nrrd")
    slicer.mrmlScene.RemoveNode(vf)

    midVCT = slicer.vtkMRMLScalarVolumeNode()
    midVCT.Copy(patient.fourDCT[10].node)
    slicer.mrmlScene.AddNode(midVCT)
    midVCT.SetName(patient.ID + "_midV_ref10")
    midVCT.SetAndObserveTransformNodeID(transformNode.GetID())
    transformLogic.hardenTransform(midVCT)
    self.setDisplay()
    return "Created midVentilation from planning CT."

  def registerMidV(self, patient):
    if not patient.loadMidV(patient.refPhase):
      return "Can't get mid ventilation CT."

    patient.createPlanParameters()
    patient.regParameters.referenceNumber = "MidV_ref" + str(patient.refPhase)

    if patient.getTransform(11):
      return

    if not patient.loadDicom(10):
      return "Can't get planning CT."

    self.setDisplay("Starting registration of planning CT to midVentilation CT.")
    patient.regParameters.movingNode = patient.fourDCT[10].node.GetID()
    patient.regParameters.referenceNode = patient.midVentilation.node.GetID()
    patient.regParameters.register()
    self.setDisplay()

  def createAverageFrom4DCT(self,patient):
    mathMultiply = vtk.vtkImageMathematics()
    mathAddCT = vtk.vtkImageMathematics()
    ctImageData = vtk.vtkImageData()

    self.delayDisplay("Starting process")
    midVCT = slicer.vtkMRMLScalarVolumeNode()
    slicer.mrmlScene.AddNode(midVCT)
    midVCT.SetName(patient.ID + "average4DCT")
    firstRun = True
    for i in range(0, 10):
        if not patient.loadDicom(i):
          self.setDisplay()
          return "Can't get CT for phase " + str(i) + "0 %"

        self.setDisplay("Getting data from phase " + str(i) + "0 %")
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
    self.setDisplay()
    return "Finished with registration"

  def createPTV(self, patient, SSigma, Rsigma, keepAmplitudes, axisOfMotion):
    import vtkSlicerContourMorphologyModuleLogic
    from vtkSlicerContoursModuleMRML import vtkMRMLContourNode

    # First we need planning CT for reference
    if not patient.loadDicom(10):
        return "Can't get planning CT."

    ## Propagate Contour from Plan to MidV:
    # contour = self.propagateContour(patient, 11, True)
    # if contour is None:
    #   print "Can't get contour."
    #   return
    # patient.fourDCT[10].contour = contour
    contour = patient.fourDCT[10].contour
    self.delayDisplay("Calculating PTV from " + contour.GetName())
    #Calculate motion
    if not keepAmplitudes:
      self.calculateMotion(patient, True, False, axisOfMotion, True)
    #Create contourmorphology node and set parameters
    self.setDisplay("Adding margins to " + contour.GetName())
    cmNode = vtkSlicerContourMorphologyModuleLogic.vtkMRMLContourMorphologyNode()
    cmLogic = vtkSlicerContourMorphologyModuleLogic.vtkSlicerContourMorphologyModuleLogic()

    slicer.mrmlScene.AddNode(cmNode)
    cmNode.SetScene(slicer.mrmlScene)
    cmNode.SetAndObserveReferenceVolumeNode(patient.fourDCT[10].node)
    cmNode.SetOperation(cmNode.Expand)
    cmNode.SetAndObserveContourANode(contour)

    cmLogic.SetAndObserveContourMorphologyNode(cmNode)
    cmLogic.SetAndObserveMRMLScene(slicer.mrmlScene)

    if not patient.calculatePTVmargins(SSigma, Rsigma):
      self.setDisplay()
      return "Can't calculate margins."

    cmNode.SetXSize(patient.ptvMargins[0])
    cmNode.SetYSize(patient.ptvMargins[1])
    cmNode.SetZSize(patient.ptvMargins[2])
    cmLogic.MorphContour()

    print patient.ptvMargins
    #Find newly created contour and rename it

    ptv = slicer.util.getNode('Expanded*Contour')
    if not ptv:
      return "Can't find PTV contour in subject Hierarchy"

    name = patient.ID + "_PTV_S" + str(SSigma) + "_s" + str(Rsigma)
    name = slicer.mrmlScene.GenerateUniqueName(name)
    ptv.SetName(name)
    self.setDisplay()
    return "Created PTV with name: " + name

  def setColorAndThickness(self, contour):
    if not contour:
      return "No Contour was set."

    index = contour.GetName().find('_Contour')
    if index < 0:
      return "Can't find name of contour"

    contourName = contour.GetName()[0:index]
    ribbonNode = slicer.util.getNode(contourName + '*Ribbon*')
    closedNode = slicer.util.getNode(contourName + '*Closed*')

    if not closedNode:
      return "No closed surface node was set for " + contourName

    #Set thickness
    closedNode.SetSliceIntersectionThickness(3)

    #Set color; Either copy it or set new one
    if ribbonNode:
      closedNode.SetColor(ribbonNode.GetColor())
    else:
      closedNode.SetColor([1, 1, 0])

  def createITV(self,patient, skipPlanRegistration, showContours):
    #TODO: Doesn't work, needs fixing.
    import vtkSlicerContourMorphologyModuleLogic
    from vtkSlicerContoursModuleMRML import vtkMRMLContourNode

    # First we need planning CT for reference
    if not patient.loadDicom(10):
        return "Can't get planning CT."

    #Create contourmorphology node and set parameters
    cmNode = vtkSlicerContourMorphologyModuleLogic.vtkMRMLContourMorphologyNode()
    cmLogic = vtkSlicerContourMorphologyModuleLogic.vtkSlicerContourMorphologyModuleLogic()

    slicer.mrmlScene.AddNode(cmNode)
    cmNode.SetScene(slicer.mrmlScene)
    cmNode.SetAndObserveReferenceVolumeNode(patient.fourDCT[10].node)
    cmNode.SetOperation(cmNode.Union)

    cmLogic.SetAndObserveContourMorphologyNode(cmNode)
    cmLogic.SetAndObserveMRMLScene(slicer.mrmlScene)

    refPhase = patient.refPhase

    if skipPlanRegistration:
        contour = patient.fourDCT[10].contour
    else:
        #Propagate contour
        contour = self.propagateContour(patient, 10, showContours)
        if contour is None:
            return "Can't propagate contour to reference phase."

    patient.fourDCT[refPhase].contour = contour

    # Create contour node
    itv = vtkMRMLContourNode()
    slicer.mrmlScene.AddNode(itv)
    itv.DeepCopy(contour)
    itv.SetName(patient.ID + "_ITV")
    self.setDisplayNode(itv)

    cmNode.SetAndObserveContourANode(itv)
    cmNode.SetAndObserveOutputContourNode(itv)

    # Propagation in 4D
    # TODO: Add option to display contours, otherwise delete nodes
    for i in range(0,10):
      if i == refPhase:
        continue
      self.setDisplay("Propagating phase: " + str(i) + "0 %")
      #Create & propagate contour
      contour = self.propagateContour(patient, i, showContours)
      if contour is None:
          self.delayDisplay( "Can't propagate contour for phase " + str(i) +"0 %")
          continue

      patient.fourDCT[i].contour = contour
      cmNode.SetAndObserveContourBNode(contour)

      if not showContours:
          slicer.mrmlScene.RemoveNode(contour)
          patient.fourDCT[i].contour = None

    if not showContours:
        slicer.mrmlScene.RemoveNode(patient.fourDCT[refPhase].contour)
        patient.fourDCT[refPhase].contour = None

  def propagateContour(self, patient, position, showContours, contour = None, parentNodeID = ""):
    from vtkSlicerContoursModuleMRML import vtkMRMLContourNode
    transformLogic = slicer.modules.transforms.logic()

    if position == 10 or position == 11:
      patient.createPlanParameters()
      if position == 11:
        patient.regParameters.referenceNumber = "MidV_ref" + str(patient.refPhase)
    else:
      patient.create4DParameters()
      patient.regParameters.referenceNumber = str(position) + "0"

    if not patient.getTransform(position):
      self.delayDisplay("Can't load transform")
      return None

    if position == 11:
      bspline = patient.midVentilation.transform
    else:
      bspline = patient.fourDCT[position].transform

    transform = vtk.vtkGeneralTransform()
    bspline.GetTransformToWorld(transform)
    transform.Update()

    # Load contour
    if contour is None:
      contour = vtkMRMLContourNode()
      if position == 10 or position == 11:
        contour.DeepCopy(patient.fourDCT[10].contour)
        if position == 11:
          contour.SetName(patient.fourDCT[10].contour.GetName() + "_midV")
        else:
          contour.SetName(patient.fourDCT[10].contour.GetName() + "_refPosition")
      else:
        contour.DeepCopy(patient.fourDCT[patient.refPhase].contour)
        contour.SetName(patient.fourDCT[patient.refPhase].contour.GetName() + "_phase" + str(position))
          
      slicer.mrmlScene.AddNode(contour)

      if showContours:
        self.setDisplayNode(contour)
        #Create subject hierarchy and add to contour set
        if len(parentNodeID) > 0:
          contourName = contour.GetName().replace("_Contour", "_SubjectHierarchy")
          subjectHierarchyNode = slicer.vtkMRMLSubjectHierarchyNode()
          subjectHierarchyNode.SetName(contourName)
          subjectHierarchyNode.SetLevel('SubSeries')
          # subjectHierarchyNode.SetAttribute('Directory',ctDirectory)
          slicer.mrmlScene.AddNode(subjectHierarchyNode)
          subjectHierarchyNode.SetParentNodeID(parentNodeID)
          subjectHierarchyNode.SetAssociatedNodeID(contour.GetID())

    contour.SetAndObserveTransformNodeID(bspline.GetID())
    if not transformLogic.hardenTransform(contour):
        self.delayDisplay("Can't harden transform.")
        slicer.mrmlScene.RemoveNode(bspline)
        return None

    slicer.mrmlScene.RemoveNode(bspline)
    return contour

  def setDisplayNode(self, contour, parentHierarchy = None):
      from vtkSlicerContoursModuleMRML import vtkMRMLContourModelDisplayNode

      if contour is None:
          self.delayDisplay("No input contour")
          return
      contour.RemoveAllDisplayNodeIDs()
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

  def plotMotion(self, relOrigins, contourName):
    ln = slicer.util.getNode(pattern='vtkMRMLLayoutNode*')
    ln.SetViewArrangement(25)

    # Get the first ChartView node
    cvn = slicer.util.getNode(pattern='vtkMRMLChartViewNode*')

    # Create arrays of data
    dn = {}
    for i in range(0, 4):
      dn[i] = slicer.mrmlScene.AddNode(slicer.vtkMRMLDoubleArrayNode())
      a = dn[i].GetArray()
      a.SetNumberOfTuples(10)
      for j in range(0,10):
        a.SetComponent(j, 0, j)
        a.SetComponent(j, 1, relOrigins[i, j])
        a.SetComponent(j, 2, 0)

    # Create the ChartNode,
    cn = slicer.mrmlScene.AddNode(slicer.vtkMRMLChartNode())

    # Add data to the Chart
    cn.AddArray('L-R', dn[0].GetID())
    cn.AddArray('A-P', dn[1].GetID())
    cn.AddArray('I-S', dn[2].GetID())
    cn.AddArray('abs', dn[3].GetID())

    # Configure properties of the Chart
    cn.SetProperty('default', 'title','Relative ' + contourName + ' motion')
    cn.SetProperty('default', 'xAxisLabel', 'phase')
    cn.SetProperty('default', 'yAxisLabel', 'position [mm]')
    cn.SetProperty('default', 'showGrid', 'on')
    cn.SetProperty('default', 'xAxisPad', '1')
    cn.SetProperty('default', 'showMarkers', 'on')

    cn.SetProperty('L-R', 'color', '#0000ff')
    cn.SetProperty('A-P', 'color', '#00ff00')
    cn.SetProperty('I-S', 'color', '#ff0000')
    cn.SetProperty('abs', 'color', '#000000')

    # Set the chart to display
    cvn.SetChartNodeID(cn.GetID())

  def findAxisOfMotion(self, origins):
    #Following guide from: http://sebastianraschka.com/Articles/2014_pca_step_by_step.html

    #scale factor for better display:
    scale = 100

    #Calculate mean position
    meanVector = [0, 0 ,0]
    for i in range(3):
      meanVector[i] = np.mean(origins[i, :])


    #Computing covariance matrix
    convMatrix = np.cov([origins[0, :], origins[1, :], origins[2, :]])

    #Get eigenvectors
    eig_val, eig_vec = np.linalg.eig(convMatrix)

    # Make a list of (eigenvalue, eigenvector) tuples
    eig_pairs = [(np.abs(eig_val[i]), eig_vec[:,i]) for i in range(len(eig_val))]

    # Sort the (eigenvalue, eigenvector) tuples from high to low
    eig_pairs.sort()
    # eig_pairs.reverse()
    matrix_w = np.hstack((eig_pairs[0][1].reshape(3, 1),
                          eig_pairs[1][1].reshape(3, 1),
                          eig_pairs[2][1].reshape(3, 1)))
    print('Matrix W:\n', matrix_w)

    #Create linear transform for contour propagation

    vtkMatrix = vtk.vtkMatrix4x4()
    transform = slicer.vtkMRMLLinearTransformNode()
    slicer.mrmlScene.AddNode(transform)

    for i in range(3):
      for j in range(3):
        vtkMatrix.SetElement(j, i, matrix_w[i, j])

    transform.SetAndObserveMatrixTransformFromParent(vtkMatrix)

    #Plot eigenvectors from mean position
    fiducials = slicer.vtkMRMLMarkupsFiducialNode()
    displayNode = slicer.vtkMRMLMarkupsDisplayNode()
	# vtkNew<vtkMRMLMarkupsFiducialStorageNode> wFStorageNode;
    slicer.mrmlScene.AddNode(displayNode)
    slicer.mrmlScene.AddNode(fiducials)
    fiducials.SetAndObserveDisplayNodeID(displayNode.GetID())
    fiducials.AddFiducialFromArray(meanVector, "Mean Position")
    for i in range(len(eig_vec)):
      # fiducials.AddFiducialFromArray(meanVector + scale * eig_vec[i], " P " + str(i+1))
      #Plot ruler
      ruler = slicer.vtkMRMLAnnotationRulerNode()
      displayRuler = slicer.vtkMRMLAnnotationLineDisplayNode()
      displayRuler.SetLabelVisibility(0)
      displayRuler.SetMaxTicks(0)
      displayRuler.SetLineWidth(5)
      slicer.mrmlScene.AddNode(displayRuler)
      slicer.mrmlScene.AddNode(ruler)
      ruler.SetAndObserveDisplayNodeID(displayRuler.GetID())
      ruler.SetPosition1(meanVector)
      ruler.SetPosition2(meanVector + scale * eig_vec[i])

    return matrix_w

  def setDisplay(self, message = None):
    """This creates display with message or turns it off, if there is none.
    """
    if not message:
      if self.info:
        self.info.visible = False
      return

    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message,self.info)
    self.infoLayout.addWidget(self.label)
    self.info.visible = True

  def delayDisplay(self, message, msec=1000):
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
