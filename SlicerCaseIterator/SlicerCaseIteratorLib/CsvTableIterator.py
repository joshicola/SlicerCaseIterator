# =========================================================================
#  Copyright Joost van Griethuysen
#
#  Licensed under the 3-Clause BSD-License (the "License");
#  you may not use this file except in compliance with the License.
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ========================================================================

import os
import ast
from collections import deque
import qt, ctk, slicer

from . import IteratorBase

# ------------------------------------------------------------------------------
# SlicerCaseIterator CSV iterator Widget
# ------------------------------------------------------------------------------


class CaseTableIteratorWidget(IteratorBase.IteratorWidgetBase):
    """This class governs the widget interface for Table Iterator."""

    def __init__(self):
        super(CaseTableIteratorWidget, self).__init__()

        self.tableNode = None
        self.tableStorageNode = None

    # ------------------------------------------------------------------------------
    def setup(self):
        """Setup the widget for display.

        Returns:
            QGroupBox: A reference to the widget to display in the extension
        """
        self.CsvInputGroupBox = qt.QGroupBox("CSV input for local files")

        CsvInputLayout = qt.QFormLayout(self.CsvInputGroupBox)

        #
        # Input CSV Path
        #
        self.batchTableSelector = slicer.qMRMLNodeComboBox()
        self.batchTableSelector.nodeTypes = ["vtkMRMLTableNode"]
        self.batchTableSelector.addEnabled = True
        self.batchTableSelector.selectNodeUponCreation = True
        self.batchTableSelector.renameEnabled = True
        self.batchTableSelector.removeEnabled = True
        self.batchTableSelector.noneEnabled = False
        self.batchTableSelector.setMRMLScene(slicer.mrmlScene)
        self.batchTableSelector.toolTip = (
            "Select the table representing the cases to process."
        )
        CsvInputLayout.addRow(self.batchTableSelector)

        self.batchTableView = slicer.qMRMLTableView()
        CsvInputLayout.addRow(self.batchTableView)
        self.batchTableView.show()

        #
        # Parameters Area
        #
        self.parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        self.parametersCollapsibleButton.text = "Parameters"
        CsvInputLayout.addWidget(self.parametersCollapsibleButton)

        # Layout within the dummy collapsible button
        parametersFormLayout = qt.QFormLayout(self.parametersCollapsibleButton)

        #
        # Input parameters GroupBox
        #

        self.inputParametersGroupBox = qt.QGroupBox("Input parameters")
        parametersFormLayout.addRow(self.inputParametersGroupBox)

        inputParametersFormLayout = qt.QFormLayout(self.inputParametersGroupBox)

        #
        # Root Path
        #
        self.rootSelector = qt.QLineEdit()
        self.rootSelector.text = "path"
        self.rootSelector.toolTip = (
            "Location of the root directory to load from, "
            "or the column name specifying said "
            "directory in the input CSV"
        )
        inputParametersFormLayout.addRow("Root Column", self.rootSelector)

        #
        # Image Path
        #
        self.imageSelector = qt.QLineEdit()
        self.imageSelector.text = "image"
        self.imageSelector.toolTip = (
            "Name of the column specifying main image files in input CSV"
        )
        inputParametersFormLayout.addRow("Image Column", self.imageSelector)

        #
        # Mask Path
        #
        self.maskSelector = qt.QLineEdit()
        self.maskSelector.text = "mask"
        self.maskSelector.toolTip = (
            "Name of the column specifying main mask files in input CSV"
        )
        inputParametersFormLayout.addRow("Mask Column", self.maskSelector)

        #
        # Additional images
        #
        self.addImsSelector = qt.QLineEdit()
        self.addImsSelector.text = ""
        self.addImsSelector.toolTip = (
            "Comma separated names of the columns specifying "
            "additional image files in input CSV"
        )
        inputParametersFormLayout.addRow(
            "Additional images Column(s)", self.addImsSelector
        )

        #
        # Additional masks
        #
        self.addMasksSelector = qt.QLineEdit()
        self.addMasksSelector.text = ""
        self.addMasksSelector.toolTip = (
            "Comma separated names of the columns "
            "specifying additional mask files in input CSV"
        )
        inputParametersFormLayout.addRow(
            "Additional masks Column(s)", self.addMasksSelector
        )

        #
        # Connect Event Handlers
        #
        self.batchTableSelector.connect(
            "nodeActivated(vtkMRMLNode*)", self.onChangeTable
        )
        self.imageSelector.connect("textEdited(QString)", self.onChangeImageColumn)

        self.segmentationParametersGroupBox = qt.QGroupBox(
            "Mask interaction parameters"
        )
        parametersFormLayout.addRow(self.segmentationParametersGroupBox)

        segmentationParametersFormLayout = qt.QFormLayout(
            self.segmentationParametersGroupBox
        )

        #
        # Auto-redirect to SegmentEditor
        #
        self.chkAutoRedirect = qt.QCheckBox()
        self.chkAutoRedirect.checked = False
        self.chkAutoRedirect.toolTip = (
            'Automatically switch module to "SegmentEditor" when each case is loaded'
        )
        segmentationParametersFormLayout.addRow(
            "Go to Segment Editor", self.chkAutoRedirect
        )

        #
        # Save masks
        #
        self.chkSaveMasks = qt.QCheckBox()
        self.chkSaveMasks.checked = False
        self.chkSaveMasks.toolTip = (
            "save all initially loaded masks when proceeding to next case"
        )
        segmentationParametersFormLayout.addRow("Save loaded masks", self.chkSaveMasks)

        #
        # Save new masks
        #
        self.chkSaveNewMasks = qt.QCheckBox()
        self.chkSaveNewMasks.checked = True
        self.chkSaveNewMasks.toolTip = (
            "save all newly generated masks when proceeding to next case"
        )
        segmentationParametersFormLayout.addRow("Save new masks", self.chkSaveNewMasks)

        return self.CsvInputGroupBox

    # ------------------------------------------------------------------------------
    def enter(self):
        """Override for the enter function of the widget."""
        self.onChangeTable()

    # ------------------------------------------------------------------------------
    def is_valid(self):
        """Check for the validity of the current configuration.

        On success, this indicates that a batch can be started. Enabling/Disabling the
        "start batch" button depends on the result True/False.

        Returns:
            boolean: Validity of the current setting, if true the batch may be started.
        """
        return (
            self.batchTableSelector.currentNodeID != ""
            and self.imageSelector.text != ""
        )

    # ------------------------------------------------------------------------------
    def startBatch(self, reader=None):
        """Function to start the batch.

        In the derived class, this should store relevant nodes to keep track of
        important data.

        Args:
            reader (str, optional): The string representing the reader. Defaults to None.

        Returns:
            Iterator: Iterator class instance defining the dataset to iterate over.
                      Iterator contains functions for loading and storing a case.
        """
        self.tableNode = self.batchTableSelector.currentNode()
        self.tableStorageNode = self.tableNode.GetStorageNode()

        columnMap = self._parseConfig()

        self._iterator = CaseTableIteratorLogic(self.tableNode, columnMap)
        self._iterator.registerEventListener(
            CsvTableEventHandler(
                reader=reader,
                redirect=self.chkAutoRedirect.checked,
                saveNew=self.chkSaveNewMasks.checked,
                saveLoaded=self.chkSaveMasks.checked,
            )
        )
        return self._iterator

    # ------------------------------------------------------------------------------
    def cleanupBatch(self):
        """Clean up files and settings of the current batch."""
        if self._iterator:
            self._iterator.closeCase()
        self.tableNode = None
        self.tableStorageNode = None
        self._iterator = None

    # ------------------------------------------------------------------------------
    def onChangeTable(self):
        """Execute on table selection from the batchTableSelector qMRMLNodeComboBox."""
        self.batchTableView.setMRMLTableNode(self.batchTableSelector.currentNode())
        self.validate()

    # ------------------------------------------------------------------------------
    def onChangeImageColumn(self):
        """Execute on change to Image Filename"""
        self.validate()

    # ------------------------------------------------------------------------------
    def _parseConfig(self):
        """This parses the user input in the selectors of different column types.

        Returns:
            dict: Mapping requested columns to the correct keys
        """
        columnMap = {}

        if self.rootSelector.text != "":
            columnMap["root"] = str(self.rootSelector.text).strip()

        assert self.imageSelector.text != ""  # Image column is a required column
        columnMap["image"] = str(self.imageSelector.text).strip()

        if self.maskSelector.text != "":
            columnMap["mask"] = str(self.maskSelector.text).strip()

        if self.addImsSelector.text != "":
            columnMap["additionalImages"] = [
                str(c).strip() for c in self.addImsSelector.text.split(",")
            ]

        if self.addMasksSelector.text != "":
            columnMap["additionalMasks"] = [
                str(c).strip() for c in self.addMasksSelector.text.split(",")
            ]

        return columnMap


# ------------------------------------------------------------------------------
# SlicerCaseIterator CSV iterator
# ------------------------------------------------------------------------------


class CaseTableIteratorLogic(IteratorBase.IteratorLogicBase):
    """Table Case Iterator Logic class."""

    def __init__(self, tableNode, columnMap):
        super(CaseTableIteratorLogic, self).__init__()
        assert tableNode is not None, "No table selected! Cannot instantiate batch"

        # If the table was loaded from a file, get the directory containing the file
        # as reference for relative paths
        tableStorageNode = tableNode.GetStorageNode()
        if tableStorageNode is not None and tableStorageNode.GetFileName() is not None:
            self.csv_dir = os.path.dirname(tableStorageNode.GetFileName())
        else:  # Table did not originate from a file
            self.csv_dir = None

        # Get the actual table contained in the MRML node
        self.batchTable = tableNode.GetTable()

        # Dictionary holding the specified (and found) columns from the tableNode
        self.caseColumns = self._getColumns(columnMap)

        self.caseCount = (
            self.batchTable.GetNumberOfRows()
        )  # Counter equalling the total number of cases

    # ------------------------------------------------------------------------------
    def __del__(self):
        super(CaseTableIteratorLogic, self).__del__()
        self.logger.debug("Destroying CSV Table Iterator")
        self.batchTable = None
        self.caseColumns = None

    # ------------------------------------------------------------------------------
    def _getColumns(self, columnMap):
        """Retrieve validated columns from the columnMap that exist in the loaded table.

        Errors are created if they are not found in the loaded table.

        Args:
            columnMap (dict): Dictionary of the table columns used.

        Returns:
            dict: A validated key/value set of columns that exist in the table.
        """
        caseColumns = {}

        # Declare temporary function to parse out the user config and get the correct
        # columns from the batchTable
        def getColumn(key):
            """Get a column with a single value.

            Columns with multiple values have been removed.

            Args:
                key (str): Key of column to retrieve.
            """
            col = None
            if key in columnMap:
                col = self.batchTable.GetColumnByName(columnMap[key])
                assert col is not None, 'Unable to find column "%s" (key %s)' % (
                    columnMap[key],
                    key,
                )
            caseColumns[key] = col

        def getListColumn(key):
            """Retrieve a column with multiple values.

            Args:
                key (str): Key of column to retrieve.
            """
            col_list = []
            if key in columnMap:
                for c_key in columnMap[key]:
                    col = self.batchTable.GetColumnByName(c_key)
                    assert col is not None, 'Unable to find column "%s" (key %s)' % (
                        c_key,
                        key,
                    )
                    col_list.append(col)
            caseColumns[key] = col_list

        # Special case: Check if there is a column "patient" or "ID"
        # (used for additional naming of the case during logging)
        patientColumn = self.batchTable.GetColumnByName("patient")
        if patientColumn is None:
            patientColumn = self.batchTable.GetColumnByName("ID")
        if patientColumn is not None:
            caseColumns["patient"] = patientColumn

        # Get the other configurable columns
        getColumn("root")
        getColumn("image")
        getColumn("mask")
        getListColumn("additionalImages")
        getListColumn("additionalMasks")

        return caseColumns

    # ------------------------------------------------------------------------------
    def loadCase(self, case_idx):
        """Load the case from the table indicated by case_idx.

        Args:
            case_idx (int): The index of the desired case in the table.

        Returns:
            boolean: True if the case was loaded successfully.
        """
        assert (
            0 <= case_idx < self.caseCount
        ), "case_idx %d is out of range (n cases: %d)" % (case_idx, self.caseCount)

        if self.currentIdx is not None:
            self.closeCase()

        if "patient" in self.caseColumns:
            patient = self.caseColumns["patient"].GetValue(case_idx)
            self.logger.info(
                "Loading patient (%d/%d): %s...", case_idx + 1, self.caseCount, patient
            )
        else:
            self.logger.info("Loading patient (%d/%d)...", case_idx + 1, self.caseCount)

        root = self._getColumnValue("root", case_idx)

        # Load images
        im = self._getColumnValue("image", case_idx)
        im_node = self._loadImageNode(root, im)
        assert im_node is not None, "Failed to load main image"

        additionalImageNodes = []
        for im in self._getColumnValue("additionalImages", case_idx, True):
            add_im_node = self._loadImageNode(root, im)
            if add_im_node is not None:
                additionalImageNodes.append(add_im_node)

        # Load masks
        ma = self._getColumnValue("mask", case_idx)
        if ma is not None:
            ma_node = self._loadMaskNode(root, ma, im_node)
        else:
            ma_node = None

        additionalMaskNodes = []
        for ma in self._getColumnValue("additionalMasks", case_idx, True):
            add_ma_node = self._loadMaskNode(root, ma)
            if add_ma_node is not None:
                additionalMaskNodes.append(add_ma_node)

        self.parameterNode.SetParameter(
            "CaseData",
            {
                "InputImage_ID": im_node.GetID(),
                "InputMask_ID": ma_node.GetID(),
                "Additional_InputImage_IDs": [
                    node.GetID() for node in additionalImageNodes
                ],
                "Additional_InputMask_IDs": [
                    node.GetID() for node in additionalMaskNodes
                ],
            }.__str__(),
        )

        self.currentIdx = case_idx

        self._eventListeners.caseLoaded(self.parameterNode)
        return True

    def closeCase(self):
        """Close a case by removing the nodes and reseting values."""
        self._eventListeners.caseAboutToClose(self.parameterNode)
        if self.parameterNode and self.parameterNode.GetParameter("CaseData") != "":
            caseData = ast.literal_eval(self.parameterNode.GetParameter("CaseData"))

            self.removeNodeByID(caseData["InputImage_ID"])
            if caseData["InputMask_ID"]:
                self.removeNodeByID(caseData["InputMask_ID"])

            deque(map(self.removeNodeByID, caseData["Additional_InputImage_IDs"]))
            deque(map(self.removeNodeByID, caseData["Additional_InputMask_IDs"]))
        self.currentIdx = None

    def getCaseData(self):
        """Retrieve node from NodeIDs stored in the CaseData of the parameterNode.

        Each node is returned, None, or an empty list.

        Returns:
            tuple:  image node, mask node, additional image nodes, additional mask nodes
        """

        try:
            caseData = eval(self.parameterNode.GetParameter("CaseData"))
            im = slicer.mrmlScene.GetNodeByID(caseData["InputImage_ID"])
            ma = (
                slicer.mrmlScene.GetNodeByID(caseData["InputMask_ID"])
                if caseData["InputMask_ID"]
                else None
            )
            add_im = list(
                map(slicer.mrmlScene.GetNodeByID, caseData["Additional_InputImage_IDs"])
            )
            add_ma = list(
                map(slicer.mrmlScene.GetNodeByID, caseData["Additional_InputMask_IDs"])
            )
            return im, ma, add_im, add_ma
        except Exception:
            return [None, None, [], []]

    # ------------------------------------------------------------------------------
    def _getColumnValue(self, colName, idx, is_list=False):
        """Retreive the value of a table column at row idx.

        Args:
            colName (str): Name of a validated table column.
            idx (int): The row number of the table.
            is_list (bool, optional): If the column is a list. Defaults to False.

        Returns:
            str: The value of the column specified at by colName and row idx.
        """
        if colName not in self.caseColumns or self.caseColumns[colName] is None:
            if is_list:
                return []
            else:
                return None
        if is_list:
            return [col.GetValue(idx) for col in self.caseColumns[colName]]
        else:
            return self.caseColumns[colName].GetValue(idx)

    # ------------------------------------------------------------------------------
    def _buildPath(self, caseRoot, fname):
        """Build filepath.

        Args:
            caseRoot (str): Parent directory
            fname (str): Name of the file to put in th caseRoot directory.

        Returns:
            str: Fully qualified file path.
        """
        if fname is None or fname == "":
            return None

        if os.path.isabs(fname):
            return fname

        # Add the caseRoot if specified
        if caseRoot is not None:
            fname = os.path.join(caseRoot, fname)

            # Check if the caseRoot is an absolute path
            if os.path.isabs(fname):
                return fname

        # Add the csv_dir to the path if it is not None (loaded table)
        if self.csv_dir is not None:
            fname = os.path.join(self.csv_dir, fname)

        return os.path.abspath(fname)

    # ------------------------------------------------------------------------------
    def _loadImageNode(self, root, fname):
        """Load an Image Node from root/fname.

        Args:
            root (str): Directory of the file.
            fname (str): Name of the file.

        Returns:
            Node: The 3D Slicer Node representing the loaded image.
        """
        im_path = self._buildPath(root, fname)
        if im_path is None:
            return None

        if not os.path.isfile(im_path):
            self.logger.warning("Volume file %s does not exist, skipping...", fname)
            return None

        load_success, im_node = slicer.util.loadVolume(im_path, returnNode=True)
        if not load_success:
            self.logger.warning("Failed to load " + im_path)
            return None

        # Use the file basename as the name for the loaded volume
        im_node.SetName(os.path.splitext(os.path.basename(im_path))[0])

        return im_node

    # ------------------------------------------------------------------------------
    def _loadMaskNode(self, root, fname, ref_im=None):
        """Load a mask node specified at root/fname that is associated with ref_im.

        The masks are loaded as segmentations or converted from Label Maps (nifti).

        Args:
            root (str): Directory where the mask is located.
            fname (str): The file name of the mask.
            ref_im (Node, optional): The node of the loaded reference image.
                                     Defaults to None.

        Returns:
            Node or None: The 3D Slicer Node of the mask or None if failed to load.
        """
        ma_path = self._buildPath(root, fname)
        if ma_path is None:
            return None

        # Check if the file actually exists
        if not os.path.isfile(ma_path):
            self.logger.warning(
                "Segmentation file %s does not exist, skipping...", fname
            )
            return None

        # Determine if file is segmentation based on extension
        isSegmentation = os.path.splitext(ma_path)[0].endswith(".seg")
        # Try to load the mask
        if isSegmentation:
            self.logger.debug("Loading segmentation")
            load_success, ma_node = slicer.util.loadSegmentation(
                ma_path, returnNode=True
            )
        else:
            self.logger.debug("Loading labelmap and converting to segmentation")
            # If not segmentation, then load as labelmap then convert to segmentation
            load_success, ma_node = slicer.util.loadLabelVolume(
                ma_path, returnNode=True
            )
            if load_success:
                # Only try to make a segmentation node if Slicer was able to load
                # the label map
                seg_node = slicer.vtkMRMLSegmentationNode()
                slicer.mrmlScene.AddNode(seg_node)
                seg_node.SetReferenceImageGeometryParameterFromVolumeNode(ref_im)
                load_success = slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
                    ma_node, seg_node
                )
                slicer.mrmlScene.RemoveNode(ma_node)
                ma_node = seg_node

                # Add a storage node for this segmentation node
                file_base, ext = os.path.splitext(ma_path)
                store_node = seg_node.CreateDefaultStorageNode()
                slicer.mrmlScene.AddNode(store_node)
                seg_node.SetAndObserveStorageNodeID(store_node.GetID())

                store_node.SetFileName("%s.seg%s" % (file_base, ext))

                # UnRegister the storage node to prevent a memory leak
                store_node.UnRegister(None)

        if not load_success:
            self.logger.warning("Failed to load " + ma_path)
            return None

        # Use the file basename as the name for the newly loaded segmentation node
        file_base = os.path.splitext(os.path.basename(ma_path))[0]
        if isSegmentation:
            # split off .seg
            file_base = os.path.splitext(file_base)[0]
        ma_node.SetName(file_base)

        return ma_node


class CsvTableEventHandler(IteratorBase.IteratorEventHandlerBase):
    """The CSV Table Event Handler for iterating through the loaded table."""

    def __init__(self, redirect, reader=None, saveNew=False, saveLoaded=False):
        super(CsvTableEventHandler, self).__init__()

        # Some variables that control the output (formatting and control of
        # discarding/saving
        self.redirect = redirect
        self.reader = reader
        self.saveNew = saveNew
        self.saveLoaded = saveLoaded

    @staticmethod
    def _rotateToVolumePlanes(referenceVolume):
        """Snap three planes to views of the reference image.

        Args:
            referenceVolume (Node): The reference image to view in the panes.
        """
        sliceNodes = slicer.util.getNodes("vtkMRMLSliceNode*")
        for name, node in sliceNodes.items():
            node.RotateToVolumePlane(referenceVolume)
        # Snap to IJK to try and avoid rounding errors
        sliceLogics = slicer.app.layoutManager().mrmlSliceLogics()
        numLogics = sliceLogics.GetNumberOfItems()
        for n in range(numLogics):
            l = sliceLogics.GetItemAsObject(n)
            l.SnapSliceOffsetToIJK()

    def onCaseLoaded(self, caller, *args, **kwargs):
        """Tasks performed on loading a case.

        Args:
            caller (Iterator): The iterator class loading the case.
        """
        try:
            im, ma, add_im, add_ma = caller.getCaseData()

            # Set the slice viewers to the correct volumes
            for sliceWidgetName in ["Red", "Green", "Yellow"]:
                logic = (
                    slicer.app.layoutManager()
                    .sliceWidget(sliceWidgetName)
                    .sliceLogic()
                    .GetSliceCompositeNode()
                )
                logic.SetBackgroundVolumeID(im.GetID())
                if len(add_im) > 0:
                    logic.SetForegroundVolumeID(add_im[0].GetID())

            # Snap the viewers to the slice plane of the main image
            self._rotateToVolumePlanes(im)

            # the following code should go somewhere in a separate class
            # including the save part
            if self.redirect:
                if slicer.util.selectedModule() != "SegmentEditor":
                    slicer.util.selectModule("SegmentEditor")
                else:
                    slicer.modules.SegmentEditorWidget.enter()

                # Explicitly set the segmentation and master volume nodes
                segmentEditorWidget = (
                    slicer.modules.segmenteditor.widgetRepresentation().self().editor
                )
                if ma is not None:
                    segmentEditorWidget.setSegmentationNode(ma)
                segmentEditorWidget.setSourceVolumeNode(im)

        except Exception as e:
            if slicer.app.majorVersion * 100 + slicer.app.minorVersion < 411:
                e = e.message
            self.logger.warning("Error loading new case: %s", e)
            self.logger.debug("", exc_info=True)

    def onCaseAboutToClose(self, caller, *args, **kwargs):
        """Perform tasks before a case is closed.

        Save masks to Flywheel instance.

        Args:
            caller (Iterator): The iterator parsing through the table.
        """
        caseData = caller.getCaseData()
        _, mask, _, additionalMasks = caseData
        if self.saveLoaded:
            if mask is not None:
                self.saveMask(mask, self.reader, caseData)
            for ma in additionalMasks:
                self.saveMask(ma, self.reader, caseData)
        if self.saveNew:
            # TODO: this should depend on if more segments were added in segmentation
            # node not depending on a new
            nodes = [
                n
                for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
                if n not in additionalMasks and n != mask
            ]

            deque(map(lambda n: self.saveMask(n, self.reader, caseData), nodes))

        if slicer.util.selectedModule() == "SegmentEditor":
            slicer.modules.SegmentEditorWidget.exit()

    # ------------------------------------------------------------------------------
    def saveMask(self, node, reader, caseData, overwrite_existing=False):
        """Save mask to filesystem.

        This function is not used in this module. It can safely be deleted.

        Args:
            node (Node): Node of mask to save.
            reader (str): Name of the reader or None.
            caseData (dict): Dictionary of the NodeIDs used in this case.
            overwrite_existing (bool, optional): Overwrite existing masks.
                                                 Defaults to False.
        """
        storage_node = node.GetStorageNode()
        if storage_node is not None and storage_node.GetFileName() is not None:
            # mask was loaded, save the updated mask in the same directory
            target_dir = os.path.dirname(storage_node.GetFileName())
        else:
            im_node, _, _, _ = caseData
            target_dir = os.path.dirname(im_node.GetStorageNode().GetFileName())

        if not os.path.isdir(target_dir):
            self.logger.debug("Creating output directory at %s", target_dir)
            os.makedirs(target_dir)

        nodename = node.GetName()

        if reader is not None:
            nodename += "_" + reader
        filename = os.path.join(target_dir, nodename)

        # Prevent overwriting existing files
        if os.path.exists(filename + ".seg.nrrd") and not overwrite_existing:
            self.logger.debug("Filename exists! Generating unique name...")
            idx = 1
            filename += "(%d).seg.nrrd"
            while os.path.exists(filename % idx):
                idx += 1
            filename = filename % idx
        else:
            filename += ".seg.nrrd"

        # Save the node
        slicer.util.saveNode(node, filename)
        self.logger.info("Saved node %s in %s", nodename, filename)
